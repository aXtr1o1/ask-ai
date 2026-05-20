"""
LangChain Service — AI model with tool support
"""
import logging
from typing import Any
import re as _re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.config import settings
from app.tools.facility_tools import ASSETS, PPM, BDM, FA, SB
from app.services.quota_service import quota_fallback_service

import json

logger = logging.getLogger("langchain_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)



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
    elif "present" in q or "current" in q or "now" in q:
        # Treat present/current wording as today's data
        return "today", "today"
    
    # ── Dynamic pattern: X days/weeks/months/years ago/before ──
    import re
    match = re.search(r"(\d+)\s*(day|week|month|year)s?\s*(ago|before)", q)
    if match:
        found_phrase = match.group(0)
        return found_phrase, found_phrase

    # ── Match explicit month names (e.g. "March", "April 2026") ──
    month_match = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)(?:\s+\d{4})?\b", q)
    if month_match:
        found_month = month_match.group(0).title()
        return found_month, found_month

    return None, None


# def _needs_default_last_7_days(query: str) -> bool:
#     q = (query or "").lower()
#     time_keywords = (
#         "today", "yesterday", "last week", "this week", "week",
#         "last month", "this month", "month",
#         "last year", "this year", "year",
#         "day", "days", "date", "present", "current"
#     )
#     if any(k in q for k in time_keywords):
#         return False
#     if _re.search(r"\b\d{4}-\d{2}-\d{2}\b", q):
#         return False
#     return True


# def _append_default_7days(text: str, query: str) -> str:
#     # Logic disabled as per user request
#     return text
    # if _needs_default_last_7_days(query):
    #     suffix = " (This is for the last 7 days)"
    #     if suffix not in text:
    #         return text + suffix
    # return text


def _append_explicit_today(text: str, query: str) -> str:
    """Ensure responses mention the same time wording user asked for."""
    q = (query or "").lower()
    if not any(k in q for k in ("today", "present", "current", "now")):
        return (text or "").strip()

    base = (text or "").strip()

    if "present" in q:
        if "present" not in base.lower():
            return f"{base} This is for present data.".strip()
        return base

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
def _clean_query_for_fallback(query: str) -> str:
    """Strip command prefixes and common suffixes to isolate the user's core request context."""
    q = (query or "").lower()
    # Remove common prefixes
    q = _re.sub(r"^(?:show me all|list all|find all|get all|search for|show me|list|find|get|give me|tell me about|how many|when was|is there any|do you have|where is|what is)\s+", "", q)
    # Remove trailing question marks and common suffixes
    q = _re.sub(r"\s+(?:located|completed|done|finished|available|status|count|total)\??$", "", q)
    q = _re.sub(r"\?$", "", q)
    # Remove leading filler words
    q = _re.sub(r"^(?:all|any|every|the|a|an)\s+", "", q).strip()
    return q


class LangChainService:
    def __init__(self):
        try:
            self.model = ChatGoogleGenerativeAI(
                model=settings.GOOGLE_AI_MODEL,
                google_api_key=settings.GOOGLE_API_KEY
            ).bind_tools([ASSETS, PPM, BDM, FA, SB])

            self.tool_map = {
                "ASSETS": ASSETS,
                "PPM":    PPM,
                "BDM":    BDM,
                "FA":     FA,
                "SB":     SB,
            }
            logger.info("🚀 LangChainService initialized with ASSETS, PPM, BDM tools")
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
                p_list_for_model: list
            ) -> str:
                """
                Build the prompt for final model call.
                - count  → one sentence answer, no table ever
                - aggregate/list → context/summary ONLY, no table
                                followed by a question asking if user wants the table
                """
                if is_count_query:
                    return (
                        "Use the above tool results and give the final answer. "
                        "Reply in one crisp and friendly sentence using the total_count. "
                        "Include what was asked (e.g. 'There are X open complaints.'). "
                        "Do not render any table."
                    )

                elif is_aggregate_query:
                    return (
                        f"USER QUERY: {user_query}\n"
                        f"SYSTEM DATA: {display_count} grouped summary rows.\n\n"
                        "TASK: Write ONLY a 2-4 sentence insight summary. "
                        "Summarize the overall distribution. "
                        "Highlight the highest/most significant values and any notable trends. "
                        "Do NOT mention internal database IDs or technical tool names. "
                        "Do NOT render any table. Do NOT include any markdown table. " + (
                            "\nEnd your response with exactly this line:\n"
                            "**Would you like to see the detailed breakdown table for a better understanding?**"
                            if display_count > 0 else ""
                        )
                    )

                else:
                    return (
                        f"USER QUERY: {user_query}\n"
                        f"TOTAL RECORDS: {display_count}\n"
                        f"DISPLAYED RECORDS: {len(p_list_for_model)}\n"
                        f"DATA PREVIEW: {p_list_for_model}\n\n"
                        "TASK: Act as a technical building analyst. Summarize the findings in 2-3 friendly, "
                        "grammatically professional sentences. Focus on synthesizing patterns—like shared "
                        "locations, identical statuses, or equipment types—rather than listing items one by one. "
                        "If the displayed records are fewer than the total found, explicitly mention that "
                        "this is a partial view of the total data. "
                        "STRICT RULES:\n"
                        "1. Do NOT start with 'Here are' or 'Here is'.\n"
                        "2. Start with 'I found...', 'I've retrieved...', or 'Your search returned...'.\n"
                        "3. Use NO markdown (no bold, no italics) in the summary text.\n"
                        "4. Do NOT include a table.\n"
                        "5. Use clear, active-voice grammar.\n\n" + (
                            "FINAL LINE (MUST BE EXACT):\n"
                            "**Would you like to see the full table for a better understanding?**"
                            if display_count > 0 else ""
                        )
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
            
            fallback_applied = None
            
            # ── Get current user query for summary log ───────────────────────
            current_user_query = ""
            for m in reversed(messages):
                if isinstance(m, HumanMessage):
                    current_user_query = (m.content or "") if isinstance(m.content, str) else ""
                    break

            # ── AMBIGUITY PRE-CHECK (runs before model, before lc_memory influence) ──
            import re as _re

            _q = current_user_query.lower()

            # complaint ambiguity check
            _complaint_ambiguous = bool(_re.search(r'\bcomplaints?\b', _q))
            _complaint_clear     = bool(_re.search(r'\b(fa|bdm|facility audit|breakdown)\b', _q))

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

            # CALL 1 — First model call
            ai_msg = self.model.invoke(messages)
            
            self._accumulate_tokens(ai_msg)
            logger.info("🤖 First model call | tool_calls=%s", bool(ai_msg.tool_calls))

            if ai_msg.tool_calls:
                logger.info(f"🛠 Tool calls: {[tc['name'] for tc in ai_msg.tool_calls]}")

                messages.append(ai_msg)
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

                    
                    count_patterns = ("how many", "total", "number of", "count of", "count ", "how many ")
                    if any(p in user_query.lower() for p in count_patterns) and args.get("limit") is not None:
                        logger.info("📊 Count query detected — clearing limit=%s", args.get("limit"))
                        args["limit"] = None

                    #previously limit was only cleared for count queries now i cleared for the list queries also. 

                    
                    list_patterns = ("list", "show me", "get ", "fetch ", "display",
                                    "give me", "provide", "retrieve", "show ",
                                    "all assets", "all complaints", "all bdm", "all ppm",
                                    "all fa", "all sb")
                    _has_number = bool(_re.search(r'\b\d+\b', user_query))
                    if any(p in user_query.lower() for p in list_patterns) and not _has_number:
                        old_limit = args.get("limit")
                        args["limit"] = None
                        logger.info("📋 List query detected — clearing limit=%s", old_limit)
                    elif _has_number:
                        logger.info("📋 List query with specific number detected — keeping limit as-is | limit=%s", args.get("limit"))

                    # If model omitted dates, infer from query keywords (e.g., present => today)
                    inferred_from, inferred_to = extract_date_from_query(user_query)
                    if args.get("date_from") is None and inferred_from is not None:
                        args["date_from"] = inferred_from
                    if args.get("date_to") is None and inferred_to is not None:
                        args["date_to"] = inferred_to
                    try:
                        tool_result = tool_fn.invoke(dict(args))
                        logger.info(f"✅ Tool call succeeded on first try | {tool_name}")

                    except Exception as e:
                        logger.error(f"❌ Tool call failed: {e}")
                        raise e

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
                            continue

                    # Extract p_list and p_count from API response shape
                    if isinstance(parsed, dict):
                        if parsed.get("fallback_applied"):
                            fallback_applied = parsed.get("fallback_applied")
                        if "p_list" in parsed:
                            p_count = parsed.get("p_count", 0)
                            p_list = parsed.get("p_list", [])
                        else:
                            p_list = list(parsed.values())
                            p_count = len(p_list)
                    else:
                        p_list = parsed if isinstance(parsed, list) else []
                        p_count = len(p_list)

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
                        
                        # 1. Dynamically identify the subject using the LLM (no hardcoding)
                        subject_prompt = f"Identify the main subject of this query in 1-2 words (e.g., 'assets', 'complaints', 'work orders'): '{user_query}'"
                        subject_res = self.model.invoke([HumanMessage(content=subject_prompt)])
                        entity = self._get_content_str(subject_res).strip().lower()
                        if not entity or len(entity) > 30: # Safety fallback
                             entity = tool_name.lower()
                        
                        # 2. Add extra detail to the entity name (Cumulative logic for better detail)
                        if args:
                            if args.get("keyword"):
                                entity = f"{entity} matching '{args.get('keyword')}'"
                            if args.get("complaint_no"):
                                entity = f"{entity} '{args.get('complaint_no')}'"
                            if args.get("asset_tag_no"):
                                entity = f"{entity} '{args.get('asset_tag_no')}'"
                            if args.get("work_order"):
                                entity = f"{entity} '{args.get('work_order')}'"
                            if args.get("asset_type"):
                                entity = f"{entity} of type '{args.get('asset_type')}'"
                            if args.get("building"):
                                entity = f"{entity} in '{args.get('building')}'"
                            if args.get("floor"):
                                entity = f"{entity} on '{args.get('floor')}'"
                            if args.get("locality"):
                                entity = f"{entity} in locality '{args.get('locality')}'"
                            if args.get("division"):
                                entity = f"{entity} for division '{args.get('division')}'"
                            if args.get("discipline"):
                                entity = f"{entity} for discipline '{args.get('discipline')}'"
                            if args.get("trade_group"):
                                entity = f"{entity} in trade group '{args.get('trade_group')}'"
                            if args.get("status"):
                                entity = f"{entity} with status '{args.get('status')}'"
                            if args.get("priority"):
                                entity = f"{entity} with priority '{args.get('priority')}'"
                            if args.get("condition"):
                                entity = f"{entity} in '{args.get('condition')}' condition"
                            if args.get("tech"):
                                entity = f"{entity} assigned to '{args.get('tech')}'"
                            if args.get("category"):
                                entity = f"{entity} in category '{args.get('category')}'"
                            if args.get("contract"):
                                entity = f"{entity} under contract '{args.get('contract')}'"
                            if args.get("make"):
                                entity = f"{entity} made by '{args.get('make')}'"
                            if args.get("model"):
                                entity = f"{entity} model '{args.get('model')}'"
                            if args.get("serial_no"):
                                entity = f"{entity} with serial number '{args.get('serial_no')}'"
                            if args.get("is_snagged"):
                                entity = f"snagged {entity}"
                            if args.get("is_scraped"):
                                entity = f"scraped {entity}"
                        
                        # 4. Extract time context
                        time_kw, _ = extract_date_from_query(user_query)
                        time_context = f" for {time_kw}" if time_kw else ""
                                
                        msg = f"No {entity} found for your request{time_context}."
                        return msg, msg, messages

                    
                    display_count = total_for_count if total_for_count > len(p_list) else p_count

                    
                    #  call 2 -updated from 2 intents (count/list) to 3 intents (count/aggregate/list)
                    # ── Build combined query using previous human message for intent context ──
                    # ── Build combined query ONLY if previous AI response was a clarification ──
                    import re as _re
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

                    intent_msg = self.model.invoke([
                        HumanMessage(content=f"""
                        Classify this user query into one of three intents:
                        - "count"     → user wants ONLY a single total number
                                        (e.g. "how many assets exist?", "total complaints count", "how many complaints are open?")
                                        (e.g. "how many assets exist?", "total complaints count", "how many complaints are open?")
                        - "aggregate" → user wants a grouped summary or breakdown by category
                                        (e.g. "assets per division?", "breakdown by building",
                                        "complaints by priority", "summarize by status",
                                        (e.g. "assets per division?", "breakdown by building",
                                        "complaints by priority", "summarize by status",
                                        "group by floor and building", "compare by make or model")
                        - "list"      → user wants full records shown as a table
                                        (e.g. "show me assets", "list complaints", "get PPM records")
                        IMPORTANT RULES:
                        - "how many per X" or "count by X" or "breakdown by X" = aggregate (NOT count)
                        - "how many total" or "how many exist" with no grouping = count
                        - "show", "list", "display", "get", "fetch" = list
                        - "give me X", "show X", "get X" where X is a number = list (NOT count)
                          The number means a limit — user wants to SEE records, not count them.

                        Query: "{combined_query_for_intent}"

                        Reply with ONLY one word: count or aggregate or list
                        """)
                    ])
                    self._accumulate_tokens(intent_msg)

                    
                    # is_aggregate_query is the new 3rd intent
                    if not tool_was_aggregate:
                        intent = self._get_content_str(intent_msg).strip().lower()
                        is_count_query     = intent == "count"
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
                        messages.append(
                            HumanMessage(content=(
                                f"The user asked: '{user_query}'. "
                                f"The system found {display_count} records. "
                                "Write 1 friendly sentence confirming what was found and the total count. "
                                "Do NOT list individual records. Keep it concise."
                            ))
                        )
                         # CALL 3 — Large dataset context call (records=[] so should be small)
                        context_ai_msg = self.model.invoke(messages)
                        self._accumulate_tokens(context_ai_msg)
                        context_summary = self._get_content_str(context_ai_msg) or f"Found {display_count} records for your request."
                        # context_summary = _append_default_7days(context_summary, user_query)

                        context_summary = _append_explicit_today(context_summary, user_query)
                        logger.info("✅ Context summary generated for large dataset | context='%s'", context_summary[:80])

                        if fallback_applied:
                            fld = fallback_applied.get("field", "")
                            val = fallback_applied.get("value", "")
                            logger.info(f"🔄 Fallback applied (large dataset): {fld} = {val}")

                        large_dataset_response = json.dumps({
                            "context_summary": context_summary,
                            "records": p_list # full raw data sent directly to frontend
                        })
                        logger.info("✅ Large dataset JSON prepared: %d records", len(p_list))

                        self._log_query_summary(current_user_query)
                        return large_dataset_response, context_summary, messages

                    messages.append(
                        ToolMessage(
                            content=json.dumps({
                                "message": f"{display_count} records found",
                                "records_returned": len(p_list),
                                "total_count": display_count,
                                "displayed_count": len(p_list_for_model),
            
                                "records": [] if is_count_query else p_list_for_model
                            }),
                            tool_call_id=tool_call["id"]
                        )
                    )

                #  STEP 3 — Call model again to generate final answe
                if is_count_query:
                    logger.info("🔢 Sending count-only prompt to model")
                    messages.append(HumanMessage(content=self._build_final_prompt(
                        is_count_query,
                        is_aggregate_query,
                        user_query,
                        display_count,
                        p_list_for_model
                    )))

                elif is_aggregate_query:
                    logger.info("📊 Sending aggregate prompt to model")
                    messages.append(HumanMessage(content=self._build_final_prompt(
                    is_count_query,
                    is_aggregate_query,
                    user_query,
                    display_count,
                    p_list_for_model
                )))

                else:
                    logger.info("📋 Sending list prompt to model")
                    messages.append(HumanMessage(content=self._build_final_prompt(
                    is_count_query,
                    is_aggregate_query,
                    user_query,
                    display_count,
                    p_list_for_model
                )))

                 # CALL 4 — Final answer generation
                final_ai_msg = self.model.invoke(messages)
                self._accumulate_tokens(final_ai_msg)
                final_content = self._get_content_str(final_ai_msg)

                # FINAL SAFETY NET (NO EMPTY STRING EVER)

                if not final_content or str(final_content).strip() == "":
                    final_content = "No data records were found matching your request."
                    logger.info("final_ai_content is empty")

                # aggregate context summary same as count (one sentence)
                # because aggregate answer starts with a summary sentence
                if is_count_query:
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
                            graph_context = f"Here is the graph result for your query."
                            if fallback_applied:
                                fld = fallback_applied.get("field", "")
                                val = fallback_applied.get("value", "")
                                logger.info(f"🔄 Fallback applied (graph): {fld} = {val}")
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
                # final_content = _append_default_7days(final_content, user_query)
                # context_summary = _append_default_7days(context_summary, user_query)
                final_content = _append_explicit_today(final_content, user_query)
                context_summary = _append_explicit_today(context_summary, user_query)

                if fallback_applied:
                    fld = fallback_applied.get("field", "")
                    val = fallback_applied.get("value", "")
                    logger.info(f"🔄 Fallback applied (normal): {fld} = {val}")

                return final_content, context_summary, messages

            else:
                 # Model skipped tool — check if this is a data query that REQUIRES a tool
                # if the model skipped the tool, we need to inject a synthetic tool call and result so the model formats from live data


                user_query = ""
                for m in reversed(messages):
                    if isinstance(m, HumanMessage):
                        user_query = (m.content or "") if isinstance(m.content, str) else ""
                        break
                q = user_query.lower()
                data_patterns = ("how many", "list", "show me", "get ", "fetch ", "display",
                 "give me", "provide", "retrieve", "show", "tell me how many",
                 "all assets", "all complaints", "all bdm", "all ppm",
                 "all fa", "all sb", "all ppm")
                needs_bdm    = any(w in q for w in ("breakdown", "bdm", "corrective"))
                needs_assets = any(w in q for w in ("asset", "equipment", "barcode"))
                needs_ppm    = any(w in q for w in ("ppm", "preventive", "planned"))
                needs_fa     = any(w in q for w in ("fa", "facility audit", "audit", "pest control", "rodent"))
                needs_sb     = any(w in q for w in ("sb", "schedule based", "schedule-based", "environmental services", "landscaping"))

                if any(p in q for p in data_patterns) and (needs_bdm or needs_assets or needs_ppm or needs_fa or needs_sb):
                    if needs_fa:
                        tool_name = "FA"
                    elif needs_sb:
                        tool_name = "SB"
                    elif needs_bdm:
                        tool_name = "BDM"
                    elif needs_assets:
                        tool_name = "ASSETS"
                    else:
                        tool_name = "PPM"
                    logger.warning("⚠️ Model skipped tool for data query — forcing %s", tool_name)
                    tool_fn = self.tool_map[tool_name]
                    aggregate_keywords = ("by ", "per ", "group by", "breakdown", "summarize", "compare")

                    # ✅ Extract date keywords from query before forcing tool call
                    forced_date_from, forced_date_to = extract_date_from_query(user_query)
                    logger.info("📅 Forced tool date extraction | date_from=%s | date_to=%s", forced_date_from, forced_date_to)

                    # Extract keyword using helper
                    cleaned_kw = _clean_query_for_fallback(user_query)
                    generic_terms = {
                        "assets", "asset", "equipment", "equipments",
                        "ppm", "preventive", "planned", "preventive maintenance",
                        "bdm", "breakdown", "breakdowns", "complaint", "complaints", "failure", "failures",
                        "fa", "facility audit", "audit", "audits",
                        "sb", "schedule based", "schedule-based", "work order", "work orders", "task", "tasks"
                    }
                    if cleaned_kw and cleaned_kw.lower() in generic_terms:
                        cleaned_kw = None

                    args = {
                        "user_name": user_name,
                        "user_id": str(user_id) if user_id is not None else None,
                        "limit": None,
                        "is_aggregate": any(kw in user_query.lower() for kw in aggregate_keywords)
                    }
                    if cleaned_kw:
                        args["keyword"] = cleaned_kw

                    # ✅ Only add dates if found in query
                    if forced_date_from is not None:
                        args["date_from"] = forced_date_from
                    if forced_date_to is not None:
                        args["date_to"] = forced_date_to

                    logger.info("🔍 Calling forced tool | tool=%s | user_name=%s", tool_name, user_name)

                    fallback_applied = None
                    try:
                        tool_result = tool_fn.invoke(dict(args))
                        logger.info(f"✅ Forced tool call succeeded | {tool_name}")

                    except Exception as e:
                        logger.error(f"❌ Forced tool call failed: {e}")
                        raise e
                    
                    try:
                        parsed = json.loads(tool_result) if isinstance(tool_result, str) else tool_result
                    except json.JSONDecodeError:
                        parsed = {}
                     #handle indexed dict from cache same as normal path
                    if isinstance(parsed, dict):
                        if parsed.get("fallback_applied"):
                            fallback_applied = parsed.get("fallback_applied")
                    if isinstance(parsed, dict) and "p_list" in parsed:
                        p_list  = parsed.get("p_list", [])
                        p_count = parsed.get("p_count", len(p_list))
                    elif isinstance(parsed, dict):
                        p_list  = list(parsed.values())
                        p_count = len(p_list)
                    else:
                        p_list  = parsed if isinstance(parsed, list) else []
                        p_count = len(p_list)

                    total_for_count = p_count
                    if p_list and isinstance(p_list[0], dict):
                        for key in ("total_count", "total_count_over", "full_count", "overall_count"):
                            val = p_list[0].get(key)
                            if isinstance(val, (int, float)) and val >= 0:
                                total_for_count = int(val)
                                break

                    display_count = total_for_count if total_for_count > len(p_list) else p_count

                    if p_count == 0 and total_for_count == 0:
                        logger.info("📊 [FORCED] No records found for tool %s", tool_name)
                        self._log_query_summary(current_user_query)

                        # 1. Start with generic map
                        entity_map = {
                            "ASSETS": "assets",
                            "PPM": "PPM tasks",
                            "BDM": "breakdown records",
                            "FA": "complaints",
                            "SB": "service boards"
                        }
                        entity = entity_map.get(tool_name, "results")

                        # 2. Try to make it more dynamic from tool arguments
                        if args and args.get("keyword"):
                            entity = args.get("keyword")
                        elif args and args.get("asset_type"):
                            entity = args.get("asset_type")

                        # 3. Extract time context
                        time_context = ""
                        for kw in ["today", "yesterday", "this week", "last week", "this month", "last month", "this year", "last year"]:
                            if kw in user_query.lower():
                                time_context = f" for {kw}"
                                break

                        msg = f"No {entity} found{time_context} for the given query."
                        return msg, msg, messages
                    # Inject synthetic tool call + result so model formats from live data

                    fake_tool_id = "forced-" + tool_name.lower() + "-1"
                    synthetic_ai = AIMessage(content="", tool_calls=[{"name": tool_name, "id": fake_tool_id, "args": {"user_name": user_name}}])
                    messages.append(synthetic_ai)

                    #  CALL 5 — Intent check for FORCED path
                    #  updated to 3 intents same as CALL 2 above
                    # ── Build combined query using previous human message for intent context ──
                    # ── Build combined query ONLY if previous AI response was a clarification ──
                    import re as _re
                    clarification_markers = ["do you mean", "please clarify"]
                    previous_ai_was_clarification_forced = False
                    ai_messages_forced_list = [m for m in messages if isinstance(m, AIMessage)]
                    if ai_messages_forced_list:
                        last_ai_content_forced = self._get_content_str(ai_messages_forced_list[-1])
                        previous_ai_was_clarification_forced = any(
                            kw in last_ai_content_forced.lower()
                            for kw in clarification_markers
                        )

                    if previous_ai_was_clarification_forced:
                        human_messages_forced = [m for m in messages if isinstance(m, HumanMessage)]
                        previous_query_forced = ""
                        if len(human_messages_forced) >= 2:
                            prev_f = human_messages_forced[-2].content
                            previous_query_forced = prev_f if isinstance(prev_f, str) else ""
                        combined_query_forced = f"{previous_query_forced} {user_query}".strip()
                        logger.info(f"🔍 [FORCED] Intent classification (clarification reply) | combined='{combined_query_forced}'")
                    else:
                        combined_query_forced = user_query
                        logger.info(f"🔍 [FORCED] Intent classification (normal) | query='{combined_query_forced}'")
                    intent_msg = self.model.invoke([
                        HumanMessage(content=f"""
                        IMPORTANT: If the query asks only for a total (e.g., 'how many', 'total') and contains no grouping keywords like 'by' or 'per', reply with exactly: count
                        Classify this user query into one of three intents:
                        - "count"     → user wants ONLY a single total number
                                        (e.g. "how many assets exist?", "what is the total complaints count", "how many complaints are open?")
                        - "aggregate" → user wants a grouped summary or breakdown by category
                                        (e.g. "assets per division?", "breakdown by building",
                                        "complaints by priority", "summarize by status",
                                        "group by floor and building", "compare by make or model")
                        - "list"      → user wants full records shown as a table
                                        (e.g. "show me assets", "list complaints", "get PPM records")

                        IMPORTANT RULES:
                        - " per X" or "count by X" or "breakdown by X" = aggregate (NOT count)
                        - "how many total" or "how many exist" with no grouping = count
                        - "show", "list", "display", "get", "fetch" = list
                        - "give me X", "show X", "get X" where X is a number = list (NOT count)
                          The number means a limit — user wants to SEE records, not count them

                        Query: "{combined_query_forced}"

                        Reply with ONLY one word: count or aggregate or list
                        """)
                    ])
                    self._accumulate_tokens(intent_msg)

                    #  — 3 intents for forced path same as normal path
                    tool_was_aggregate = args.get("is_aggregate") is True
                    tool_has_groupby = bool(args.get("group_by_columns"))

                    if not tool_was_aggregate:
                        intent = self._get_content_str(intent_msg).strip().lower()
                        is_count_query     = intent == "count"
                        is_aggregate_query = intent == "aggregate"
                    else:
                        if tool_has_groupby:
                            logger.info("📊 [FORCED] Tool ran in aggregate mode WITH group_by → forcing AGGREGATE intent")
                            intent = "aggregate"
                            is_aggregate_query = True
                            is_count_query = False
                        else:
                            logger.info("🔢 [FORCED] Tool ran in aggregate mode WITHOUT group_by → treating as COUNT intent")
                            intent = "count"
                            is_aggregate_query = False
                            is_count_query = True
                    if is_count_query:
                        logger.info("🔢 Intent=COUNT [FORCED] | query='%s'", user_query)
                    elif is_aggregate_query:
                        logger.info("📊 Intent=AGGREGATE [FORCED] | query='%s'", user_query)  # ✅ ADDED
                    else:
                        logger.info("📋 Intent=LIST [FORCED] | query='%s'", user_query)

                    MAX_DISPLAY = 25
                    p_list_for_model = p_list if len(p_list) <= MAX_DISPLAY else p_list[:MAX_DISPLAY]
                    is_large_result = len(p_list) > MAX_DISPLAY

                    
                    #— aggregate excluded from large dataset path
                    if is_large_result and not is_count_query and not is_aggregate_query:
                        logger.info("📌 Large dataset (%d records) [FORCED]", len(p_list))

                        messages.append(
                            ToolMessage(
                                content=json.dumps({
                                    "message": f"{display_count} records found (large dataset)",
                                    "total_count": display_count,
                                    "records": []
                                }),
                                tool_call_id=fake_tool_id
                            )
                        )
                        messages.append(
                            HumanMessage(content=(
                                f"The user asked: '{user_query}'. "
                                f"The system found {display_count} records. "
                                "Write 1 friendly sentence confirming what was found and the total count. "
                                "Do NOT list individual records. Keep it concise."
                            ))
                        )
                        # CALL 6  Large dataset context call FORCED path
                        context_ai_msg = self.model.invoke(messages)
                        self._accumulate_tokens(context_ai_msg)
                        context_summary = self._get_content_str(context_ai_msg) or f"Found {display_count} records for your request."
                        context_summary = _append_explicit_today(context_summary, user_query)

                        if fallback_applied:
                            fld = fallback_applied.get("field", "")
                            val = fallback_applied.get("value", "")
                            logger.info(f"🔄 Fallback applied (forced large dataset): {fld} = {val}")

                        large_dataset_response = json.dumps({
                            "context_summary": context_summary,
                            "records": p_list
                        })

                        self._log_query_summary(current_user_query)
                        return large_dataset_response, context_summary, messages

                    messages.append(
                        ToolMessage(
                            content=json.dumps({
                                "message": f"{display_count} records found",
                                "records_returned": len(p_list),
                                "total_count": display_count,
                                "displayed_count": len(p_list_for_model),
                                "records": [] if is_count_query else p_list_for_model
                            }),
                            tool_call_id=fake_tool_id
                        )
                    )

                    #  CALL 7 Final answer generation FORCED path

                    if is_count_query:
                        logger.info("🔢 Sending count-only prompt to model")
                        messages.append(HumanMessage(content=self._build_final_prompt(
                            is_count_query,
                            is_aggregate_query,
                            user_query,
                            display_count,
                            p_list_for_model
                        )))
                    elif is_aggregate_query:
                        
                        messages.append(HumanMessage(content=self._build_final_prompt(
                        is_count_query,
                        is_aggregate_query,
                        user_query,
                        display_count,
                        p_list_for_model
                    )))

                        
                    else:
                        messages.append(HumanMessage(content=self._build_final_prompt(
                        is_count_query,
                        is_aggregate_query,
                        user_query,
                        display_count,
                        p_list_for_model
                    )))

                    final_ai_msg = self.model.invoke(messages)
                    self._accumulate_tokens(final_ai_msg)
                    content = self._get_content_str(final_ai_msg) or "No specific data could be retrieved for this query."
                    logger.info("✅ Response after forced tool call")                  
                    if is_count_query:
                        context_summary = content   
                        logger.info("🧠 [FORCED] Count context_summary='%s'", context_summary[:80])
                    elif is_aggregate_query:
                        first_line = content.split("\n")[0].strip()
                        context_summary = first_line if first_line else f"Found grouped summary with {display_count} rows."
                        logger.info("🧠 [FORCED] Aggregate context_summary='%s'", context_summary[:80])
                        if is_graph and tool_was_aggregate:  # ← BOTH conditions must be true
                            logger.info("📊 [GRAPH FORCED] Wrapping aggregate as graph JSON...")
                            graph_context = f"Here is the graph result for your query."
                            if fallback_applied:
                                fld = fallback_applied.get("field", "")
                                val = fallback_applied.get("value", "")
                                logger.info(f"🔄 Fallback applied (forced graph): {fld} = {val}")
                            graph_response = self.build_graph_response(graph_context, p_list_for_model)
                            return graph_response, context_summary, messages
                        
                                                    
                    else:
                        first_line = content.split("\n")[0].strip()
                        context_summary = first_line if first_line else f"Found {display_count} records for your request."
                        logger.info("🧠 [FORCED] List context_summary='%s'", context_summary[:80])

                    # ── Stash table data for two-step yes/no flow ──
                    if not is_count_query:
                        self._last_pending_table = p_list_for_model
                        logger.info("📋 [FORCED PATH] Stashed pending_table | records=%d", len(p_list_for_model))
                    else:
                        self._last_pending_table = None

                    self._log_query_summary(current_user_query)
                    entity = "data"

                    self._log_query_summary(current_user_query)
                    entity = "data"
                    if "asset" in content.lower():
                        entity = "assets"
                    elif "complaint" in content.lower():
                        entity = "complaints"
                    elif "ppm" in content.lower():
                        entity = "ppm tasks"

                    if is_graph and not is_aggregate_query :
                        content = (
                        f"Here are the results for your query:\n\n{content}\n\n"
                        f"**Graph not available for this query**\n"
                        f"To generate a chart, the data needs to be grouped by a category.\n"
                        f"Since your query *'{user_query}'* does not include any grouping or category, a graph cannot be created.\n\n"
                        f"**Tip:** Try modifying your question by adding a category (for example: by type, date, or status) so that I can generate a meaningful chart"

                        )
                    # content = _append_default_7days(content, user_query)
                    # context_summary = _append_default_7days(context_summary, user_query)
                    content = _append_explicit_today(content, user_query)
                    context_summary = _append_explicit_today(context_summary, user_query)

                    if fallback_applied:
                        fld = fallback_applied.get("field", "")
                        val = fallback_applied.get("value", "")
                        logger.info(f"🔄 Fallback applied (forced normal): {fld} = {val}")

                    return content, context_summary, messages
                    
                content = self._get_content_str(ai_msg)
                if not content or str(content).strip() == "":
                    content = "No matching records were found for the requested data."
                logger.info("✅ No tool call — direct response")
                self._log_query_summary(current_user_query)
                return content, content, messages

        except Exception as e:
            logger.error(f"❌ Query processing error: {e}", exc_info=True)
            raise

langchain_service = LangChainService()