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


class LangChainService:
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
    def build_graph_response(self,context_summary: str, records: list) -> str:
        
        # Auto-detect label_key (string/text column → X axis)
        # and value_key (numeric column → Y axis) from first record
        label_key = "label"
        value_key = "value"

        if records and isinstance(records[0], dict):
            keys = list(records[0].keys())
            for k in keys:
                val = records[0].get(k)
                if isinstance(val, (int, float)):
                    # numeric column → Y axis (bar height)
                    value_key = k
                else:
                    # string/text column → X axis (category labels)
                    label_key = k

        graph_response = {
            "type":            "graph",       # ← frontend checks this field
            "chart_type":      "bar",         # ← bar chart type
            "context_summary": context_summary,
            "label_key":       label_key,     # ← X axis column name
            "value_key":       value_key,     # ← Y axis column name
            "records":         records        # ← full grouped data for chart
        }

        logger.info(
            "📊 [GRAPH] Built graph response | label_key=%s | value_key=%s | records=%d",
            label_key, value_key, len(records)
        )

        return json.dumps(graph_response)
    def _build_final_prompt(
                self,
                is_count_query: bool,
                is_aggregate_query: bool,
                user_query: str,
                display_count: int,
                p_list_for_model: list,
                search_context: dict | None = None,
            ) -> str:
                """
                Build the prompt for final model call.
                - count  → one sentence answer, no table in text
                - aggregate/list → context/summary ONLY (UI shows tables when applicable)
                """
                if is_count_query:
                    match_hint = search_context_prompt_block(search_context)
                    return (
                        "Use the above tool results. Reply in one crisp, friendly sentence using total_count. "
                        "Do not render a table. "
                        "Do NOT ask if the user wants details, a breakdown, or to see a table — the app shows tables automatically."
                        + (match_hint if match_hint else "")
                    )

                elif is_aggregate_query:
                    return (
                        f"USER QUERY: {user_query}\n"
                        f"SYSTEM DATA: {display_count} grouped summary rows.\n\n"
                        "TASK:\n"
                        "Act as a technical building analyst. Write ONLY a 2-4 sentence insight summary.\n"
                        "PRIMARY GOAL: You MUST directly and specifically answer the user's query or specific comparison/question using the tool results. For example, if the user asks to compare specific elements, categories, or floors (e.g., 'compare Ground Floor and First Floor BDM'), you MUST focus directly on those elements, compare their exact counts/values from the data, and explicitly address the comparison.\n"
                        "CRITICAL INTENT RULE: If the user asks 'how many' of the grouped category exist (e.g. 'how many floors', 'how many buildings'), your VERY FIRST sentence MUST directly state the total number of unique categories found in the data (which equals the number of grouped summary rows). Only summarize highest/lowest values AFTER directly answering the exact 'how many' question.\n"
                        "FALLBACK GOAL: If the user's query is general or does not specify items to compare, summarize the overall distribution, highlighting the highest/most significant values and key trends.\n"
                        "IMPORTANT: If the user asks for 'highest', 'lowest', 'top', or 'bottom', you MUST explicitly name the specific item(s) and their count in your summary. If there is a massive tie (e.g. 20 items with 1 count), just name 1 or 2 examples.\n"
                        "STRICT RULES:\n"
                        "1. Do NOT get distracted by unrelated data (such as unassigned, null, or other categories) if the user's query targets specific items.\n"
                        "2. Do NOT mention internal database IDs or technical tool names.\n"
                        "3. Do NOT render any table natively.\n"
                        "4. You MUST ask the user: 'Would you like to view this data as a markdown table for better understanding?'\n"
                    )

                else:
                    return (
                        f"USER QUERY: {user_query}\n"
                        f"TOTAL RECORDS: {display_count}\n"
                        f"DISPLAYED RECORDS: {len(p_list_for_model)}\n"
                        f"DATA PREVIEW: {p_list_for_model}\n"
                        f"{search_context_prompt_block(search_context)}"
                        "TASK:\n"
                        "Act as a technical building analyst. Summarize the findings in 2-3 friendly, grammatically professional sentences.\n"
                        "PRIMARY GOAL: You MUST directly and specifically answer the user's query or specific comparison/question using the DATA PREVIEW. If the user asks for specific items, locations, or statuses, focus your summary directly on those items first.\n"
                        "IMPORTANT: If the user asks for 'highest', 'lowest', 'top', or 'bottom', you MUST explicitly name the specific item(s) and their count in your summary. If there is a massive tie (e.g. 20 items with 1 count), just name 1 or 2 examples.\n"
                        "If MATCH CONTEXT is provided, add one short sentence with field names and counts only (same style as summary_line).\n"
                        "SECONDARY GOAL: Focus on synthesizing patterns—like shared locations, identical statuses, or equipment types—rather than listing items one by one.\n"
                        "STRICT RULES:\n"
                        "1. Do NOT start with 'Here are' or 'Here is'.\n"
                        "2. Start with 'I found...', 'I've retrieved...', or 'Your search returned...'.\n"
                        "3. Use NO markdown (no bold, no italics) in the summary text.\n"
                        "4. Do NOT include a table natively.\n"
                        "5. Use clear, active-voice grammar.\n"
                        "6. If the displayed records are fewer than the total found, explicitly mention that this is a partial view of the total data.\n"
                        "7. You MUST ask the user: 'Would you like to view this data as a markdown table for better understanding?'\n"
                    )


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



                # ── MULTI-TOOL PATH: 2+ tool calls → render multiple tables ──────────────
                if len(ai_msg.tool_calls) > 1:
                    logger.info("🛠 Running multi-tool execution path with %d tool calls", len(ai_msg.tool_calls))

                    # Extract the current user query
                    user_query = ""
                    for m in reversed(messages):
                        if isinstance(m, HumanMessage):
                            user_query = (m.content or "") if isinstance(m.content, str) else ""
                            break

                    executed_tools = []
                    TOOL_FRIENDLY_NAMES = {
                        "ASSETS": "Assets",
                        "BDM": "BDM Complaints",
                        "PPM": "PPM Work Orders",
                        "FA": "Facility Audit Complaints",
                        "SB": "Schedule Based Work Orders"
                    }
                    def _friendly(name: str) -> str:
                        u = name.upper()
                        for k, v in TOOL_FRIENDLY_NAMES.items():
                            if k in u:
                                return v
                        return name.replace("get_", "").replace("_", " ").title()

                    # Detect if a common limit is requested across datasets
                    _has_number = bool(_re.search(r'\b\d+\b', user_query))
                    _count_pats_multi = (
                        "how many", "total", "number of", "count of", "count ",
                    )
                    _is_multi_count_query = (
                        any(p in user_query.lower() for p in _count_pats_multi)
                        and not _has_number
                        and not _query_wants_list_display(user_query)
                    )
                    common_limit = next((int(tc["args"]["limit"]) for tc in ai_msg.tool_calls if tc.get("args") and isinstance(tc["args"].get("limit"), (int, str)) and str(tc["args"]["limit"]).isdigit()), None)
                    if common_limit is None and _has_number:
                        # Removed buggy logic: Do not scrape the raw user query for numbers, 
                        # because names like "Building 1" will mistakenly set limit=1
                        pass

                    for tool_call in ai_msg.tool_calls:
                        tool_name = tool_call["name"]
                        tool_fn = self.tool_map[tool_name]
                        if tool_call.get("args") is None:
                            tool_call["args"] = {}
                        args = dict(tool_call["args"])
                        args.pop("user_id", None)
                        args["user_name"] = user_name
                        if user_id is not None:
                            args["user_id"] = str(user_id)

                        # Set default limit to common_limit if not explicitly specified for this tool call
                        if args.get("limit") is None and common_limit is not None:
                            args["limit"] = common_limit

                        if args.get("limit") is not None:
                            logger.info("✅ Multi-Tool: Trusting limit=%s from AI payload.", args.get("limit")) 
                        # Infer dates
                        inferred_from, inferred_to = extract_date_from_query(user_query)
                        if args.get("date_from") is None and inferred_from is not None:
                            args["date_from"] = inferred_from
                        if args.get("date_to") is None and inferred_to is not None:
                            args["date_to"] = inferred_to

                        try:
                            args = normalize_tool_args(tool_name, user_query, args)
                            tool_call["args"] = args
                            tool_result = tool_fn.invoke(dict(args))
                            logger.info("✅ Multi-tool call succeeded: %s", tool_name)
                        except Exception as e:
                            logger.error("❌ Multi-tool call failed for %s: %s", tool_name, e)
                            tool_result = f"Error: {str(e)}"

                        parsed = tool_result
                        if isinstance(tool_result, str):
                            try:
                                parsed = json.loads(tool_result)
                            except json.JSONDecodeError:
                                logger.warning("Multi-tool %s returned non-JSON: %s", tool_name, tool_result[:100])
                                messages.append(
                                    ToolMessage(content=tool_result, tool_call_id=tool_call["id"])
                                )
                                executed_tools.append({
                                    "tool_name": tool_name,
                                    "friendly_name": _friendly(tool_name),
                                    "p_list": [],
                                    "display_count": 0,
                                    "search_context": {"summary_line": tool_result},
                                })
                                continue

                        if isinstance(parsed, dict):
                            p_list = parsed.get("p_list", list(parsed.values()) if "p_list" not in parsed else [])
                        else:
                            p_list = parsed if isinstance(parsed, list) else []

                        ds_search_context = None
                        if isinstance(parsed, dict):
                            ds_search_context = extract_from_tool_response(
                                parsed,
                                keyword_used=args.get("keyword"),
                                entity=self._entity_label_from_tool(tool_name),
                            )

                        p_count = parsed.get("p_count", len(p_list)) if isinstance(parsed, dict) else len(p_list)
                        display_count = len(p_list)
                        if p_list and isinstance(p_list[0], dict):
                            for key in ("total_count", "total_count_over", "full_count", "overall_count"):
                                val = p_list[0].get(key)
                                if isinstance(val, (int, float)) and val >= 0:
                                    display_count = int(val)
                                    break
                        if isinstance(p_count, (int, float)) and p_count >= 0:
                            display_count = max(display_count, int(p_count))

                        friendly_name = _friendly(tool_name)
                        if args.get("is_aggregate") and args.get("group_by_columns"):
                            import re as _re_agg
                            formatted_cols = [
                                _re_agg.sub(r'(?<!^)(?=[A-Z])', ' ', col)
                                for col in args.get("group_by_columns", [])
                            ]
                            friendly_name = f"{friendly_name} by {', '.join(formatted_cols)}"

                        # Cap records sent to the MODEL (ToolMessage) to avoid token overflow.
                        # The full p_list is stored in executed_tools for the frontend response.
                        # Aggregate queries use a higher cap since grouped rows are always small.
                        _is_multi_agg = args.get("is_aggregate") and args.get("group_by_columns")
                        _MULTI_MAX_DISPLAY = 500 if _is_multi_agg else 25
                        _records_for_model = p_list if len(p_list) <= _MULTI_MAX_DISPLAY else p_list[:_MULTI_MAX_DISPLAY]
                        if len(p_list) > _MULTI_MAX_DISPLAY:
                            logger.info(
                                "📌 Multi-tool: capping ToolMessage records %d → %d for %s (token safety)",
                                len(p_list), _MULTI_MAX_DISPLAY, tool_name,
                            )

                        _tm_payload: dict = {
                            "dataset_name": friendly_name,
                            "message": f"{display_count} records found",
                            "records": _records_for_model,   # capped — safe for model context
                            "total_count": display_count,
                        }
                        if ds_search_context:
                            _tm_payload["search_context"] = ds_search_context
                        messages.append(
                            ToolMessage(
                                content=json.dumps(_tm_payload),
                                tool_call_id=tool_call["id"]
                            )
                        )
                        executed_tools.append({
                            "tool_name": tool_name,
                            "friendly_name": friendly_name,
                            "p_list": p_list,               # full list — sent to frontend
                            "display_count": display_count,
                            "search_context": ds_search_context,
                        })

                    # No data at all → short-circuit (count queries may keep p_list empty on purpose)
                    if not executed_tools:
                        msg = "No records were found for your request."
                        return msg, msg, messages
                    if not _is_multi_count_query and all(
                        len(t["p_list"]) == 0 and t.get("display_count", 0) == 0
                        for t in executed_tools
                    ):
                        msg = "No records were found for your request."
                        return msg, msg, messages

                    def _plain_count_only_multi(tools: list) -> bool:
                        return False

                    # ── MULTI-TABLE SYSTEM PROMPT ─────────────────────────────────
                    # Injected ONLY for multi-table responses so the LLM knows the
                    # frontend will render the tables separately — it must write only
                    # a concise plain-text summary, never reproduce table markup.
                    _multi_table_instructions = (
                        "Summarise multi-dataset tool results in 2-3 friendly sentences. "
                        "Name each dataset and its record count. "
                        "If match context is given, one short phrase per dataset with field names and counts. "
                        "IMPORTANT: If the user asks for 'highest', 'lowest', 'top', or 'bottom', you MUST explicitly name the specific item(s) and their count in your summary. If there is a massive tie (e.g. 20 items with 1 count), just name 1 or 2 examples.\n"
                    )
                    if _plain_count_only_multi(executed_tools):
                        _multi_table_instructions += (
                            "No tables, HTML, bullets, or raw rows. "
                            "Do NOT ask about markdown tables, details, or viewing data — counts only."
                        )
                    else:
                        _multi_table_instructions += (
                            "The UI already shows interactive data tables for each dataset below your summary. "
                            "Do NOT ask 'Would you like to view this data as a markdown table?' or similar — "
                            "that is redundant. Give counts and match context only (e.g. Spot Name). "
                            "If only a preview of rows is shown, state total counts clearly."
                        )
                    multi_table_system_prompt = SystemMessage(content=_multi_table_instructions)

                    summary_messages = [multi_table_system_prompt] + messages[:]
                    _multi_sc_lines = []
                    for t in executed_tools:
                        line = f"- {t['friendly_name']}: {t['display_count']} records"
                        sc = t.get("search_context")
                        if sc and sc.get("summary_line"):
                            line += f" ({sc['summary_line']})"
                        _multi_sc_lines.append(line)
                    summary_messages.append(HumanMessage(content=(
                        f"The user asked: '{user_query}'.\n"
                        "Datasets retrieved:\n" +
                        "\n".join(_multi_sc_lines) +
                        "\n\nWrite your 2-3 sentence summary now. If match counts are provided, one short sentence with field names and counts only."
                    )))

                    summary_ai_msg = self.model.invoke(summary_messages)
                    self._accumulate_tokens(summary_ai_msg)
                    context_summary = _strip_redundant_table_offer(
                        self._get_content_str(summary_ai_msg) or "Here are the results of your query."
                    )

                    # Large count-only (e.g. 623+5) → plain text; small counts → show tables below
                    if _plain_count_only_multi(executed_tools):
                        self._log_query_summary(current_user_query)
                        return context_summary, context_summary, messages

                    # Build the structured multi-dataset JSON the frontend expects
                    multiple_datasets_response = json.dumps({
                        "type": "multiple_datasets",
                        "context_summary": context_summary,
                        "datasets": [
                            {
                                "name": t["friendly_name"],
                                "records": t["p_list"],
                                "total_count": t.get("display_count", 0),
                                "search_context": t.get("search_context"),
                            }
                            for t in executed_tools
                            if len(t["p_list"]) > 0 or t.get("display_count", 0) > 0
                        ]
                    })

                    self._log_query_summary(current_user_query)
                    return multiple_datasets_response, context_summary, messages

                # ── SINGLE-TOOL PATH ─────────────────────────────────────────────
                is_count_query     = False
                is_aggregate_query = False
                display_count      = 0
                p_list_for_model   = []

                for tool_call in ai_msg.tool_calls:
                    tool_name = tool_call["name"]
                    tool_fn = self.tool_map[tool_call["name"]]
                    if tool_call.get("args") is None:
                        tool_call["args"] = {}
                    args = dict(tool_call["args"])
                    args.pop("user_id", None)
                    args["user_name"] = user_name
                    if user_id is not None:
                        args["user_id"] = str(user_id)

                    # Override limit for count queries — LLM often passes limit=1 incorrectly
                    user_query = ""
                    for m in reversed(messages):
                        if isinstance(m, HumanMessage):
                            user_query = (m.content or "") if isinstance(m.content, str) else ""
                            break

                    if args.get("limit") is not None:
                        logger.info("✅ Trusting limit=%s from AI payload.", args.get("limit"))

                    # If model omitted dates, infer from query keywords (e.g., present => today)
                    inferred_from, inferred_to = extract_date_from_query(user_query)
                    if args.get("date_from") is None and inferred_from is not None:
                        args["date_from"] = inferred_from
                    if args.get("date_to") is None and inferred_to is not None:
                        args["date_to"] = inferred_to

                    # ── FOLLOW-UP PAYLOAD MERGE ─────────────────────────────────
                    # Problem: for follow-up queries like "among them how many are online",
                    # the model adds the NEW filter (status=Online) but DROPS ALL filters
                    # from the previous payload (e.g. division='HVAC System', keyword='FCU').
                    #
                    # Fix: if the query is a follow-up (pronoun detected) AND we have a
                    # stored previous payload, merge the stored fields into the current args.
                    # The model's new fields always win (override previous); missing fields
                    # are filled in from the previous payload.
                    #
                    # Independent queries: model already sends a fresh keyword/filter.
                    # Python does NOT inject anything for those — the model handles them.
                    # ────────────────────────────────────────────────
                    # Fields that are always rebuilt per-query — never carry over
                    _NO_CARRY = {"user_name", "user_id", "offset", "limit",
                                 "is_aggregate", "group_by_columns"}
                    from app.services.query_classifier import _FOLLOWUP_PRONOUNS as _FUP_RE
                    _is_followup = bool(_FUP_RE.search(user_query))

                    # ── FOLLOW-UP TOOL CORRECTION ──────────────────────────────────────────
                    # Problem: "give me 8 among them" after PPM MONTHLY query picks BDM
                    # because BDM still has an old Catering Services payload.
                    #
                    # Fix: for follow-up queries, ALWAYS use _last_used_tool (the single
                    # most recently called tool). If the model picks a DIFFERENT tool,
                    # redirect to _last_used_tool.
                    if _is_followup and self._last_used_tool and self._last_used_tool != tool_name:
                        _redirect_tool = self._last_used_tool
                        logger.info(
                            "🔀 Follow-up tool correction | model picked %s → "
                            "redirecting to last-used %s | query='%s'",
                            tool_name, _redirect_tool, user_query[:70],
                        )
                        tool_name = _redirect_tool
                        if _redirect_tool in self.tool_map:
                            tool_fn = self.tool_map[_redirect_tool]

                    # ── END FOLLOW-UP TOOL CORRECTION ─────────────────────────────────────

                    # Retrieve the stored payload for THIS tool only
                    _prev_payload = self._last_tool_payload.get(tool_name, {})

                    if _is_followup and _prev_payload:
                        _injected = []
                        for _k, _v in _prev_payload.items():
                            if _k in _NO_CARRY:
                                continue
                            # Only inject if model did NOT already set this field
                            if _k not in args or args[_k] is None:
                                args[_k] = _v
                                _injected.append(f"{_k}={_v!r}")
                        if _injected:
                            logger.info(
                                "🔗 Follow-up payload merge | tool=%s | injected=%s | query='%s'",
                                tool_name, ", ".join(_injected), user_query[:70],
                            )
                    # ── END FOLLOW-UP PAYLOAD MERGE ──────────────────────────────────

                    search_context = None


                    try:
                        args = normalize_tool_args(tool_name, user_query, args)
                        tool_call["args"] = args
                        tool_result = tool_fn.invoke(dict(args))
                        logger.info(f"✅ Tool call succeeded on first try | {tool_name}")
                        # ── Save payload per-tool for next follow-up query ──────────────────────────
                        _SKIP_SAVE = {"user_name", "user_id", "offset", "limit",
                                      "is_aggregate", "group_by_columns"}
                        _saved = {k: v for k, v in args.items()
                                  if k not in _SKIP_SAVE and v is not None}
                        self._last_tool_payload[tool_name] = _saved
                        self._last_used_tool = tool_name  # Track most recent tool
                        logger.info(
                            "💾 Saved %s payload for follow-up | %s",
                            tool_name, _saved,
                        )
                        # ────────────────────────────────────────────────────────

                    except Exception as e:
                        logger.error(f"❌ Tool call failed: {e}")
                        tool_result = f"Error: {str(e)}"

                    # Parse tool result — tools return JSON string, not dict

                    parsed = tool_result
                    if isinstance(tool_result, str):
                        try:
                            parsed = json.loads(tool_result)
                        except json.JSONDecodeError:
                            logger.warning("Tool %s returned non-JSON: %s", tool_name, tool_result[:100])
                            messages.append(
                                ToolMessage(content=tool_result, tool_call_id=tool_call["id"])
                            )
                            # Let the LLM handle the error gracefully!
                            error_msg = self.model.invoke(messages)
                            self._accumulate_tokens(error_msg)
                            ans = self._get_content_str(error_msg)
                            return ans, ans, messages

                    # Extract p_list and p_count from API response shape
                    if isinstance(parsed, dict):
                        if "p_list" in parsed:
                            p_count = parsed.get("p_count", 0)
                            p_list = parsed.get("p_list", [])
                        else:
                            p_list = list(parsed.values())
                            p_count = len(p_list)
                        search_context = extract_from_tool_response(
                            parsed,
                            keyword_used=args.get("keyword"),
                            entity=self._entity_label_from_tool(tool_name),
                        )
                        self._last_search_context = search_context
                        if search_context:
                            logger.info(
                                "🔍 Match context | mode=%s | summary=%s",
                                search_context.get("search_mode")
                                or ("keyword" if search_context.get("keyword") else "?"),
                                (search_context.get("summary_line") or "")[:120],
                            )
                    else:
                        p_list = parsed if isinstance(parsed, list) else []
                        p_count = len(p_list)
                        self._last_search_context = None

                    # For count queries: SP may return total in rows (COUNT(*) OVER ()) — prefer that
                    
                    total_for_count = p_count
                    if p_list and isinstance(p_list[0], dict):
                        for key in ("total_count", "total_count_over", "full_count", "overall_count"):
                            val = p_list[0].get(key)
                            if isinstance(val, (int, float)) and val >= 0:
                                total_for_count = int(val)
                                logger.info("📊 Using total from row field '%s' = %s", key, total_for_count)
                                break

                    logger.info(
                        "📊 Tool result | %s | p_list_length=%s | p_count=%s | total_for_count=%s",
                        tool_name, len(p_list), p_count, total_for_count
                    )
                    # ── If tool actually ran in aggregate mode → force aggregate intent
                    # This overrides whatever the intent classifier says later
                    tool_was_aggregate = args.get("is_aggregate") is True
                    tool_has_groupby = bool(args.get("group_by_columns"))

                    if tool_was_aggregate:
                        if tool_has_groupby:
                            logger.info("📊 Tool ran in aggregate mode WITH group_by → forcing AGGREGATE intent")
                            is_aggregate_query = True
                            is_count_query = False
                        else:
                            logger.info("🔢 Tool ran in aggregate mode WITHOUT group_by → treating as COUNT intent")
                            is_aggregate_query = False
                            is_count_query = True

                    
                    if p_count == 0 and total_for_count == 0:
                        logger.info("📊 No records found for tool %s", tool_name)
                        self._log_query_summary(current_user_query)
                        
                        entity = _enrich_entity_from_args(
                            self._entity_label_from_tool(tool_name), args
                        )

                        # Extract time context
                        time_kw, _ = extract_date_from_query(user_query)
                        time_context = f" for {time_kw}" if time_kw else ""
                                
                        msg = f"No {entity} found for your request{time_context}."
                        return msg, msg, messages

                    
                    display_count = total_for_count if total_for_count > len(p_list) else p_count

                    
                    #  call 2 -updated from 2 intents (count/list) to 3 intents (count/aggregate/list)
                    # ── Build combined query using previous human message for intent context ──
                    # ── Build combined query ONLY if previous AI response was a clarification ──
                    clarification_markers = ["do you mean", "please clarify"]
                    previous_ai_was_clarification = False
                    ai_messages_list = [m for m in messages if isinstance(m, AIMessage)]
                    if ai_messages_list:
                        last_ai_content = self._get_content_str(ai_messages_list[-1])
                        previous_ai_was_clarification = any(
                            kw in last_ai_content.lower()
                            for kw in clarification_markers
                        )

                    if previous_ai_was_clarification:
                        human_messages_list = [m for m in messages if isinstance(m, HumanMessage)]
                        previous_query = ""
                        if len(human_messages_list) >= 2:
                            prev = human_messages_list[-2].content
                            previous_query = prev if isinstance(prev, str) else ""
                        combined_query_for_intent = f"{previous_query} {user_query}".strip()
                        logger.info(f"🔍 Intent classification (clarification reply) | combined='{combined_query_for_intent}'")
                    else:
                        combined_query_for_intent = user_query
                        logger.info(f"🔍 Intent classification (normal) | query='{combined_query_for_intent}'")

                    if not tool_was_aggregate:
                        inferred_intent = _infer_intent_from_query(combined_query_for_intent)
                        if inferred_intent:
                            intent = inferred_intent
                            is_count_query = intent == "count"
                            is_aggregate_query = intent == "aggregate"
                            logger.info("🔍 Intent inferred (no LLM) | intent=%s", intent)
                        else:
                            intent_msg = self.model.invoke([
                                HumanMessage(content=f"""
                                Classify this user query into one of three intents:
                                - "count"     → user wants ONLY a single total number
                                - "aggregate" → user wants a grouped summary or breakdown by category
                                - "list"      → user wants full records shown as a table
                                Rules: "how many per X" / "breakdown by X" = aggregate;
                                "how many total" with no grouping = count;
                                "show/list/get" without counting words = list.

                                Query: "{combined_query_for_intent}"

                                Reply with ONLY one word: count or aggregate or list
                                """)
                            ])
                            self._accumulate_tokens(intent_msg)
                            intent = self._get_content_str(intent_msg).strip().lower()
                            is_count_query = intent == "count"
                            is_aggregate_query = intent == "aggregate"
                    else:
                        # intent already set above by tool_has_groupby check — do NOT override
                        intent = "count" if is_count_query else "aggregate"
                        
                    if is_count_query:
                        logger.info("🔢 Intent=COUNT — sending count only to model | query='%s'", user_query)
                    elif is_aggregate_query:
                        logger.info("📊 Intent=AGGREGATE — sending grouped summary to model | query='%s'", user_query)
                    else:
                        logger.info("📋 Intent=LIST — sending full records to model | query='%s'", user_query)

                    MAX_DISPLAY = 25
                    if is_aggregate_query:
                        MAX_DISPLAY = 500
                    p_list_for_model = p_list if len(p_list) <= MAX_DISPLAY else p_list[:MAX_DISPLAY]
                    is_large_result = len(p_list) > MAX_DISPLAY

                    
                    # aggregate is excluded from large dataset path
                    # because grouped summary rows are always small (just a few rows)
                    if is_large_result and not is_count_query and not is_aggregate_query:
                        logger.info("📌 Large dataset (%d records) → sending raw JSON to frontend", len(p_list))

                        messages.append(
                            ToolMessage(
                                content=json.dumps({
                                    "message": f"{display_count} records found (large dataset)",
                                    "total_count": display_count,
                                    "records": []  # no records sent to model

                                }),
                                tool_call_id=tool_call["id"]
                            )
                        )
                        _large_ctx_hint = ""
                        if search_context and search_context.get("summary_line"):
                            _large_ctx_hint = (
                                f" Include one sentence like: {search_context['summary_line']}"
                            )
                        messages.append(
                            HumanMessage(content=(
                                f"The user asked: '{user_query}'. "
                                f"The system found {display_count} records."
                                f"{_large_ctx_hint} "
                                "Write 1-2 friendly sentences. Do NOT list individual records. Keep it concise."
                            ))
                        )
                         # CALL 3 — Large dataset context call (records=[] so should be small)
                        context_ai_msg = self.model.invoke(messages)
                        self._accumulate_tokens(context_ai_msg)
                        context_summary = self._get_content_str(context_ai_msg) or f"Found {display_count} records for your request."
                        context_summary = _append_explicit_today(context_summary, user_query)
                        context_summary = append_match_explanation(context_summary, search_context)
                        logger.info("✅ Context summary generated for large dataset | context='%s'", context_summary[:80])

                        large_dataset_response = json.dumps({
                            "type": "large_dataset",
                            "context_summary": context_summary,
                            "records": p_list,
                            "search_context": search_context,
                        })
                        logger.info("✅ Large dataset JSON prepared: %d records", len(p_list))

                        self._log_query_summary(current_user_query)
                        return large_dataset_response, context_summary, messages

                    _tool_payload = {
                        "message": f"{display_count} records found",
                        "records_returned": len(p_list),
                        "total_count": display_count,
                        "displayed_count": len(p_list_for_model),
                        "records": [] if is_count_query else p_list_for_model,
                    }
                    if search_context:
                        _tool_payload["search_context"] = search_context
                    messages.append(
                        ToolMessage(
                            content=json.dumps(_tool_payload),
                            tool_call_id=tool_call["id"]
                        )
                    )

                #  STEP 3 — Call model again to generate final answer
                _entity_label = self._entity_label_from_tool(tool_name)
                if search_context:
                    search_context["total_records"] = display_count

                _use_keyword_count_reply = bool(
                    is_count_query
                    and search_context
                    and (
                        search_context.get("keyword")
                        or search_context.get("search_mode") == "field_filter"
                        or search_context.get("search_mode") == "multi_field_filter"
                    )
                )

                if _use_keyword_count_reply:
                    logger.info(
                        "🔢 Count + %s — using polished single-sentence reply",
                        search_context.get("search_mode", "keyword"),
                    )
                elif is_count_query:
                    logger.info("🔢 Sending count-only prompt to model")
                    messages.append(HumanMessage(content=self._build_final_prompt(
                        is_count_query,
                        is_aggregate_query,
                        user_query,
                        display_count,
                        p_list_for_model,
                        search_context,
                    )))

                elif is_aggregate_query:
                    logger.info("📊 Sending aggregate prompt to model")
                    messages.append(HumanMessage(content=self._build_final_prompt(
                    is_count_query,
                    is_aggregate_query,
                    user_query,
                    display_count,
                    p_list_for_model,
                    search_context,
                )))

                else:
                    logger.info("📋 Sending list prompt to model")
                    messages.append(HumanMessage(content=self._build_final_prompt(
                    is_count_query,
                    is_aggregate_query,
                    user_query,
                    display_count,
                    p_list_for_model,
                    search_context,
                )))

                # CALL 4 — Final answer generation
                if _use_keyword_count_reply:
                    final_content = format_keyword_count_reply(
                        search_context, entity=_entity_label
                    )
                else:
                    final_ai_msg = self.model.invoke(messages)
                    self._accumulate_tokens(final_ai_msg)
                    final_content = self._get_content_str(final_ai_msg)

                    if not final_content or str(final_content).strip() == "":
                        final_content = "No data records were found matching your request."
                        logger.info("final_ai_content is empty")

                # aggregate context summary same as count (one sentence)
                # because aggregate answer starts with a summary sentence
                if is_count_query:
                    if not _use_keyword_count_reply:
                        final_content = append_match_explanation(
                            final_content, search_context, entity=_entity_label
                        )
                    context_summary = final_content
                    logger.info("🧠 Count query context_summary='%s'", context_summary[:80])
                elif is_aggregate_query:
                    #take first line as context summary
                    # full grouped table is too large for lc_memory
                        lines = final_content.split("\n")
                        summary_lines = []
                        for line in lines:
                            stripped = line.strip()
                            # Stop when we hit the table (starts with |)
                            if stripped.startswith("|"):
                                break
                            # Collect non-empty lines
                            if stripped:
                                summary_lines.append(stripped)
                        
                        context_summary = " ".join(summary_lines) if summary_lines else f"Found grouped summary with {display_count} rows."
                        logger.info("🧠 Aggregate query context_summary='%s'", context_summary[:80])
                        # ── Only build graph if tool actually ran in aggregate mode ──
                        if tool_was_aggregate and is_graph:  # ← ADD is_graph CHECK
                            logger.info("📊 [GRAPH] Wrapping aggregate as graph JSON | records=%d", len(p_list_for_model))
                            graph_context = "Here is the graph result for your query."
                            graph_response = self.build_graph_response(graph_context, p_list_for_model)
                            self._log_query_summary(current_user_query)
                            return graph_response, context_summary, messages
                        else:
                            if tool_was_aggregate:
                                logger.info("📊 [AGGREGATE] Tool ran in aggregate mode but is_graph=False → returning as text+table")
                            else:
                                logger.warning("⚠️ [GRAPH] Intent=AGGREGATE but tool ran in RAW mode — skipping graph, returning text")

                    
                else:
                    # Extract everything BEFORE the table as context summary
                    lines = final_content.split("\n")
                    summary_lines = []
                    for line in lines:
                        stripped = line.strip()
                        # Stop when we hit the table
                        if stripped.startswith("|"):
                            break
                        if stripped:
                            summary_lines.append(stripped)
                   
                    context_summary = " ".join(summary_lines) if summary_lines else f"Found {display_count} records for your request."
                    final_content = append_match_explanation(final_content, search_context)
                    context_summary = append_match_explanation(context_summary, search_context)
                    logger.info("🧠 List query context_summary='%s'", context_summary[:80])

                # ── Stash table data for two-step yes/no flow ──
                if not is_count_query:
                    self._last_pending_table = p_list_for_model
                    logger.info("📋 [NORMAL PATH] Stashed pending_table | records=%d", len(p_list_for_model))
                else:
                    self._last_pending_table = None

                # logger.info("✅ Final response generated after tool execution")
                # self._log_query_summary(current_user_query)
                

                logger.info("✅ Final response generated after tool execution")
                self._log_query_summary(current_user_query)
                entity = "data"
                if "asset" in final_content.lower():
                    entity = "assets"
                elif "complaint" in final_content.lower():
                    entity = "complaints"
                elif "ppm" in final_content.lower():
                    entity = "ppm tasks"

                if is_graph and not is_aggregate_query and not is_count_query:
                    final_content = (
                        f"Here are the results for your query:\n\n{final_content}\n\n"
                        f"**Graph not available for this query**\n"
                        f"To generate a chart, the data needs to be grouped by a category.\n"
                        f"Since your query *'{user_query}'* does not include any grouping or category, a graph cannot be created.\n\n"
                        f"**Tip:** Try modifying your question by adding a category (for example: by type, date, or status) so that I can generate a meaningful chart"

                    )
                final_content = _append_explicit_today(final_content, user_query)
                context_summary = _append_explicit_today(context_summary, user_query)

                return final_content, context_summary, messages

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