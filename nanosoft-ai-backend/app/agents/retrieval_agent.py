"""
Retrieval Agent — Node 3 in the LangGraph multi-agent pipeline.

Responsibilities:
  - Receive the goal plan from the Goal Planning Agent
  - Use an LLM with thinking to decide WHAT to retrieve, WHICH tool, WHAT params
  - Execute the decided retrieval steps through the appropriate tool channels
  - Log a clean, structured summary to the console

The retrieval decision is fully model-based (no hardcoded routing rules).
The tool execution layer (DB, API, Web, Document) remains mechanical.

Model: gemini-2.5-flash with thinking enabled
"""

import json
import asyncio
import inspect
import urllib.request
import urllib.parse
import re
import os
from typing import List, Dict, Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

# Facility Database Tools (DB in architecture diagram)
from app.tools import facility_tools

# Space Booking API Tools (API in architecture diagram)
from app.tools import space_booking_tool

from app.agents.prompts.retrieval_prompt import (
    get_retrieval_system_prompt,
    build_retrieval_user_message,
)
from app.agents.log_config import setup_agent_logger
from app.config import settings

logger = setup_agent_logger("retrieval_agent")

# Stop words for document keyword cleanup
_STOP_WORDS = frozenset({
    "i", "a", "an", "the", "to", "of", "in", "on", "at", "for",
    "and", "or", "is", "it", "be", "do", "we", "my", "me",
    "need", "want", "book", "find", "show", "get", "give", "go",
    "please", "can", "could", "would", "like", "any", "some",
    "search", "find", "query", "select"
})


class RetrievalAgent:
    """
    Retrieval Agent — Model-Based Decision Layer + Mechanical Execution Layer.

    The LLM decides WHAT to retrieve (which tool, which params).
    The execution layer mechanically calls the tool and returns raw data.

    Channels:
      1. DB       — Facility databases (ASSETS, PPM, BDM, FA, SB)
      2. API      — Space booking APIs (GET_SPOTS, BOOK_SPOT, GET_BOOKING_STATUS)
      3. DOCUMENT — Local file searching in /docs
      4. WEB_SEARCH — DuckDuckGo Lite
    """

    def __init__(self):
        from langchain_core.tools import BaseTool

        # Register DB tools
        self._db_tools = {}
        for attr_name in dir(facility_tools):
            attr = getattr(facility_tools, attr_name)
            if isinstance(attr, BaseTool):
                self._db_tools[attr.name.lower()] = attr

        # Register API tools
        self._api_tools = {}
        for attr_name in dir(space_booking_tool):
            attr = getattr(space_booking_tool, attr_name)
            if isinstance(attr, BaseTool):
                self._api_tools[attr.name.lower()] = attr

        # In-memory retrieval cache
        self._cache = {}

        # Build tool info strings for the system prompt
        self._db_tools_info = self._build_tools_info(self._db_tools)
        self._api_tools_info = self._build_tools_info(self._api_tools)

        # LLM model with thinking enabled — for deciding retrieval strategy
        self._llm = ChatGoogleGenerativeAI(
            model=settings.MULTI_AGENT_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=1,          # required for thinking mode
            thinking_budget=5000,   # correct kwarg for langchain_google_genai
        )

    def _build_tools_info(self, tools_dict: dict) -> str:
        """Build a human-readable string listing all tools and their descriptions."""
        lines = []
        for name, tool in tools_dict.items():
            desc = getattr(tool, "description", "No description available.")
            lines.append(f'  - "{name}": {desc}')
        return "\n".join(lines) if lines else "  (No tools registered)"

    # ── LLM Decision Layer ────────────────────────────────────────────────────

    async def _decide_retrieval_plan(
        self,
        user_query: str,
        understood_intent: dict,
        goal_plan: dict,
        retry_instructions: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Use the LLM to decide what to retrieve: which channel, which tool, what params.
        Returns a list of step dicts ready for the mechanical execution layer.
        """
        system_msg = get_retrieval_system_prompt(
            db_tools_info=self._db_tools_info,
            api_tools_info=self._api_tools_info,
        )
        user_msg = HumanMessage(content=build_retrieval_user_message(
            user_query=user_query,
            understood_intent=understood_intent,
            goal_plan=goal_plan,
            retry_instructions=retry_instructions,
        ))

        response = await self._llm.ainvoke([system_msg, user_msg])

        # Extract token counts from usage_metadata
        # In langchain_google_genai 4.2.0, thinking tokens are at:
        #   usage_metadata['output_token_details']['reasoning']
        token_counts = {"thinking": 0, "input": 0, "output": 0}
        usage = getattr(response, "usage_metadata", None)
        if usage and isinstance(usage, dict):
            token_counts["input"]    = usage.get("input_tokens", 0) or 0
            token_counts["output"]   = usage.get("output_tokens", 0) or 0
            out_details = usage.get("output_token_details") or {}
            if isinstance(out_details, dict):
                token_counts["thinking"] = out_details.get("reasoning", 0) or 0

        # Parse JSON
        raw_content = response.content
        if isinstance(raw_content, list):
            text_parts = [
                p.get("text", "") if isinstance(p, dict) else str(p)
                for p in raw_content
                if not (isinstance(p, dict) and p.get("type") == "thinking")
            ]
            raw_content = "".join(text_parts).strip()
        else:
            raw_content = str(raw_content).strip()

        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]
        raw_content = raw_content.strip()

        try:
            plan = json.loads(raw_content)
            if not isinstance(plan, list):
                plan = []
        except json.JSONDecodeError as e:
            logger.error("Retrieval LLM JSON parse failed: %s | raw='%s'", e, raw_content[:200])
            plan = []

        logger.info(
            "|| Retrieval LLM decided %d step(s) | thinking_tokens=%d | input_tokens=%d",
            len(plan), token_counts["thinking"], token_counts["input"]
        )
        return plan, token_counts

    # ── Mechanical Execution Layer ────────────────────────────────────────────

    def _make_cache_key(self, source: str, target: str, params: Dict[str, Any]) -> str:
        stable_params = {k: v for k, v in params.items() if k not in ("session_id", "user_name")}
        serialized = json.dumps(stable_params, sort_keys=True)
        return f"{source}:{target}:{serialized}"

    async def execute_step(
        self,
        step: Dict[str, Any],
        user_name: str,
        session_id: Optional[str] = None,
        user_query: str = "",
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute a single retrieval step mechanically."""
        step_id = step.get("step_id")
        source  = str(step.get("source", "")).strip().lower()
        target  = str(step.get("target", "")).strip().lower()
        params  = dict(step.get("params", {}))

        if "user_name" not in params and user_name:
            params["user_name"] = user_name
        if "user_id" not in params and user_id is not None:
            params["user_id"] = str(user_id)   # BDMInput schema expects str, not int
        if "session_id" not in params and session_id:
            params["session_id"] = session_id

        # Cache for idempotent operations
        use_cache = source in ("db", "web_search")
        if use_cache:
            cache_key = self._make_cache_key(source, target, params)
            if cache_key in self._cache:
                logger.info("Cache hit for Step %s (%s:%s)", step_id, source, target)
                return {
                    "step_id": step_id,
                    "success": True,
                    "cached": True,
                    "data": self._cache[cache_key],
                    "retrieval_reasoning": step.get("retrieval_reasoning", ""),
                }

        logger.info(
            "Executing Step %s | source=%s | target=%s | params=%s",
            step_id, source, target, list(params.keys())
        )

        try:
            if source == "db":
                res_data = await self._execute_db(target, params, user_query)
            elif source == "api":
                res_data = await self._execute_api(target, params, user_query)
            elif source == "document":
                res_data = await self._execute_document(target, params)
            elif source == "web_search":
                res_data = await self._execute_web_search(target, params)
            else:
                return {
                    "step_id": step_id,
                    "success": False,
                    "error": f"Unknown retrieval source: '{source}'",
                }

            if use_cache and res_data and res_data.get("success"):
                cache_key = self._make_cache_key(source, target, params)
                self._cache[cache_key] = res_data.get("data")

            return {
                "step_id": step_id,
                "retrieval_reasoning": step.get("retrieval_reasoning", ""),
                **res_data,
            }

        except Exception as e:
            logger.error("Step %s execution failed: %s", step_id, e, exc_info=True)
            return {
                "step_id": step_id,
                "success": False,
                "error": str(e),
            }

    async def execute_plan(
        self,
        plan: List[Dict[str, Any]],
        user_name: str,
        session_id: Optional[str] = None,
        parallel: bool = False,
        user_query: str = "",
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a list of retrieval steps sequentially or in parallel."""
        if not plan:
            return []
        if parallel:
            logger.info("Executing retrieval plan in PARALLEL (%d steps)", len(plan))
            tasks = [self.execute_step(step, user_name, session_id, user_query, user_id) for step in plan]
            return list(await asyncio.gather(*tasks))
        else:
            logger.info("Executing retrieval plan SEQUENTIALLY (%d steps)", len(plan))
            results = []
            for step in plan:
                res = await self.execute_step(step, user_name, session_id, user_query, user_id)
                results.append(res)
            return results

    async def _run_tool_direct(self, tool: Any, params: Dict[str, Any]) -> Any:
        """Directly execute the tool's underlying function, bypassing LangChain wrapper."""
        func = None
        is_async = False

        if hasattr(tool, "coroutine") and tool.coroutine is not None:
            func = tool.coroutine
            is_async = True
        elif hasattr(tool, "func") and tool.func is not None:
            func = tool.func
            is_async = False
        else:
            if hasattr(tool, "_orig_arun") and tool._orig_arun is not None:
                func = tool._orig_arun
                is_async = True
            else:
                func = getattr(tool, "_orig_run", None) or tool._run
                is_async = False

        sig = inspect.signature(func)
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        if has_kwargs:
            clean_params = params
        else:
            clean_params = {k: v for k, v in params.items() if k in sig.parameters}

        if is_async:
            return await func(**clean_params)
        else:
            return await asyncio.get_event_loop().run_in_executor(
                None, lambda: func(**clean_params)
            )

    async def _execute_db(self, target: str, params: Dict[str, Any], user_query: str = "") -> Dict[str, Any]:
        tool = self._db_tools.get(target)
        if not tool:
            return {
                "success": False,
                "error": f"Database target '{target}' not supported. Available: {list(self._db_tools.keys())}",
            }
        from app.services.tool_payload_validator import normalize_tool_args
        normalized_params = normalize_tool_args(target, user_query, params)
        result_str = await self._run_tool_direct(tool, normalized_params)
        return {"success": True, "data": self._parse_json_safe(result_str)}

    async def _execute_api(self, target: str, params: Dict[str, Any], user_query: str = "") -> Dict[str, Any]:
        tool = self._api_tools.get(target)
        if not tool:
            return {
                "success": False,
                "error": f"API target '{target}' not supported. Available: {list(self._api_tools.keys())}",
            }
        from app.services.tool_payload_validator import normalize_tool_args
        normalized_params = normalize_tool_args(target, user_query, params)
        result_str = await self._run_tool_direct(tool, normalized_params)
        return {"success": True, "data": self._parse_json_safe(result_str)}

    async def _execute_document(self, target: str, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query", target or "")
        limit = params.get("limit", 3)

        possible_dirs = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs")),
            os.path.abspath(os.path.join(os.getcwd(), "docs")),
            os.path.abspath(os.path.join(os.getcwd(), "..", "docs")),
        ]
        docs_dir = None
        for d in possible_dirs:
            if os.path.exists(d) and os.path.isdir(d):
                docs_dir = d
                break

        if not docs_dir:
            return {"success": False, "error": f"Docs directory not found. Searched: {possible_dirs}"}

        query_words = [w.strip().lower() for w in re.split(r'\W+', query) if w.strip()]
        keywords = [w for w in query_words if w not in _STOP_WORDS]

        scored_files = []
        for root, _, files in os.walk(docs_dir):
            for file in files:
                if file.endswith((".md", ".txt", ".json")):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                        score = 0
                        if keywords:
                            content_lower = content.lower()
                            file_lower = file.lower()
                            for kw in keywords:
                                if kw in file_lower:
                                    score += 15
                                if kw in content_lower:
                                    score += content_lower.count(kw)
                        scored_files.append((score, file, content))
                    except Exception as e:
                        logger.warning("Error reading doc file %s: %s", file, e)

        if not scored_files:
            return {"success": True, "data": []}

        if keywords:
            scored_files.sort(key=lambda x: x[0], reverse=True)

        docs_content = []
        for score, file, content in scored_files[:3]:
            docs_content.append(f"--- START FILE: {file} ---\n{content}\n--- END FILE: {file} ---")

        try:
            docs_joined = "\n\n".join(docs_content)
            prompt = f"""
You are an advanced document search assistant.
Search the provided documents and find sections relevant to the user query.

User Query: {query}

Provided Documents:
{docs_joined}

Return a JSON list of matches. Each match must contain:
- "file_name": the name of the file
- "snippet": a concise relevant snippet
- "line_no": approximate 1-indexed line number
- "score": relevance score 1-10

Output ONLY a raw JSON array. No markdown, no extra text.
"""
            doc_llm = ChatGoogleGenerativeAI(
                model=settings.MULTI_AGENT_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.0,
            )
            response = await doc_llm.ainvoke([HumanMessage(content=prompt)])
            raw_content = response.content.strip()
            if raw_content.startswith("```"):
                raw_content = raw_content.split("```")[1]
                if raw_content.startswith("json"):
                    raw_content = raw_content[4:]
            raw_content = raw_content.strip()
            results = json.loads(raw_content)
            if not isinstance(results, list):
                results = [results]
            results.sort(key=lambda x: x.get("score", 0), reverse=True)
            return {"success": True, "data": results[:limit]}
        except Exception as e:
            logger.error("Document search failed: %s", e)
            return {"success": False, "error": f"Document search failed: {e}"}

    async def _execute_web_search(self, target: str, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query", target or "")
        limit = params.get("limit", 5)

        logger.info("Fetching DuckDuckGo Lite results for: '%s'", query)
        url = "https://lite.duckduckgo.com/lite/"
        data = urllib.parse.urlencode({"q": query}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Origin": "https://lite.duckduckgo.com",
                "Referer": "https://lite.duckduckgo.com/",
            }
        )
        try:
            def fetch():
                with urllib.request.urlopen(req, timeout=8) as resp:
                    return resp.read().decode("utf-8")

            html = await asyncio.get_event_loop().run_in_executor(None, fetch)

            from html.parser import HTMLParser

            class DDGHTMLParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.results = []
                    self.current_result = None
                    self.in_title = False
                    self.in_snippet = False
                    self.temp_text = []

                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    cls = attrs_dict.get("class", "")
                    cls_list = cls.split()
                    if tag == "a" and "result-link" in cls_list:
                        self.in_title = True
                        self.temp_text = []
                        self.current_result = {
                            "title": "",
                            "url": attrs_dict.get("href", ""),
                            "snippet": "",
                        }
                    elif "result-snippet" in cls_list:
                        self.in_snippet = True
                        self.temp_text = []

                def handle_data(self, data):
                    if self.in_title or self.in_snippet:
                        self.temp_text.append(data)

                def handle_endtag(self, tag):
                    if self.in_title and tag == "a":
                        self.in_title = False
                        if self.current_result:
                            self.current_result["title"] = "".join(self.temp_text).strip()
                    elif self.in_snippet and tag in ("td", "div", "span"):
                        self.in_snippet = False
                        if self.current_result:
                            self.current_result["snippet"] = "".join(self.temp_text).strip()
                            self.current_result["title"] = self.current_result["title"].replace("\u00a0", " ")
                            self.current_result["snippet"] = self.current_result["snippet"].replace("\u00a0", " ")
                            self.results.append(self.current_result)
                            self.current_result = None

            parser = DDGHTMLParser()
            parser.feed(html)
            results = parser.results[:limit]

            if results:
                return {"success": True, "source": "duckduckgo_lite", "data": results}

        except Exception as e:
            logger.error("DuckDuckGo Lite search failed: %s", e)
            return {"success": False, "error": f"Web search failed: {e}"}

        return {"success": False, "error": "No search results returned."}

    def _parse_json_safe(self, text: str) -> Any:
        try:
            return json.loads(text)
        except Exception:
            return text


# ── Singleton ─────────────────────────────────────────────────────────────────
retrieval_agent = RetrievalAgent()


# ── LangGraph Node ────────────────────────────────────────────────────────────

async def retrieval_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph Node: Retrieval Agent.

    Reads:  state['goal_plan'], state['understood_intent'], state['user_query'],
            state['retry_instructions'] (if this is a retry)
    Writes: state['retrieval_plan'], state['retrieval_results'],
            state['retrieval_log'], state['retrieval_thinking_tokens']
    """
    user_query        = state.get("user_query", "")
    understood_intent = state.get("understood_intent", {}) or {}
    goal_plan         = state.get("goal_plan", {}) or {}
    retry_instructions = state.get("retry_instructions")
    retry_count       = state.get("retry_count", 0) or 0
    user_name         = state.get("user_name", "system")
    user_id           = state.get("user_id")          # ← authenticated user ID
    session_id        = state.get("session_id")
    trace             = list(state.get("agent_trace", []))

    logger.info("=" * 66)
    logger.info("Retrieval Agent -- START | query='%s' | retry=%d", user_query[:80], retry_count)
    if retry_instructions:
        logger.info("|| RETRY INSTRUCTIONS: %s", retry_instructions[:200])
    logger.info("=" * 66)

    approach = goal_plan.get("approach", "")

    # Skip retrieval only for DIRECT_ANSWER, or for CLARIFY with no tools listed.
    # If CLARIFY has tools_required, we still fetch data (best-effort broad retrieval)
    # so the Execution Agent can present real data alongside any clarification note.
    tools_required = goal_plan.get("tools_required") or []
    if approach == "DIRECT_ANSWER":
        logger.info("|| Approach is DIRECT_ANSWER — skipping retrieval")
        trace.append(
            f"[RetrievalAgent] approach={approach} | no retrieval needed | thinking_tokens=0"
        )
        return {
            **state,
            "retrieval_plan":             [],
            "retrieval_results":          [],
            "retrieval_log":              "No retrieval needed — approach is DIRECT_ANSWER",
            "retrieval_thinking_tokens":  0,
            "agent_trace":                trace,
        }

    if approach == "CLARIFY" and not tools_required:
        logger.info("|| Approach is CLARIFY with no tools listed — skipping retrieval")
        trace.append(
            f"[RetrievalAgent] approach=CLARIFY | no tools listed | no retrieval | thinking_tokens=0"
        )
        return {
            **state,
            "retrieval_plan":             [],
            "retrieval_results":          [],
            "retrieval_log":              "No retrieval — approach is CLARIFY and no tools were specified",
            "retrieval_thinking_tokens":  0,
            "agent_trace":                trace,
        }

    if approach == "CLARIFY" and tools_required:
        logger.info(
            "|| Approach is CLARIFY but tools are listed (%s) — proceeding with best-effort retrieval",
            tools_required,
        )

    # ── Step 1: LLM decides the retrieval plan ────────────────────────────────
    try:
        decided_plan, token_counts = await retrieval_agent._decide_retrieval_plan(
            user_query=user_query,
            understood_intent=understood_intent,
            goal_plan=goal_plan,
            retry_instructions=retry_instructions,
        )
    except Exception as e:
        logger.error("Retrieval LLM decision failed: %s", e, exc_info=True)
        decided_plan = []
        token_counts = {"thinking": 0, "input": 0, "output": 0}

    logger.info("|| Retrieval plan decided: %d steps", len(decided_plan))
    for step in decided_plan:
        logger.info(
            "||   Step %s | source=%s | target=%s | params=%s | reason=%s",
            step.get("step_id"), step.get("source"), step.get("target"),
            list((step.get("params") or {}).keys()),
            step.get("retrieval_reasoning", "")[:80],
        )

    # ── Step 2: Execute the decided plan ─────────────────────────────────────
    if decided_plan:
        logger.info("\n|| ============================================================")
        logger.info("||  RETRIEVAL AGENT -- EXECUTION PLAN")
        logger.info("|| ============================================================")
        for step in decided_plan:
            s_id     = step.get("step_id", "?")
            s_source = step.get("source", "?")
            s_target = step.get("target", "?")
            s_params = {k: v for k, v in (step.get("params") or {}).items()
                        if k not in ("user_name", "user_id", "session_id", "offset")}
            s_reason = step.get("retrieval_reasoning", "")
            logger.info(
                "||  Step %-2s → [%s] Tool: %-10s | Filters: %s",
                s_id, s_source.upper(), s_target, s_params
            )
            logger.info("||           Why : %s", s_reason[:120])
        logger.info("|| ============================================================")

    results = await retrieval_agent.execute_plan(
        plan=decided_plan,
        user_name=user_name,
        session_id=session_id,
        user_query=user_query,
        user_id=user_id,
    )

    # ── Log and trace ─────────────────────────────────────────────────────────
    success_count = sum(1 for r in results if r.get("success"))
    log_str = (
        f"\n"
        f"|| ============================================================\n"
        f"||  RETRIEVAL AGENT -- RESULT\n"
        f"|| ============================================================\n"
        f"||  Query          : {user_query[:80]}\n"
        f"||  Steps Decided  : {len(decided_plan)}\n"
        f"||  Steps Succeeded: {success_count}/{len(results)}\n"
        f"||  Thinking Tokens: {token_counts['thinking']:,}\n"
        f"||  Input Tokens   : {token_counts['input']:,}\n"
        f"||  Output Tokens  : {token_counts['output']:,}\n"
        f"|| ============================================================"
    )
    logger.info(log_str)

    trace.append(
        f"[RetrievalAgent] steps={len(decided_plan)} | success={success_count}/{len(results)} | "
        f"thinking_tokens={token_counts['thinking']} | retry={retry_count}"
    )

    return {
        **state,
        "retrieval_plan":            decided_plan,
        "retrieval_results":         results,
        "retrieval_log":             log_str,
        "retrieval_thinking_tokens": token_counts["thinking"],
        "agent_trace":               trace,
    }
