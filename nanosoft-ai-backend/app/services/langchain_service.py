"""
LangChain Service — AI model with tool support
"""
import logging
from typing import Any
import re as _re
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

import json

logger = logging.getLogger("langchain_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)

# UI already renders tables for multi-tool and most list flows — strip model boilerplate.
_RE_TABLE_OFFER_PHRASE = _re.compile(
    r"\s*(?:"
    r"would you like to view (?:this )?data as a markdown table(?: for better understanding)?|"
    r"would you like (?:to see )?(?:this )?(?:data )?(?:as |in )?a (?:markdown )?table(?: for better understanding)?"
    r")\s*\??\s*",
    _re.I,
)


def _strip_redundant_table_offer(text: str) -> str:
    if not text or not isinstance(text, str):
        return text or ""
    cleaned = _RE_TABLE_OFFER_PHRASE.sub(" ", text)
    return _re.sub(r"\s+", " ", cleaned).strip()


def extract_date_from_query(query: str):
    """Extract date keyword from user query for forced tool calls."""
    q = query.lower()
    # ORDER MATTERS — check longer phrases first
    if "last week" in q:
        return "last week", "last week"
    elif "this week" in q:
        return "this week", "today"
    elif "last month" in q:
        return "last month", "last month"
    elif "this month" in q:
        return "this month", "today"
    elif "this year" in q:
        return "this year", "today"
    elif "last year" in q:
        return "last year", "last year"
    elif "yesterday" in q:
        return "yesterday", "yesterday"
    elif "today" in q:
        return "today", "today"
    elif "current" in q or "now" in q:
        # Treat current/now wording as today's data
        return "today", "today"
    
    # ── Dynamic pattern: X days/weeks/months/years ago/before ──
    match = _re.search(r"(\d+)\s*(day|week|month|year)s?\s*(ago|before)", q)
    if match:
        found_phrase = match.group(0)
        return found_phrase, found_phrase

    # ── Match explicit month names (e.g. "March", "April 2026") ──
    month_match = _re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)(?:\s+\d{4})?\b", q)
    if month_match:
        found_month = month_match.group(0).title()
        return found_month, found_month

    return None, None


def _complaint_query_is_clear(query: str, messages: list | None = None) -> bool:
    """
    True when the user named FA and/or BDM (or answered a prior clarification).
    Generic "complaints" alone stays ambiguous.
    """
    q = (query or "").lower()
    if _re.search(
        r"\b(fa|bdm|facility audit|breakdown maintenance|breakdown)\b",
        q,
    ):
        return True
    # "BDM and FA" / "FA and BDM" in one question → always fetch both, never clarify
    if _re.search(r"\bbd[m]?\b", q) and _re.search(r"\bfa\b", q):
        return True
    if _re.search(r"\b(fa|bdm)\s+and\s+(fa|bdm)\b", q):
        return True
    if _re.search(r"\bboth\b", q) and _re.search(
        r"\b(fa|bdm|complaints?|facility audit|breakdown)\b", q
    ):
        return True
    # User replied after clarification in the same session
    if messages:
        prior_human = [
            (m.content or "").lower()
            for m in messages
            if isinstance(m, HumanMessage) and isinstance(m.content, str)
        ]
        if len(prior_human) >= 2:
            prev = prior_human[-2]
            if _re.search(
                r"\bdo you mean facility audit|breakdown maintenance\b", prev
            ) or any(
                marker in prev
                for marker in ("please clarify", "fa) complaints or breakdown")
            ):
                return True
    return False


def _query_wants_list_display(query: str) -> bool:
    """User asked to see data (tables), not only a numeric count."""
    q = (query or "").lower()
    return bool(
        _re.search(
            r"\b(show\s+me|show\s+all|show\s+the|list\b|display\b|give\s+me\s+(the\s+)?|retrieve\b|fetch\b)",
            q,
        )
        or q.strip().startswith("show ")
    )


def _infer_intent_from_query(query: str) -> str | None:
    """Fast intent detection for common phrasing (avoids extra model call)."""
    q = (query or "").lower()
    if _re.search(
        r"\b(how many|count of|number of)\s+.+\s+(per|by|each|wise)\b"
        r"|\b(breakdown|grouped by|distribution)\b"
        r"|\bhow many per\b|\bcount by\b"
        r"|\bwise\b.*\bcounts?\b|\bcounts?\b.*\b(per|by|wise)\b",
        q,
    ):
        return "aggregate"
    # "show me how many …" → list (preview tables + counts), not count-only text
    if _re.search(
        r"\b(how many|total count|number of|count of|how many total|get the count|show total)\b",
        q,
    ):
        if _query_wants_list_display(q):
            return "list"
        return "count"
    if _re.search(r"\b(show|list|get |fetch |display|give me|retrieve|provide)\b", q):
        return "list"
    return None


# Max rows per dataset in multi-tool UI when user also asked to "show" data
MULTI_DATASET_PREVIEW_LIMIT = 30
# For "how many" only: still show tables when each dataset has at most this many rows
MULTI_COUNT_AUTO_TABLE_MAX = 30


def _append_explicit_today(text: str, query: str) -> str:
    """Ensure responses mention the same time wording user asked for."""
    q = (query or "").lower()
    if not any(k in q for k in ("today", "current", "now")):
        return (text or "").strip()

    base = (text or "").strip()

    if "current" in q:
        if "current" not in base.lower():
            return f"{base} This is for current data.".strip()
        return base

    if "now" in q:
        if "now" not in base.lower() and "today" not in base.lower():
            return f"{base} This is for now.".strip()
        return base

    if "today" not in base.lower():
        return f"{base} This is for today.".strip()
    return base


def _enrich_entity_from_args(entity: str, args: dict) -> str:
    """Append filter context to entity label for empty-result messages."""
    if not args:
        return entity
    if args.get("keyword"):
        entity = f"{entity} matching '{args.get('keyword')}'"
    for key, label in (
        ("complaint_no", "complaint"),
        ("asset_tag_no", "asset tag"),
        ("work_order", "work order"),
        ("asset_type", "type"),
        ("building", "building"),
        ("floor", "floor"),
        ("locality", "locality"),
        ("division", "division"),
        ("discipline", "discipline"),
        ("trade_group", "trade group"),
        ("status", "status"),
        ("priority", "priority"),
        ("condition", "condition"),
        ("tech", "technician"),
        ("category", "category"),
        ("contract", "contract"),
        ("make", "make"),
        ("model", "model"),
        ("serial_no", "serial number"),
    ):
        if args.get(key):
            entity = f"{entity} ({label} '{args.get(key)}')"
    if args.get("is_snagged"):
        entity = f"snagged {entity}"
    if args.get("is_scraped"):
        entity = f"scraped {entity}"
    return entity


class LangChainService:
    def __init__(self):
        try:
            self.model = ChatGoogleGenerativeAI(
                model=settings.GOOGLE_AI_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.0
            ).bind_tools([ASSETS, PPM, BDM, FA, SB])

            self.tool_map = {
                "ASSETS": ASSETS,
                "PPM":    PPM,
                "BDM":    BDM,
                "FA":     FA,
                "SB":     SB,
            }
            self._last_search_context = None
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
    async def process_query(self, messages: list, user_name: str = None, user_id: str = None, session_id: str = None, is_graph: bool = False) -> tuple[str, str, list]:
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

            # complaint ambiguity check — only when type (FA vs BDM) is not named
            _complaint_ambiguous = bool(_re.search(r'\bcomplaints?\b', _q))
            _complaint_clear = _complaint_query_is_clear(current_user_query, messages)

            # work order ambiguity check
            _workorder_ambiguous = bool(_re.search(r'\b(work\s*orders?|scheduled|compliance|work\s*order)\b', _q))
            _workorder_clear     = bool(_re.search(r'\b(ppm|sb|preventive|schedule[\s\-]based)\b', _q))

            if _complaint_ambiguous and not _complaint_clear:
                logger.info("🔀 Ambiguous complaint query intercepted before model | query='%s'", current_user_query)
                clarification = (
                    "Do you mean Facility Audit (FA) complaints or Breakdown Maintenance (BDM) complaints?\n"
                    "Please clarify so I can fetch the correct data."
                )
                return clarification, clarification, messages

            if _workorder_ambiguous and not _workorder_clear:
                logger.info("🔀 Ambiguous work order query intercepted before model | query='%s'", current_user_query)
                clarification = (
                    "Do you mean PPM (Preventive Maintenance) work orders or SB (Schedule Based) work orders?\n"
                    "Please clarify so I can fetch the correct data."
                )
                return clarification, clarification, messages


            # ── QUERY REWRITING STEP REMOVED ──
            # The original user query is passed directly to the model.
            logger.info(f"💬 Direct Query (No Rewriter): '{current_user_query}'")


            # CALL 1 — First model call
            ai_msg = self.model.invoke(messages)
            
            self._accumulate_tokens(ai_msg)
            logger.info("🤖 First model call | tool_calls=%s", bool(ai_msg.tool_calls))

            if ai_msg.tool_calls:
                logger.info(f"🛠 Tool calls: {[tc['name'] for tc in ai_msg.tool_calls]}")

                # Deduplicate tool calls with identical names and arguments
                unique_tool_calls = []
                seen_keys = set()
                for tc in ai_msg.tool_calls:
                    call_key = (tc["name"], json.dumps(tc.get("args") or {}, sort_keys=True))
                    if call_key not in seen_keys:
                        seen_keys.add(call_key)
                        unique_tool_calls.append(tc)
                    else:
                        logger.info("♻️ Discarding duplicate tool call: %s", tc["name"])
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

                        # Bulletproof limit clearing (Multi-Tool Path):
                        if args.get("limit") is not None:
                            explicit_limit_pattern = r'\b(top|limit|show|first|last|only|get|fetch)\s+(\d+)\b'
                            if not _re.search(explicit_limit_pattern, user_query.lower()):
                                logger.info("🚫 Multi-Tool: Clearing hallucinated limit=%s because user didn't explicitly ask for 'top N' or 'limit N'.", args.get("limit"))
                                args["limit"] = None
                            else:
                                logger.info("✅ Multi-Tool: Keeping limit=%s because user explicitly asked for a specific number of items.", args.get("limit"))
                        # else: keep the limit (which was either parsed by LLM or propagated from common_limit)

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

                        _hide_tables_for_large_count = (
                            _is_multi_count_query
                            and display_count > MULTI_COUNT_AUTO_TABLE_MAX
                        )
                        if _hide_tables_for_large_count:
                            _ui_p_list: list = []
                        elif len(p_list) > MULTI_DATASET_PREVIEW_LIMIT:
                            _ui_p_list = p_list[:MULTI_DATASET_PREVIEW_LIMIT]
                        elif len(p_list) <= 30:
                            _ui_p_list = p_list
                        else:
                            _ui_p_list = p_list[:25] + p_list[-10:]
                        _records_for_ui = _ui_p_list
                        _tm_payload: dict = {
                            "dataset_name": friendly_name,
                            "message": f"{display_count} records found",
                            "records": _records_for_ui,
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
                            "p_list": [] if _hide_tables_for_large_count else _ui_p_list,
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
                        """Pure count answer (no tables) when every dataset is a large total."""
                        if not _is_multi_count_query:
                            return False
                        for t in tools:
                            c = t.get("display_count", 0)
                            if 0 < c <= MULTI_COUNT_AUTO_TABLE_MAX:
                                return False
                        return True

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

                    # Bulletproof limit clearing:
                    # We ONLY respect the AI's limit if the user explicitly asked for a number of items 
                    # using words like "top 5", "limit 10", "show 3", "first 5". 
                    # Just having a number in the query (like "Appartement-1509") is NOT enough to keep the limit!
                    if args.get("limit") is not None:
                        explicit_limit_pattern = r'\b(top|limit|show|first|last|only|get|fetch)\s+(\d+)\b'
                        if not _re.search(explicit_limit_pattern, user_query.lower()):
                            logger.info("🚫 Clearing hallucinated limit=%s because user didn't explicitly ask for 'top N' or 'limit N'.", args.get("limit"))
                            args["limit"] = None
                        else:
                            logger.info("✅ Keeping limit=%s because user explicitly asked for a specific number of items.", args.get("limit"))

                    # If model omitted dates, infer from query keywords (e.g., present => today)
                    inferred_from, inferred_to = extract_date_from_query(user_query)
                    if args.get("date_from") is None and inferred_from is not None:
                        args["date_from"] = inferred_from
                    if args.get("date_to") is None and inferred_to is not None:
                        args["date_to"] = inferred_to

                    search_context = None

                    try:
                        args = normalize_tool_args(tool_name, user_query, args)
                        tool_call["args"] = args
                        tool_result = tool_fn.invoke(dict(args))
                        logger.info(f"✅ Tool call succeeded on first try | {tool_name}")

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
                # Model skipped tool — direct response
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