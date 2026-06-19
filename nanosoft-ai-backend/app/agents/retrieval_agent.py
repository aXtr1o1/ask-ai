import logging
import json
import asyncio
import inspect
import urllib.request
import urllib.parse
import re
import os
from typing import List, Dict, Any, Optional

# Facility Database Tools (DB in architecture diagram)
from app.tools import facility_tools

# Space Booking API Tools (API in architecture diagram)
from app.tools import space_booking_tool

logger = logging.getLogger("retrieval_agent")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)

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
    Retrieval Agent (as specified in the architecture diagram).
    Delegates information retrieval tasks to appropriate targets:
    1. DB (Facility databases: ASSETS, PPM, BDM, FA, SB)
    2. API (Booking APIs: GET_SPOTS, BOOK_SPOT, GET_BOOKING_STATUS)
    3. DOCUMENT (Local file searching in /docs)
    4. WEB_SEARCH (DuckDuckGo Lite crawling with LLM fallback)
    """

    def __init__(self):
        # Maps step actions/sources to tools dynamically by scanning modules for LangChain tools
        from langchain_core.tools import BaseTool

        self._db_tools = {}
        for attr_name in dir(facility_tools):
            attr = getattr(facility_tools, attr_name)
            if isinstance(attr, BaseTool):
                self._db_tools[attr.name.lower()] = attr

        self._api_tools = {}
        for attr_name in dir(space_booking_tool):
            attr = getattr(space_booking_tool, attr_name)
            if isinstance(attr, BaseTool):
                self._api_tools[attr.name.lower()] = attr
        # In-memory retrieval cache to avoid repeating identical heavy lookups
        self._cache = {}

        # Initialize Google Generative AI Model for LLM processing
        from langchain_google_genai import ChatGoogleGenerativeAI
        from app.config import settings
        self.model = ChatGoogleGenerativeAI(
            model=settings.MULTI_AGENT_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.0
        )

        # Dynamically patch loaded tools in-place to route through retrieval_agent
        self._patch_tools()

    def _patch_tools(self):
        def wrap_tool(tool_obj, source: str):
            if hasattr(tool_obj, "_orig_run"):
                return  # Avoid double patching

            orig_run = tool_obj._run
            orig_arun = tool_obj._arun

            tool_obj._orig_run = orig_run
            tool_obj._orig_arun = orig_arun

            def new_run(*args, **kwargs):
                user_name = kwargs.get("user_name", "system")
                session_id = kwargs.get("session_id", "system_session")
                step = {
                    "source": source,
                    "target": tool_obj.name.lower(),
                    "params": kwargs
                }
                import asyncio
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(asyncio.run, self.execute_step(step, user_name, session_id))
                    result = future.result()

                if isinstance(result, dict) and result.get("success"):
                    data = result.get("data")
                    if isinstance(data, (dict, list)):
                        return json.dumps(data)
                    return str(data)
                else:
                    error_msg = result.get("error") if isinstance(result, dict) else str(result)
                    return f"Error executing tool {tool_obj.name}: {error_msg}"

            async def new_arun(*args, **kwargs):
                user_name = kwargs.get("user_name", "system")
                session_id = kwargs.get("session_id", "system_session")
                step = {
                    "source": source,
                    "target": tool_obj.name.lower(),
                    "params": kwargs
                }
                result = await self.execute_step(step, user_name, session_id)

                if isinstance(result, dict) and result.get("success"):
                    data = result.get("data")
                    if isinstance(data, (dict, list)):
                        return json.dumps(data)
                    return str(data)
                else:
                    error_msg = result.get("error") if isinstance(result, dict) else str(result)
                    return f"Error executing tool {tool_obj.name}: {error_msg}"

            tool_obj._run = new_run
            tool_obj._arun = new_arun

        for tool_obj in self._db_tools.values():
            wrap_tool(tool_obj, "db")
        for tool_obj in self._api_tools.values():
            wrap_tool(tool_obj, "api")

    def _make_cache_key(self, source: str, target: str, params: Dict[str, Any]) -> str:
        # Filter out dynamic parameters like session_id/user_name to maximize cache hit rate
        stable_params = {k: v for k, v in params.items() if k not in ("session_id", "user_name")}
        serialized = json.dumps(stable_params, sort_keys=True)
        return f"{source}:{target}:{serialized}"

    async def execute_step(self, step: Dict[str, Any], user_name: str, session_id: Optional[str] = None, user_query: str = "") -> Dict[str, Any]:
        """
        Executes a single retrieval step.
        Input format:
        {
            "step_id": int/str,
            "source": "db" | "api" | "document" | "web_search",
            "target": str,  # e.g., "assets", "get_spots", or "query_term"
            "params": dict  # Arguments to pass to the tool
        }
        """
        step_id = step.get("step_id")
        source = str(step.get("source", "")).strip().lower()
        target = str(step.get("target", "")).strip().lower()
        params = step.get("params", {})

        # Inject standard parameters if missing
        if "user_name" not in params and user_name:
            params["user_name"] = user_name
        if "session_id" not in params and session_id:
            params["session_id"] = session_id

        # Check cache (only for db and web_search, which are idempotent query operations)
        use_cache = source in ("db", "web_search")
        if use_cache:
            cache_key = self._make_cache_key(source, target, params)
            if cache_key in self._cache:
                logger.info(f"💾 Cache hit for Step {step_id} ({source}:{target})")
                return {
                    "step_id": step_id,
                    "success": True,
                    "cached": True,
                    "data": self._cache[cache_key]
                }

        logger.info(f"🔄 Executing Step {step_id} | Source: {source} | Target: {target} | Params: {list(params.keys())}")

        try:
            res_data = None
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
                    "error": f"Unknown retrieval source: '{source}'"
                }

            # Store in cache if successful
            if use_cache and res_data and res_data.get("success"):
                cache_key = self._make_cache_key(source, target, params)
                self._cache[cache_key] = res_data.get("data")

            return {
                "step_id": step_id,
                **res_data
            }
        except Exception as e:
            logger.error(f"❌ Step {step_id} execution failed: {e}", exc_info=True)
            return {
                "step_id": step_id,
                "success": False,
                "error": str(e)
            }

    async def execute_plan(self, plan: List[Dict[str, Any]], user_name: str, session_id: Optional[str] = None, parallel: bool = False, user_query: str = "") -> List[Dict[str, Any]]:
        """Executes a list of retrieval steps either sequentially or in parallel."""
        if parallel:
            logger.info("⚡ Executing retrieval plan in PARALLEL")
            tasks = [self.execute_step(step, user_name, session_id, user_query) for step in plan]
            return list(await asyncio.gather(*tasks))
        else:
            logger.info("🚶 Executing retrieval plan SEQUENTIALLY")
            results = []
            for step in plan:
                res = await self.execute_step(step, user_name, session_id, user_query)
                results.append(res)
            return results

    async def _run_tool_direct(self, tool: Any, params: Dict[str, Any]) -> Any:
        """
        Directly executes the tool's underlying function (async or sync) 
        bypassing LangChain wrapper and validation checks to avoid missing 'config' argument errors.
        """
        func = None
        is_async = False
        
        # Check if the tool wraps an underlying function (standard for @tool decorated items)
        if hasattr(tool, "coroutine") and tool.coroutine is not None:
            func = tool.coroutine
            is_async = True
        elif hasattr(tool, "func") and tool.func is not None:
            func = tool.func
            is_async = False
        else:
            # Fallback to orig_run/orig_arun methods if not a standard @tool decorated function
            if hasattr(tool, "_orig_arun") and tool._orig_arun is not None:
                func = tool._orig_arun
                is_async = True
            else:
                func = tool._orig_run or tool._run
                is_async = False

        # Inspect signature to filter out unsupported kwargs (e.g. config or run_manager)
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
                "error": f"Database target '{target}' not supported. Choose from: {list(self._db_tools.keys())}"
            }
        
        from app.services.tool_payload_validator import normalize_tool_args
        normalized_params = normalize_tool_args(target, user_query, params)
        
        result_str = await self._run_tool_direct(tool, normalized_params)
        return {
            "success": True,
            "data": self._parse_json_safe(result_str)
        }

    async def _execute_api(self, target: str, params: Dict[str, Any], user_query: str = "") -> Dict[str, Any]:
        tool = self._api_tools.get(target)
        if not tool:
            return {
                "success": False,
                "error": f"API target '{target}' not supported. Choose from: {list(self._api_tools.keys())}"
            }
        
        from app.services.tool_payload_validator import normalize_tool_args
        normalized_params = normalize_tool_args(target, user_query, params)
        
        result_str = await self._run_tool_direct(tool, normalized_params)
        return {
            "success": True,
            "data": self._parse_json_safe(result_str)
        }

    async def _execute_document(self, target: str, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query", target or "")
        limit = params.get("limit", 3)
        
        # Search inside ask-ai/docs folder (dynamic path check)
        possible_dirs = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs")), # e.g., ask-ai/docs
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs")),      # e.g., nanosoft-ai-backend/docs
            os.path.abspath(os.path.join(os.getcwd(), "docs")),                                # fallback to cwd/docs
            os.path.abspath(os.path.join(os.getcwd(), "..", "docs"))                           # fallback to cwd/../docs
        ]
        docs_dir = None
        for d in possible_dirs:
            if os.path.exists(d) and os.path.isdir(d):
                docs_dir = d
                break

        if not docs_dir:
            return {
                "success": False,
                "error": f"Docs directory not found. Searched paths: {possible_dirs}"
            }
            
        # Tokenize user query to compute relevance matches
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
                                    score += 15  # Boost filename matches
                                if kw in content_lower:
                                    score += content_lower.count(kw)
                                    
                        scored_files.append((score, file, content))
                    except Exception as e:
                        logger.warning(f"Error reading doc file {file}: {e}")
                        
        if not scored_files:
            return {
                "success": True,
                "data": []
            }
            
        # Sort files by relevance score descending
        if keywords:
            scored_files.sort(key=lambda x: x[0], reverse=True)
            
        # Load contents of top 3 most relevant documents to respect token budget
        docs_content = []
        for score, file, content in scored_files[:3]:
            docs_content.append(f"--- START FILE: {file} ---\n{content}\n--- END FILE: {file} ---")

            
        try:
            from langchain_core.messages import HumanMessage
            docs_joined = "\n\n".join(docs_content)
            prompt = f"""
You are an advanced document search assistant.
Your task is to search through the provided documents and find sections/snippets relevant to the user query.

User Query: {query}

Provided Documents:
{docs_joined}

You must return a JSON list of matches. Each match must contain:
- "file_name": the name of the file
- "snippet": a concise snippet from the file containing the relevant information
- "line_no": the approximate 1-indexed line number in the original file
- "score": relevance score from 1 to 10 (higher is more relevant)

Output ONLY a raw JSON array of objects, with no markdown code blocks, backticks, or conversational text.
Example structure:
[
  {{
    "file_name": "example.md",
    "snippet": "...",
    "line_no": 42,
    "score": 8
  }}
]
"""
            response = await self.model.ainvoke([HumanMessage(content=prompt)])
            raw_content = response.content.strip()
            
            # Clean up markdown code block wrapping if present
            if raw_content.startswith("```"):
                raw_content = raw_content.split("```")[1]
                if raw_content.startswith("json"):
                    raw_content = raw_content[4:]
            raw_content = raw_content.strip()
            
            results = json.loads(raw_content)
            if not isinstance(results, list):
                results = [results]
                
            # Sort by score descending
            results.sort(key=lambda x: x.get("score", 0), reverse=True)
            return {
                "success": True,
                "data": results[:limit]
            }
        except Exception as e:
            logger.error(f"LLM document search failed: {e}")
            return {
                "success": False,
                "error": f"Document search failed: {e}"
            }

    async def _execute_web_search(self, target: str, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query", target or "")
        limit = params.get("limit", 5)

        logger.info(f"🌐 Fetching DuckDuckGo Lite search results for: '{query}'")
        
        # 1. Fetch search results from lite.duckduckgo.com using POST to bypass bot detection
        url = "https://lite.duckduckgo.com/lite/"
        data = urllib.parse.urlencode({"q": query}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Origin": "https://lite.duckduckgo.com",
                "Referer": "https://lite.duckduckgo.com/"
            }
        )
        try:
            # Wrap standard urlopen in asyncio executor to avoid blocking the loop
            def fetch():
                with urllib.request.urlopen(req, timeout=8) as response:
                    return response.read().decode("utf-8")
                    
            html = await asyncio.get_event_loop().run_in_executor(None, fetch)
            
            # Robust standard HTMLParser to extract results
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
                            "snippet": ""
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
                            # Clean up characters
                            self.current_result["title"] = self.current_result["title"].replace("\u00a0", " ")
                            self.current_result["snippet"] = self.current_result["snippet"].replace("\u00a0", " ")
                            self.results.append(self.current_result)
                            self.current_result = None

            parser = DDGHTMLParser()
            parser.feed(html)
            results = parser.results[:limit]
                    
            if results:
                return {
                    "success": True,
                    "source": "duckduckgo_lite",
                    "data": results
                }
        except Exception as e:
            logger.error(f"DuckDuckGo Lite search scrape failed: {e}")
            return {
                "success": False,
                "error": f"Web search scrape failed: {e}"
            }

        return {
            "success": False,
            "error": "No search results returned from DuckDuckGo Lite."
        }

    def _parse_json_safe(self, text: str) -> Any:
        try:
            return json.loads(text)
        except Exception:
            return text

# Export a single global instance
retrieval_agent = RetrievalAgent()


# LangGraph Node Integration Helper
async def retrieval_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph Node wrapper for RetrievalAgent.
    Expects state to contain:
    - 'retrieval_plan': List[Dict[str, Any]] (generated by Goalplanning Agent)
    - 'user_name': str
    - 'session_id': Optional[str]
    
    Returns updated state dict with 'retrieval_results'.
    """
    plan = state.get("retrieval_plan", [])
    user_name = state.get("user_name", "system")
    session_id = state.get("session_id")
    user_query = state.get("user_query", "")
    
    # Execute the plan across the dynamically patched tools/channels
    results = await retrieval_agent.execute_plan(
        plan=plan,
        user_name=user_name,
        session_id=session_id,
        user_query=user_query
    )
    
    return {
        "retrieval_results": results
    }
