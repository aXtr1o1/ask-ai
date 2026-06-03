"""
LangChain Service — AI model with tool support.

This file contains only the LangChainService class.
All stateless helper functions and regex constants live in langchain_helpers.py.
"""
import logging
import re as _re
import json

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

from app.config import settings
from app.tools.facility_tools import ASSETS, PPM, BDM, FA, SB
from app.services.langchain_tool_paths import LangChainToolPathsMixin
from app.services.langchain_response_builder import LangChainResponseBuilderMixin
from app.services.quota_service import quota_fallback_service
from app.services.keyword_match_context import (
    append_match_explanation,
    extract_from_tool_response,
    format_keyword_count_reply,
    search_context_prompt_block,
)
from app.services.tool_payload_validator import normalize_tool_args
from app.services.query_classifier import needs_facility_tools

# ── Import all helpers from the companion module ──────────────────────────────
# Re-exported at module level so existing callers (tests, main.py) keep working:
#   from app.services.langchain_service import _complaint_query_is_clear  ← still works
from app.services.langchain_helpers import (
    _strip_redundant_table_offer,
    extract_date_from_query,
    _extract_prev_keyword,
    _extract_established_tool_context,
    _is_after_clarification,
    _complaint_query_is_clear,
    _query_wants_list_display,
    _infer_intent_from_query,
    _append_explicit_today,
    _enrich_entity_from_args,
    _RE_TABLE_OFFER_PHRASE,
    _RE_PREV_KEYWORD,
    _RE_ESTAB_FA,
    _RE_ESTAB_BDM,
    _RE_ESTAB_PPM,
    _RE_ESTAB_SB,
    _RE_ESTAB_ASSETS,
)

logger = logging.getLogger("langchain_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


class LangChainService(LangChainToolPathsMixin, LangChainResponseBuilderMixin):
    def __init__(self):
        try:
            _base_model = ChatGoogleGenerativeAI(
                model=settings.GOOGLE_AI_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.0
            )
            # Model WITH tools — for facility data queries
            self.model = _base_model.bind_tools([ASSETS, PPM, BDM, FA, SB])
            # Model WITHOUT tools — for conversational / general queries
            self.plain_model = _base_model

            self.tool_map = {
                "ASSETS": ASSETS,
                "PPM":    PPM,
                "BDM":    BDM,
                "FA":     FA,
                "SB":     SB,
            }
            self._last_search_context = None
            # Stores the last successful tool payload per tool (filter fields only).
            # Used to carry over filters for follow-up queries (e.g. 'among them...').
            # Keyed by tool name so ASSETS history never bleeds into PPM/BDM/FA/SB.
            self._last_tool_payload: dict = {}  # {tool_name: {field: value}}
            # Tracks the SINGLE most recently called tool — used to redirect
            # follow-up queries ("give me 8 among them") to the correct tool.
            self._last_used_tool: str | None = None
            logger.info("🚀 LangChainService initialized with ASSETS, PPM, BDM, FA, SB tools")
        except Exception as e:
            logger.error(f"❌ LangChainService init failed: {e}", exc_info=True)
            raise

    # ── Accumulate tokens from each model call ───────────────────────────────
    # ── Called after every model.invoke() to add up tokens for this query
    def _accumulate_tokens(self, ai_response):
        if hasattr(ai_response, 'usage_metadata') and ai_response.usage_metadata:
            self._total_input_tokens  += ai_response.usage_metadata.get('input_tokens')  or 0
            self._total_output_tokens += ai_response.usage_metadata.get('output_tokens') or 0
            self._total_tokens        += ai_response.usage_metadata.get('total_tokens')  or 0

    # ── Print ONE clean summary line at end of every query ──────────────────
    def _log_query_summary(self, user_query: str):
        
        logger.info(
            f"📊 QUERY TOKEN SUMMARY | query='{user_query}' "
            f"| input_tokens={self._total_input_tokens} "
            f"| output_tokens={self._total_output_tokens} "
            f"| total_tokens={self._total_tokens}"
        )

    @staticmethod
    def _entity_label_from_tool(tool_name: str) -> str:
        t = (tool_name or "").upper()
        if "ASSET" in t:
            return "assets"
        if "PPM" in t:
            return "PPM work orders"
        if "BDM" in t:
            return "BDM complaints"
        if "FA" in t:
            return "FA complaints"
        if "SB" in t:
            return "SB work orders"
        return "records"

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

    def extract_chunk_text(self, chunk) -> str: # later purpose for the streaming purpose
        content = chunk.content
        if not content:
            return ""
        if isinstance(content, list):
            return content[0].get("text", "") if content else ""
        if isinstance(content, str):
            return content
        return str(content)
    # for displaying the graph purpose. 


    # ──  return type is now tuple[str, str, list] used for the chat memory and the db memory .
    # ── (final_response_text, context_summary, messages)
    # ── context_summary = short sentence for ALL query types → used by main.py for lc_memory
    # ── final_response_text = full data response → used by main.py for history (DB)


    async def process_query(self, messages: list, user_name: str = None, user_id: str = None, session_id: str = None, is_graph: bool = False, is_after_clarification: bool = False, is_all_datasets: bool = False) -> tuple[str, str, list]:
        try:
            
            # user_name is always from the frontend request; use it for all tool calls
            
            if not user_name:
                raise ValueError("user_name is required (from frontend request)")
            logger.info(f"💬 Processing query for user_name: {user_name} | user_id: {user_id}")

            # ── Reset token counters for this query ──────────────────────────
            self._total_input_tokens  = 0
            self._total_output_tokens = 0
            self._total_tokens        = 0
            
            # ── Get current user query for summary log ───────────────────────
            current_user_query = ""
            for m in reversed(messages):
                if isinstance(m, HumanMessage):
                    current_user_query = (m.content or "") if isinstance(m.content, str) else ""
                    break

            # ── AMBIGUITY PRE-CHECK (runs before model, before lc_memory influence) ──
            _q = current_user_query.lower()

            # ── STEP 0: Extract previous assistant context for follow-up detection ──
            # (Needed here so needs_facility_tools can evaluate follow-up pronouns)
            _prev_assistant_for_clf = ""
            for _m in reversed(messages):
                from langchain_core.messages import AIMessage as _AIMsg2
                if isinstance(_m, _AIMsg2):
                    _prev_assistant_for_clf = (_m.content or "") if isinstance(_m.content, str) else ""
                    break

            # ── STEP 1: Conversational shortcut — bypass ambiguity gate entirely ──
            # If the query has NO facility signal at all (greetings, general questions,
            # "show me how AI works", "how many people are in the team"), skip straight
            # past the ambiguity check so we never show a false clarification prompt.
            _is_facility_query = needs_facility_tools(current_user_query, _prev_assistant_for_clf)
            if not _is_facility_query:
                logger.info("🗣️ [AmbiguityGate] Non-facility query — skipping ambiguity check | query='%s'", current_user_query[:80])
            else:
                # ── STEP 2: Generic table ambiguity check ─────────────────────────
                # Narrow trigger: bare action verbs (show/list/find/get…) alone are NOT
                # enough — they must appear with a data noun, OR the query explicitly
                # mentions the ambiguous terms "complaints" / "work orders".
                # This prevents "show me how AI works" → false clarification.
                _generic_db_query = bool(_re.search(
                    # Action verb + data noun together → ambiguous
                    r'\b(show|list|how\s+many|count|total|get|search|find|view|fetch)\b'
                    r'[^.!?]{0,60}'
                    r'\b(records?|data|results?|reports?|entry|entries|items?)\b'
                    r'|\bcomplaints?\b'               # always ambiguous: FA or BDM?
                    # ── Work-order variants (including common typos) ──────────
                    r'|\bwork[\s\-]?orders?\b'        # work order, work-order, workorder
                    r'|\bworko[rd]ers?\b'             # workoders, workoers (typos)
                    r'|\bscheduled\s+work\b',         # always ambiguous: PPM or SB?
                    _q,
                ))

                _has_table_keyword = bool(_re.search(
                    r"\b(asset|assets|equipment|equipments|device|devices|ppm|sb|preventive|schedule[\s\-]based"
                    r"|fa|facility\s+audit|audit|bdm|breakdown|breakdowns)\b",
                    _q,
                ))
                # Also clear if: last AI message was a clarification OR caller explicitly flagged
                # this as a reply to a clarification.
                # IMPORTANT — established context alone is NOT enough to clear the gate.
                # It only clears when the current query also has a follow-up pronoun
                # (them/those/these/the ones/…), meaning the user is genuinely continuing
                # the previous data conversation.
                # Without this guard, a fresh generic query like "how many data we have"
                # would bypass clarification just because ASSETS was used turns ago.
                _established_ctx = _extract_established_tool_context(messages)
                _has_followup_pronoun = bool(_re.search(
                    r"\b(them|those|these|it\b|the\s+ones|of\s+them|among\s+them|"
                    r"from\s+those|from\s+them|the\s+above|same\s+ones|"
                    r"what\s+about|how\s+about|in\s+that|for\s+that|from\s+that|"
                    r"show\s+me\s+(more|them|those)|give\s+me\s+(more|them|those))\b",
                    _q,
                    _re.IGNORECASE,
                ))
                # Established context only clears IF a follow-up pronoun is also present
                _ctx_clears = (_established_ctx is not None) and _has_followup_pronoun
                _table_clear = _has_table_keyword or is_after_clarification or _is_after_clarification(messages) or _ctx_clears
                if is_after_clarification:
                    logger.info("✅ Clarification bypass active — skipping ambiguity pre-check | query='%s'", current_user_query[:80])

                if _generic_db_query and not _table_clear:
                    logger.info("🔀 Generic query without dataset intercepted | query='%s'", current_user_query)
                    clarification = (
                        "Please clarify which kind of data you want to search?\n"
                        "Assets, PPM, BDM, FA, or SB."
                    )
                    return clarification, clarification, messages

            # Sub-clarifications for FA-vs-BDM complaints and PPM-vs-SB work orders are
            # intentionally removed. The single general clarification above handles all
            # ambiguous queries uniformly — users select from Assets/PPM/BDM/FA/SB.


            # ── QUERY REWRITING STEP REMOVED ──
            # The original user query is passed directly to the model.
            logger.info(f"💬 Direct Query (No Rewriter): '{current_user_query}'")

            # ── PRE-CLASSIFICATION: decide which model to invoke ──────────────
            # Extract the last assistant response as context for follow-up detection
            _prev_assistant = ""
            for m in reversed(messages):
                from langchain_core.messages import AIMessage as _AIMsg
                if isinstance(m, _AIMsg):
                    _prev_assistant = (m.content or "") if isinstance(m.content, str) else ""
                    break

            # ── CLARIFICATION OVERRIDE INJECTION ─────────────────────────────
            # When the user replied to a clarification (e.g. "sb" after being asked
            # which dataset), inject a strong SystemMessage that forces the model
            # to call the correct tool immediately — bypassing its own clarification
            # rules from the system prompt.
            if is_after_clarification:
                _dataset_map = {
                    "assets": ("ASSETS", "Assets"),
                    "asset":  ("ASSETS", "Assets"),
                    "ppm":    ("PPM",    "PPM (Preventive Maintenance)"),
                    "bdm":    ("BDM",    "BDM (Breakdown Maintenance)"),
                    "fa":     ("FA",     "FA (Facility Audit)"),
                    "sb":     ("SB",     "SB (Schedule Based)"),
                }
                _chosen_tool = None
                _chosen_label = None

                if is_all_datasets:
                    # ── ALL DATASETS: user replied "all" or "many" ──────────────────────
                    # Strip the "all: " prefix to recover the original question
                    _actual_q = _re.sub(r"^\s*all\s*[:\s]+", "", current_user_query, flags=_re.IGNORECASE).strip()
                    if not _actual_q:
                        _actual_q = current_user_query
                    _override_msg = SystemMessage(content=(
                        f"OVERRIDE: The user was asked to clarify which dataset to search. "
                        f"They replied 'all' — meaning they want data from EVERY dataset. "
                        f"You MUST call ALL 5 tools simultaneously right now: ASSETS, PPM, BDM, FA, and SB. "
                        f"Apply the same query logic to each tool to answer: '{_actual_q}'. "
                        f"Do NOT ask for clarification. Do NOT skip any tool. Call all 5 tools now."
                    ))
                    messages = [_override_msg] + list(messages)
                    logger.info(
                        "🌐 All-datasets override injected | actual_q='%s'",
                        _actual_q[:80],
                    )
                else:
                    # ── SINGLE DATASET: user replied with a specific tool name ───────────
                    # Check the original user reply (first word(s) before any colon or space)
                    _reply_lower = current_user_query.lower()
                    for _kw, (_tool_name, _label) in _dataset_map.items():
                        if _re.search(rf"\b{_re.escape(_kw)}\b", _reply_lower):
                            _chosen_tool = _tool_name
                            _chosen_label = _label
                            break

                    if _chosen_tool:
                        # Extract the actual question part (strip dataset prefix if present)
                        _actual_q = _re.sub(rf"^\s*{_re.escape(_chosen_tool.lower())}\s*[:\s]+", "", _reply_lower, flags=_re.IGNORECASE).strip()
                        if not _actual_q:
                            _actual_q = current_user_query
                        _override_msg = SystemMessage(content=(
                            f"OVERRIDE: The user was asked to clarify which dataset to search. "
                            f"They have now chosen: {_chosen_label}. "
                            f"You MUST call the {_chosen_tool} tool immediately to answer: '{_actual_q}'. "
                            f"Do NOT ask for clarification again. Do NOT explain anything. Just call the {_chosen_tool} tool now."
                        ))
                        messages = [_override_msg] + list(messages)
                        logger.info(
                            "💉 Clarification override injected | chosen_tool=%s | actual_q='%s'",
                            _chosen_tool, _actual_q[:80],
                        )

            _use_tools = needs_facility_tools(current_user_query, _prev_assistant)
            # When clarification was just resolved, always use tools
            if is_after_clarification:
                _use_tools = True
            logger.info(
                "🔀 QueryClassifier | use_tools=%s | query='%s'",
                _use_tools, current_user_query[:80]
            )

            # ── ALL-DATASETS SHORTCUT ─────────────────────────────────────────────
            # When user replied "all" / "every" / etc. after the general clarification,
            # bypass the first model call entirely (the model keeps looping on clarification
            # because of lc_memory context). Instead, directly build the 5 tool calls and
            # skip straight to multi-tool execution. The model is still used to summarize.
            if is_all_datasets and is_after_clarification:
                _actual_q_all = _re.sub(r"^\s*all\s*[:\s]+", "", current_user_query, flags=_re.IGNORECASE).strip() or current_user_query
                logger.info("🌐 All-datasets DIRECT EXECUTION — bypassing model decision | actual_q='%s'", _actual_q_all[:80])
                _ALL_TOOLS = ["ASSETS", "PPM", "BDM", "FA", "SB"]
                _direct_tool_calls = [
                    {
                        "name": tool_name,
                        "id": f"direct_all_{tool_name.lower()}",
                        "args": {"user_name": user_name, "user_id": str(user_id or ""), "offset": 0, "is_aggregate": False},
                        "type": "tool_call",
                    }
                    for tool_name in _ALL_TOOLS
                ]
                # Build a synthetic AIMessage that looks like the model chose all 5 tools
                from langchain_core.messages import AIMessage as _AIMsg
                ai_msg = _AIMsg(content="", tool_calls=_direct_tool_calls)
                messages.append(ai_msg)
                logger.info("🛠 Tool calls (direct): %s", _ALL_TOOLS)
                # Fall through to the multi-tool execution block below (ai_msg.tool_calls is set)

            elif not _use_tools:
                # Conversational query — invoke plain model (no tools available)
                ai_msg = self.plain_model.invoke(messages)
                self._accumulate_tokens(ai_msg)
                logger.info("🤖 First model call (no tools) | conversational")
                conv_text = _strip_redundant_table_offer(self._get_content_str(ai_msg))
                self._log_query_summary(current_user_query)
                return conv_text, conv_text, messages

            else:
                # CALL 1 — Normal first model call (model decides which tool(s) to use)
                # ── AMBIGUITY GUARD: prevent LLM from calling all 5 tools as a fallback ──
                # When the model cannot determine a single specific tool from the user query,
                # it MUST respond with a plain-text clarification — never call multiple tools.
                _ambiguity_guard = SystemMessage(content=(
                    "IMPORTANT ROUTING RULE: You have 5 tools — ASSETS, PPM, BDM, FA, SB. "
                    "Each tool serves a DISTINCT dataset. "
                    "If the user's query does NOT clearly identify ONE specific dataset, "
                    "do NOT call multiple tools as a fallback. "
                    "Instead, respond with a plain text message asking the user to specify "
                    "which dataset they want: Assets, PPM, BDM, FA, or SB. "
                    "Only call ALL tools simultaneously when the user explicitly says "
                    "'all', 'every dataset', 'all modules', or similar all-inclusive intent."
                ))
                _guarded_messages = [_ambiguity_guard] + list(messages)
                ai_msg = self.model.invoke(_guarded_messages)
                self._accumulate_tokens(ai_msg)
                logger.info("🤖 First model call | tool_calls=%s", bool(ai_msg.tool_calls))

            if ai_msg.tool_calls:

                logger.info(f"🛠 Tool calls: {[tc['name'] for tc in ai_msg.tool_calls]}")
                
                # If there are keywords in the tool call arguments, log them separately
                keywords = [
                    tc.get("args", {}).get("keyword")
                    for tc in ai_msg.tool_calls
                    if tc.get("args") and tc["args"].get("keyword")
                ]
                if keywords:
                    logger.info("🔑 Search Keywords: %s", keywords)

                # Deduplicate tool calls with identical names and arguments (case-insensitive for string arguments)
                unique_tool_calls = []
                seen_keys = set()
                for tc in ai_msg.tool_calls:
                    tc_args = tc.get("args") or {}
                    # Normalize string values for comparison (strip & lowercase)
                    norm_args = {}
                    for k, v in tc_args.items():
                        if isinstance(v, str):
                            norm_args[k] = v.strip().lower()
                        elif isinstance(v, list):
                            norm_args[k] = [x.strip().lower() if isinstance(x, str) else x for x in v]
                        else:
                            norm_args[k] = v
                    
                    call_key = (tc["name"], json.dumps(norm_args, sort_keys=True))
                    if call_key not in seen_keys:
                        seen_keys.add(call_key)
                        unique_tool_calls.append(tc)
                    else:
                        logger.info("♻️ Discarding duplicate tool call: %s with args %s", tc["name"], tc_args)
                ai_msg.tool_calls = unique_tool_calls

                messages.append(ai_msg)



                if len(ai_msg.tool_calls) > 1:
                    return await self._handle_multi_tool_path(ai_msg, messages, user_name, str(user_id or ''), current_user_query)
                else:
                    return await self._handle_single_tool_path(ai_msg, messages, user_name, str(user_id or ''), current_user_query, is_graph)
            else:
                # Model skipped tool — direct response.
                # BUT: if this is a follow-up pronoun query ("give me 9 of them",
                # "give me 10 among them") and we have a stored payload,
                # force-invoke the most recent tool instead of going conversational.
                from app.services.query_classifier import _FOLLOWUP_PRONOUNS as _FUP_RE2
                _user_q2 = ""
                for _m2 in reversed(messages):
                    if isinstance(_m2, HumanMessage):
                        _user_q2 = (_m2.content or "") if isinstance(_m2.content, str) else ""
                        break

                _is_fup2 = bool(_FUP_RE2.search(_user_q2))
                # Extract requested count from "give me 9 of them" / "show 5 of them"
                import re as _re2
                _limit_match = _re2.search(r'\b(\d+)\b', _user_q2)
                _requested_limit = int(_limit_match.group(1)) if _limit_match else None

                # Find the most recently used tool (last key in _last_tool_payload)
                _redirect_tool2 = None
                _redirect_payload2 = {}
                if _is_fup2 and _requested_limit and self._last_tool_payload:
                    # Use the tool that was most recently saved
                    for _t2, _p2 in reversed(list(self._last_tool_payload.items())):
                        if _p2:
                            _redirect_tool2 = _t2
                            _redirect_payload2 = _p2
                            break

                if _redirect_tool2 and _redirect_tool2 in self.tool_map:
                    logger.info(
                        "🔀 Follow-up force-invoke | model skipped tools | redirecting to %s "
                        "with payload=%s + limit=%s | query='%s'",
                        _redirect_tool2, _redirect_payload2, _requested_limit, _user_q2[:70],
                    )
                    _fup_args: dict = {
                        "user_name": user_name,
                        "user_id": str(user_id) if user_id is not None else None,
                        "limit": _requested_limit,
                        "offset": 0,
                        "is_aggregate": False,
                    }
                    # Inject stored filters
                    for _fk, _fv in _redirect_payload2.items():
                        if _fk not in ("user_name", "user_id", "offset", "limit", "is_aggregate"):
                            _fup_args[_fk] = _fv

                    try:
                        _fup_args = normalize_tool_args(_redirect_tool2, _user_q2, _fup_args)
                        _fup_result = self.tool_map[_redirect_tool2].invoke(dict(_fup_args))
                        _fup_parsed = json.loads(_fup_result) if isinstance(_fup_result, str) else _fup_result
                        _fup_p_list = _fup_parsed.get("p_list", []) if isinstance(_fup_parsed, dict) else []
                        _fup_p_count = _fup_parsed.get("p_count", len(_fup_p_list)) if isinstance(_fup_parsed, dict) else len(_fup_p_list)

                        # Build response the same way the normal single-tool list path does
                        _fup_entity = self._entity_label_from_tool(_redirect_tool2)
                        _fup_context_summary = (
                            f"I've retrieved {len(_fup_p_list)} {_fup_entity} records for you."
                        )
                        _fup_response = json.dumps({
                            "type": "large_dataset",
                            "context_summary": _fup_context_summary,
                            "records": _fup_p_list,
                        })
                        self._last_tool_payload[_redirect_tool2] = {
                            k: v for k, v in _fup_args.items()
                            if k not in ("user_name", "user_id", "offset", "limit", "is_aggregate") and v is not None
                        }
                        self._last_used_tool = _redirect_tool2  # Keep tracking most recent tool

                        self._log_query_summary(current_user_query)
                        return _fup_response, _fup_context_summary, messages
                    except Exception as _fup_err:
                        logger.error("❌ Follow-up force-invoke failed: %s", _fup_err)
                        # Fall through to conversational response below

                # Normal no-tool path
                logger.info("✅ No tool call — direct response")
                content = self._get_content_str(ai_msg)
                if not content or str(content).strip() == "":
                    content = "No matching records were found for the requested data."
                self._log_query_summary(current_user_query)
                return content, content, messages


        except Exception as e:
            logger.error(f"❌ Query processing error: {e}", exc_info=True)
            raise

langchain_service = LangChainService()