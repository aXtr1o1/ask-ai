"""
app/agents/retrieval_agent.py
------------------------------
Retrieval Agent — Node 3 in the LangGraph multi-agent pipeline.

WHAT THIS AGENT DOES:
  1. Reads the goal plan produced by the Goal Planning Agent.
  2. Sends the plan + understood intent to an LLM (with thinking).
     The LLM decides: which tool to call and what parameters to pass.
  3. Python executes the decided tool calls against the DB or API.
  4. Returns raw results to the next agent (Validation Agent).

WHY two layers (LLM decision + Python execution):
  The LLM handles ambiguity — it knows which of the 5 modules to query
  for a given intent. Python handles certainty — it calls the exact stored
  procedure with the exact parameters the LLM decided. No AI in the DB call,
  no hardcoded routing rules in the decision layer.

WHY only DB and API channels (no document, no web search):
  Web search is done in Node 1 (Understanding Agent) and stored in
  state['web_search_summary'] — available to all downstream agents.
  Document search was removed: the 5 DB modules cover all facility data.

Model: gemini-2.5-flash with thinking (budget=5000)
"""

import json
import asyncio
import inspect
from typing import List, Dict, Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from app.tools import facility_tools
from app.tools import space_booking_tool
from app.agents.prompts.retrieval_prompt import (
    get_retrieval_system_prompt,
    build_retrieval_user_message,
)
from app.agents.log_config import (
    setup_agent_logger,
    extract_token_counts,
    parse_llm_text,
    strip_json_fences,
)
from app.config import settings

logger = setup_agent_logger("retrieval_agent")


class RetrievalAgent:
    """
    Retrieval Agent — wraps the LLM decision layer and tool execution layer.

    Lifecycle:
      __init__  — discovers DB and API tools at import time (once, not per request)
      _decide() — LLM reads goal plan and returns a JSON retrieval plan
      execute() — Python mechanically calls each tool in the plan
    """

    def __init__(self):
        from langchain_core.tools import BaseTool

        # ── Discover DB tools (facility_tools.py uses @tool decorator) ──────────
        # WHY dynamic discovery: adding a new @tool to facility_tools.py
        # automatically makes it available here — no manual registration needed.
        self._db_tools: Dict[str, Any] = {
            attr.name.lower(): attr
            for name in dir(facility_tools)
            if isinstance((attr := getattr(facility_tools, name)), BaseTool)
        }

        # ── Discover API tools (space_booking_tool.py) ──────────────────────────
        self._api_tools: Dict[str, Any] = {
            attr.name.lower(): attr
            for name in dir(space_booking_tool)
            if isinstance((attr := getattr(space_booking_tool, name)), BaseTool)
        }

        # ── Build tool description strings for the LLM prompt ──────────────────
        # WHY inject at runtime: tool descriptions may change. Dynamic injection
        # ensures the model always sees the current tool list.
        self._db_tools_info  = self._tools_info(self._db_tools)
        self._api_tools_info = self._tools_info(self._api_tools)

        # ── LLM for the decision layer ──────────────────────────────────────────
        # WHY thinking_budget=5000: the retrieval agent must reason over multi-step
        # plans, pick correct tool parameters, and decide aggregate vs. list mode.
        # It sees more context (intent + goal plan) than any other agent.
        self._llm = ChatGoogleGenerativeAI(
            model=settings.MULTI_AGENT_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=1,        # required for thinking mode (Gemini constraint)
            thinking_budget=5000,
        )

    def _tools_info(self, tools: dict) -> str:
        """Return a human-readable list of tools and their descriptions."""
        lines = [
            f'  - "{name}": {getattr(t, "description", "No description.")}'
            for name, t in tools.items()
        ]
        return "\n".join(lines) if lines else "  (none registered)"

    # ── Layer 1: LLM decides what to retrieve ────────────────────────────────

    async def _decide(
        self,
        user_query: str,
        understood_intent: dict,
        goal_plan: dict,
        retry_instructions: Optional[str],
    ) -> tuple[List[Dict], dict]:
        """
        Ask the LLM to produce a retrieval plan as a JSON array of step objects.
        Returns (plan_steps, token_counts).
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

        response     = await self._llm.ainvoke([system_msg, user_msg])
        token_counts = extract_token_counts(response)
        raw          = strip_json_fences(parse_llm_text(response))

        try:
            plan = json.loads(raw)
            if not isinstance(plan, list):
                plan = []
        except json.JSONDecodeError as e:
            logger.error("|| Retrieval LLM JSON parse failed: %s | raw='%s'", e, raw[:200])
            plan = []

        logger.info(
            "|| LLM decided %d retrieval step(s) | thinking=%d | input=%d tokens",
            len(plan), token_counts["thinking"], token_counts["input"],
        )
        return plan, token_counts

    # ── Layer 2: Python executes the decided steps ────────────────────────────

    async def _run_tool(self, tool: Any, params: Dict) -> Any:
        """
        Call a tool's underlying function directly, bypassing the LangChain wrapper.

        WHY bypass BaseTool.invoke():
          BaseTool serialises params as a JSON string then re-parses them inside
          the tool. This causes type-coercion bugs (bool→str, int→float) that
          make Pydantic validation fail. Calling the underlying function directly
          passes Python-typed values exactly as the schema expects.

        WHY inspect.signature() to filter params:
          Tools have fixed param lists. Passing unknown kwargs raises TypeError.
          We use the signature to keep only accepted params.
        """
        func, is_async = None, False
        if hasattr(tool, "coroutine") and tool.coroutine:
            func, is_async = tool.coroutine, True
        elif hasattr(tool, "func") and tool.func:
            func, is_async = tool.func, False
        else:
            func     = getattr(tool, "_orig_arun", None) or getattr(tool, "_orig_run", None) or tool._run
            is_async = asyncio.iscoroutinefunction(func)

        sig        = inspect.signature(func)
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        safe_params = params if has_kwargs else {k: v for k, v in params.items() if k in sig.parameters}

        if is_async:
            return await func(**safe_params)
        # WHY run_in_executor: psycopg2 is synchronous. Running it directly in
        # an async context would block the entire event loop for all requests.
        return await asyncio.get_event_loop().run_in_executor(None, lambda: func(**safe_params))

    async def _exec_db(self, target: str, params: Dict, user_query: str) -> Dict:
        """
        Execute a DB stored-procedure tool call.

        WHY normalize_tool_args before calling:
          The LLM sometimes sends "ANNUALLY" when DB stores "ANNUAL", or
          is_aggregate=True without group_by_columns. The normaliser fixes these
          before they reach the stored procedure, preventing 0-row results.
        """
        tool = self._db_tools.get(target)
        if not tool:
            return {
                "success": False,
                "error": f"DB tool '{target}' not found. Available: {list(self._db_tools)}",
            }
        from app.services.tool_payload_validator import normalize_tool_args
        result = await self._run_tool(tool, normalize_tool_args(target, user_query, params))
        return {"success": True, "data": self._safe_json(result)}

    async def _exec_api(self, target: str, params: Dict, user_query: str) -> Dict:
        """Execute a space booking API tool call."""
        tool = self._api_tools.get(target)
        if not tool:
            return {
                "success": False,
                "error": f"API tool '{target}' not found. Available: {list(self._api_tools)}",
            }
        from app.services.tool_payload_validator import normalize_tool_args
        result = await self._run_tool(tool, normalize_tool_args(target, user_query, params))
        return {"success": True, "data": self._safe_json(result)}

    async def execute_step(
        self,
        step: Dict,
        user_name: str,
        user_id: Optional[int],
        session_id: Optional[str],
        user_query: str,
    ) -> Dict:
        """
        Execute one retrieval step and return the result envelope.

        WHY inject user_name/user_id/session_id here (not in the LLM plan):
          The LLM prompt says "NEVER put user_name in params — injected automatically."
          This ensures auth context is always present and consistent, regardless of
          what the LLM decides. The LLM only deals with business filter values.
        """
        step_id = step.get("step_id")
        source  = str(step.get("source", "")).strip().lower()
        target  = str(step.get("target", "")).strip().lower()
        params  = dict(step.get("params") or {})

        # Inject authentication context
        params.setdefault("user_name", user_name)
        if user_id is not None:
            params.setdefault("user_id", str(user_id))  # BDMInput schema expects str
        if session_id:
            params.setdefault("session_id", session_id)

        logger.info(
            "|| Step %s | [%s] %s | filters=%s",
            step_id, source.upper(), target, [k for k in params if k not in ("user_name", "user_id", "session_id")],
        )

        try:
            if source == "db":
                data = await self._exec_db(target, params, user_query)
            elif source == "api":
                data = await self._exec_api(target, params, user_query)
            else:
                return {"step_id": step_id, "success": False,
                        "error": f"Unknown source '{source}'. Use 'db' or 'api'."}

            return {"step_id": step_id, "retrieval_reasoning": step.get("retrieval_reasoning", ""), **data}

        except Exception as e:
            logger.error("|| Step %s failed: %s", step_id, e, exc_info=True)
            return {"step_id": step_id, "success": False, "error": str(e)}

    async def execute_plan(
        self,
        plan: List[Dict],
        user_name: str,
        user_id: Optional[int],
        session_id: Optional[str],
        user_query: str,
    ) -> List[Dict]:
        """
        Execute all steps in the retrieval plan sequentially.

        WHY sequential (not parallel):
          Some steps depend on previous step results (e.g. get count first,
          then fetch list for the highest-count building). Sequential execution
          ensures each step can reference prior results in the Execution Agent.
        """
        results = []
        for step in plan:
            res = await self.execute_step(step, user_name, user_id, session_id, user_query)
            results.append(res)
        return results

    @staticmethod
    def _safe_json(text: Any) -> Any:
        """Parse JSON string safely; return raw value on failure."""
        if isinstance(text, str):
            try:
                return json.loads(text)
            except Exception:
                return text
        return text


# ── Singleton ─────────────────────────────────────────────────────────────────
# WHY singleton: tool discovery in __init__ scans module attributes at import
# time. Creating one instance at startup reuses the tool registry for every
# request instead of re-scanning on each query.
retrieval_agent = RetrievalAgent()


# ── LangGraph Node ────────────────────────────────────────────────────────────

async def retrieval_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph Node 3: Retrieval Agent.

    Reads from state:
      user_query, understood_intent, goal_plan,
      user_name, user_id, session_id,
      retry_instructions (set by Validation Agent on RETRY)

    Writes to state:
      retrieval_plan, retrieval_results, retrieval_log,
      retrieval_thinking_tokens, agent_trace
    """
    user_query         = state.get("user_query", "")
    understood_intent  = state.get("understood_intent") or {}
    goal_plan          = state.get("goal_plan") or {}
    retry_instructions = state.get("retry_instructions")
    retry_count        = state.get("retry_count", 0) or 0
    user_name          = state.get("user_name", "system")
    user_id            = state.get("user_id")
    session_id         = state.get("session_id")
    trace              = list(state.get("agent_trace", []))

    logger.info("=" * 66)
    logger.info("Retrieval Agent -- START | query='%s' | retry=%d", user_query[:80], retry_count)
    if retry_instructions:
        logger.info("|| RETRY: %s", retry_instructions[:200])
    logger.info("=" * 66)

    approach       = goal_plan.get("approach", "")
    tools_required = goal_plan.get("tools_required") or []

    # ── Short-circuit: DIRECT_ANSWER — no DB data needed ─────────────────────
    # WHY: Goal Planning decided the query can be answered from conversation
    # history or general knowledge. Hitting the DB would be wasteful.
    if approach == "DIRECT_ANSWER":
        logger.info("|| DIRECT_ANSWER — skipping retrieval")
        trace.append("[RetrievalAgent] DIRECT_ANSWER | no retrieval")
        return {
            **state,
            "retrieval_plan":            [],
            "retrieval_results":         [],
            "retrieval_log":             "Skipped — DIRECT_ANSWER",
            "retrieval_thinking_tokens": 0,
            "agent_trace":               trace,
        }

    # ── Short-circuit: CLARIFY with no tools — just ask the user ─────────────
    if approach == "CLARIFY" and not tools_required:
        logger.info("|| CLARIFY (no tools) — skipping retrieval")
        trace.append("[RetrievalAgent] CLARIFY | no tools | no retrieval")
        return {
            **state,
            "retrieval_plan":            [],
            "retrieval_results":         [],
            "retrieval_log":             "Skipped — CLARIFY with no tools",
            "retrieval_thinking_tokens": 0,
            "agent_trace":               trace,
        }

    # ── Short-circuit: WEB_SEARCH — no DB data needed ───────────────────────
    # WHY: Goal Planning set approach=WEB_SEARCH meaning the answer comes
    # entirely from external sources (web search already ran in the Understanding
    # Agent). There is no DB tool to call. Connecting to the DB to load enum
    # values would block for a new connection with zero benefit.
    if approach == "WEB_SEARCH":
        logger.info("|| WEB_SEARCH approach — skipping DB retrieval (web search already ran in Node 1)")
        trace.append("[RetrievalAgent] WEB_SEARCH | no DB retrieval")
        return {
            **state,
            "retrieval_plan":            [],
            "retrieval_results":         [],
            "retrieval_log":             "Skipped — WEB_SEARCH (handled by Understanding Agent)",
            "retrieval_thinking_tokens": 0,
            "agent_trace":               trace,
        }

    # ── Step 1: LLM decides the plan ─────────────────────────────────────────
    try:
        plan, token_counts = await retrieval_agent._decide(
            user_query=user_query,
            understood_intent=understood_intent,
            goal_plan=goal_plan,
            retry_instructions=retry_instructions,
        )
    except Exception as e:
        logger.error("|| LLM decision failed: %s", e, exc_info=True)
        plan, token_counts = [], {"thinking": 0, "input": 0, "output": 0}

    # Log the plan
    logger.info(
        "|| ============================================================\n"
        "||  RETRIEVAL PLAN (%d step(s))\n"
        "|| ============================================================",
        len(plan),
    )
    for step in plan:
        filters = {k: v for k, v in (step.get("params") or {}).items()
                   if k not in ("user_name", "user_id", "session_id")}
        logger.info(
            "||  Step %s -> [%s] %s | filters=%s | why: %s",
            step.get("step_id", "?"),
            str(step.get("source", "?")).upper(),
            step.get("target", "?"),
            filters,
            str(step.get("retrieval_reasoning", ""))[:100],
        )

    # ── Step 2: Execute the plan ──────────────────────────────────────────────
    results = await retrieval_agent.execute_plan(
        plan=plan,
        user_name=user_name,
        user_id=user_id,
        session_id=session_id,
        user_query=user_query,
    )

    # ── Summary log ──────────────────────────────────────────────────────────
    ok = sum(1 for r in results if r.get("success"))
    log_str = (
        f"\n|| ============================================================\n"
        f"||  RETRIEVAL RESULT\n"
        f"|| ============================================================\n"
        f"||  Steps: {len(plan)} decided | {ok}/{len(results)} succeeded\n"
        f"||  Thinking: {token_counts['thinking']:,} tokens | Input: {token_counts['input']:,} tokens\n"
        f"|| ============================================================"
    )
    logger.info(log_str)

    trace.append(
        f"[RetrievalAgent] steps={len(plan)} | ok={ok}/{len(results)} | "
        f"thinking={token_counts['thinking']} | retry={retry_count}"
    )

    return {
        **state,
        "retrieval_plan":            plan,
        "retrieval_results":         results,
        "retrieval_log":             log_str,
        "retrieval_thinking_tokens": token_counts["thinking"],
        "agent_trace":               trace,
    }
