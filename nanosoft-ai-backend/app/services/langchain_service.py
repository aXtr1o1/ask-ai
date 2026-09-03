"""
LangChain Service — Normal ASK-AI orchestration.

Pipeline for every query:
  1. Understanding Agent (Advance folder, reused directly) classifies intent
     and, for db_query, which module(s) are relevant.
  2. Level check — Normal ASK-AI only serves Level 1 (Information Retrieval).
     Anything else is redirected to Advanced ASK-AI.
  3. Per selected module: real metadata + enum values (Advance folder registries)
     are given to a small model call that decides the filter values, the
     aggregate/group-by decision, and whether the user wants a count, a list,
     or a graph.
  4. The filter values are remapped from DB column names to the tool argument
     names (via Advance's retrieval mappings) and the matching module function
     is called directly.
  5. The result is rendered — count / table / large dataset / graph — reusing
     the existing display-length threshold.

Chat history: every turn is written into Advance's own conversation_memory
singleton (Understanding_Agent/conversation_memory.py), keyed by Normal's own
session_id. classify_query() already reads that same store internally, so
this is what gives it real follow-up context — no changes to Advance's code,
and no separate history store to keep in sync. Normal and Advance never share
a session_id, so their histories never mix despite using the same store.

Rendering logic (thresholds, large-dataset/graph responses) lives in
LangChainToolPathsMixin. Prompt text for the final summary lives in
LangChainResponseBuilderMixin.
"""
import logging
import re as _re
import json
import inspect

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from app.config import settings
from app.tools.facility_tools import ASSETS, PPM, BDM, FA, SB, CONTRACT, EMPLOYEE
from app.services.langchain_tool_paths import LangChainToolPathsMixin
from app.services.langchain_response_builder import LangChainResponseBuilderMixin
from app.prompts.system_prompt import get_level_check_prompt, get_payload_prompt
from app.api.advance.Understanding_Agent.agent import classify_query
from app.api.advance.Understanding_Agent.conversation_memory import conversation_memory
from app.api.advance.analysis.metadata import get_metadata
from app.api.advance.analysis.metadata.enum_values import get_enum_block
from app.api.advance.retrieval.mappings import ALL_MAPPINGS

logger = logging.getLogger("langchain_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)

# ── Module name (Advance's registries) -> callable that builds the payload
# and calls the matching app/api/routes/*.py function directly. ────────────
MODULE_TOOL_MAP = {
    "assets":    ASSETS,
    "ppm":       PPM,
    "bdm":       BDM,
    "fa":        FA,
    "sb":        SB,
    "contracts": CONTRACT,
    "employees": EMPLOYEE,
}

MODULE_FRIENDLY_NAMES = {
    "assets":    "Assets",
    "ppm":       "PPM Work Orders",
    "bdm":       "BDM Complaints",
    "fa":        "Facility Audit Complaints",
    "sb":        "Schedule Based Work Orders",
    "contracts": "Contracts",
    "employees": "Employees",
}

# ── Reply keywords for the "which dataset?" clarification prompt ──────────
_DATASET_REPLY_MAP = {
    "assets":    "assets",
    "asset":     "assets",
    "ppm":       "ppm",
    "bdm":       "bdm",
    "fa":        "fa",
    "sb":        "sb",
}


def _parse_json_response(text: str) -> dict:
    """Parse a model's JSON reply, tolerating markdown code fences."""
    if not text:
        return {}
    cleaned = _re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=_re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        logger.warning("⚠️ Could not parse JSON from model response: %s", text[:200])
        return {}


def _map_filters_to_tool_args(module: str, filters: dict) -> dict:
    """Remap DB column names (PascalCase, from Advance's metadata) to the
    snake_case argument names the module functions expect."""
    str_map, bool_map, num_map = ALL_MAPPINGS.get(module, ({}, {}, {}))
    combined = {**str_map, **bool_map, **num_map}
    return {combined.get(key, key): value for key, value in (filters or {}).items()}


class LangChainService(LangChainToolPathsMixin, LangChainResponseBuilderMixin):
    def __init__(self):
        try:
            self.model = ChatGoogleGenerativeAI(
                model=settings.GOOGLE_AI_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.0,
            )
            self._last_search_context = None
            # Stashed for chat_websocket_handler's yes/no "view as table" follow-up flow.
            self._last_pending_table = None
            logger.info("LangChainService initialized (modules: %s)", ", ".join(MODULE_TOOL_MAP))
        except Exception as e:
            logger.error(f"❌ LangChainService init failed: {e}", exc_info=True)
            raise

    def _accumulate_tokens(self, ai_response):
        if hasattr(ai_response, 'usage_metadata') and ai_response.usage_metadata:
            self._total_input_tokens  += ai_response.usage_metadata.get('input_tokens')  or 0
            self._total_output_tokens += ai_response.usage_metadata.get('output_tokens') or 0
            self._total_tokens        += ai_response.usage_metadata.get('total_tokens')  or 0

    def _log_query_summary(self, user_query: str):
        logger.info(
            f"📊 QUERY TOKEN SUMMARY | query='{user_query}' "
            f"| input_tokens={self._total_input_tokens} "
            f"| output_tokens={self._total_output_tokens} "
            f"| total_tokens={self._total_tokens}"
        )

    def _get_content_str(self, msg) -> str:
        if not msg:
            return ""
        content = getattr(msg, "content", msg)
        if not content:
            return ""
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
                else:
                    parts.append(str(item))
            return " ".join(parts)
        if isinstance(content, str):
            return content
        return str(content)

    def _resolve_clarification_reply(self, current_user_query: str, is_all_datasets: bool) -> tuple[bool, list, str]:
        """
        The user just replied to the 'which dataset?' clarification prompt.
        Recover the chosen module(s) and the actual question directly from
        their reply rather than re-classifying it with the Understanding
        Agent, since that reply alone ('sb', 'all') carries no signal on its own.
        """
        if is_all_datasets:
            actual_q = _re.sub(r"^\s*all\s*[:\s]+", "", current_user_query, flags=_re.IGNORECASE).strip()
            return True, ["assets", "ppm", "bdm", "fa", "sb"], (actual_q or current_user_query)

        reply_lower = current_user_query.lower()
        for keyword, module in _DATASET_REPLY_MAP.items():
            if _re.search(rf"\b{_re.escape(keyword)}\b", reply_lower):
                actual_q = _re.sub(rf"^\s*{_re.escape(keyword)}\s*[:\s]+", "", reply_lower, flags=_re.IGNORECASE).strip()
                return True, [module], (actual_q or current_user_query)

        return False, [], current_user_query

    def _check_level(self, query_summary: str) -> int:
        """Level 1 (Information Retrieval) is the only level Normal ASK-AI serves."""
        ai_msg = self.model.invoke([HumanMessage(content=get_level_check_prompt(query_summary))])
        self._accumulate_tokens(ai_msg)
        data = _parse_json_response(self._get_content_str(ai_msg))
        try:
            level = int(data.get("level", 1))
        except (TypeError, ValueError):
            level = 1
        return level if level in (1, 2, 3, 4, 5) else 1

    def _run_module(self, module: str, query_summary: str, user_name: str, user_id) -> dict:
        """Generate the filter/aggregate payload for one module and call it."""
        schema = get_metadata([module]).get(module, {})
        metadata_block = "\n".join(f"  {col}: {desc}" for col, desc in schema.items()) or "  (no fields registered)"
        enum_block = get_enum_block([module])

        prompt = get_payload_prompt(query_summary, module, metadata_block, enum_block)
        ai_msg = self.model.invoke([HumanMessage(content=prompt)])
        self._accumulate_tokens(ai_msg)
        agent_out = _parse_json_response(self._get_content_str(ai_msg))

        is_aggregate = bool(agent_out.get("is_aggregate"))
        group_by_columns = agent_out.get("group_by_columns") or None
        aggregate_function = agent_out.get("aggregate_function") if is_aggregate else None
        limit = agent_out.get("limit")
        limit = int(limit) if isinstance(limit, (int, float)) else None
        response_type = agent_out.get("response_type")
        if response_type not in ("list", "count", "graph"):
            response_type = "list"

        payload = _map_filters_to_tool_args(module, agent_out.get("filters") or {})
        payload.update({
            "user_name": user_name,
            "user_id": user_id,
            "limit": limit,
            "offset": 0,
            "is_aggregate": is_aggregate,
            "group_by_columns": group_by_columns,
            "aggregate_function": aggregate_function,
        })

        tool_fn = MODULE_TOOL_MAP[module]
        # Drop any key the model produced that this module's function doesn't accept,
        # instead of crashing on an unexpected keyword argument.
        valid_params = set(inspect.signature(tool_fn).parameters.keys())
        dropped = set(payload) - valid_params
        if dropped:
            logger.warning("⚠️ [%s] Dropping unmapped filter keys: %s", module.upper(), dropped)
        payload = {k: v for k, v in payload.items() if k in valid_params}

        logger.info("📋 [%s PAYLOAD]: %s", module.upper(), json.dumps(payload, default=str, ensure_ascii=False))

        try:
            raw_result = tool_fn(**payload)
            parsed = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
        except Exception as e:
            logger.error("❌ Module call failed for %s: %s", module, e, exc_info=True)
            parsed = {"p_list": [], "p_count": 0}

        if isinstance(parsed, dict):
            p_list = parsed.get("p_list", [])
            p_count = parsed.get("p_count", len(p_list))
        else:
            p_list = parsed if isinstance(parsed, list) else []
            p_count = len(p_list)
        display_count = int(p_count) if isinstance(p_count, (int, float)) and p_count >= 0 else len(p_list)

        return {
            "module": module,
            "friendly_name": MODULE_FRIENDLY_NAMES.get(module, module.title()),
            "p_list": p_list,
            "display_count": display_count,
            "is_aggregate": is_aggregate,
            "response_type": response_type,
            "filters": agent_out.get("filters") or {},
        }

    async def process_query(self, messages: list, user_name: str = None, user_id: str = None, session_id: str = None, is_graph: bool = False, is_after_clarification: bool = False, is_all_datasets: bool = False) -> tuple[str, str, list]:
        try:
            if not user_name:
                raise ValueError("user_name is required (from frontend request)")
            logger.info(f"💬 Processing query for user_name: {user_name} | user_id: {user_id}")

            self._total_input_tokens  = 0
            self._total_output_tokens = 0
            self._total_tokens        = 0
            self._last_pending_table  = None

            current_user_query = ""
            for m in reversed(messages):
                if isinstance(m, HumanMessage):
                    current_user_query = (m.content or "") if isinstance(m.content, str) else ""
                    break

            if not current_user_query:
                msg = "I didn't receive a question to answer."
                return msg, msg, messages

            resolved_from_reply, modules, query_summary = (False, [], current_user_query)
            if is_after_clarification:
                resolved_from_reply, modules, query_summary = self._resolve_clarification_reply(
                    current_user_query, is_all_datasets,
                )

            if not resolved_from_reply:
                # classify_query() reads its own conversation history internally via
                # conversation_memory.get_history(session_id) — writing Normal's turns
                # into that same store below (keyed by Normal's own session_id) is what
                # gives it real follow-up context, with no changes needed to Advance's code.
                result = classify_query(current_user_query, session_id)
                intent = result["intent"]

                if intent == "general":
                    text = result["general_response"] or "I'm here to help with facility data questions."
                    conversation_memory.add_turn(
                        session_id, current_user_query, result["query_summary"],
                        intent="general", general_response=text,
                    )
                    self._log_query_summary(current_user_query)
                    return text, text, messages

                if intent == "web_search":
                    text = result["web_search_summary"] or "I couldn't find anything relevant."
                    conversation_memory.add_turn(
                        session_id, current_user_query, result["query_summary"],
                        intent="web_search", general_response=text,
                    )
                    self._log_query_summary(current_user_query)
                    return text, text, messages

                query_summary = result["query_summary"]
                modules = [m for m in (result["modules"] or []) if m in MODULE_TOOL_MAP]

            if not modules:
                clarification = (
                    "Please clarify which kind of data you want to search?\n"
                    "Assets, PPM, BDM, FA, or SB."
                )
                conversation_memory.add_turn(
                    session_id, current_user_query, query_summary, intent="db_query", modules=[],
                )
                self._log_query_summary(current_user_query)
                return clarification, clarification, messages

            level = self._check_level(query_summary)
            logger.info("📶 Level check | level=%s | summary='%s'", level, query_summary[:80])
            if level != 1:
                redirect = (
                    "This question needs deeper analysis than Normal ASK-AI can provide. "
                    "Please switch to Advanced ASK-AI for this request."
                )
                conversation_memory.add_turn(
                    session_id, current_user_query, query_summary, intent="db_query", modules=modules,
                )
                self._log_query_summary(current_user_query)
                return redirect, redirect, messages

            module_results = [
                self._run_module(mod, query_summary, user_name, str(user_id) if user_id is not None else None)
                for mod in modules
            ]

            if len(module_results) == 1:
                final_content, context_summary = self._handle_single_module(module_results[0], query_summary, is_graph)
            else:
                final_content, context_summary = self._handle_multi_module(module_results, query_summary)

            conversation_memory.add_turn(
                session_id, current_user_query, query_summary, intent="db_query", modules=modules,
                filter_values={r["module"]: r["filters"] for r in module_results if r["filters"]},
            )
            self._log_query_summary(current_user_query)
            return final_content, context_summary, messages

        except Exception as e:
            logger.error(f"❌ Query processing error: {e}", exc_info=True)
            raise

langchain_service = LangChainService()
