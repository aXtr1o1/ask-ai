"""
LangChain Service — AI model with tool support
"""
import logging
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.config import settings
from app.tools.facility_tools import ASSETS, PPM, BDM

import json

logger = logging.getLogger("langchain_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


class LangChainService:
    def __init__(self):
        try:
            self.model = ChatGoogleGenerativeAI(
                model=settings.GOOGLE_AI_MODEL,
                google_api_key=settings.GOOGLE_API_KEY
            ).bind_tools([ASSETS, PPM, BDM])

            self.tool_map = {
                "ASSETS": ASSETS,
                "PPM": PPM,
                "BDM": BDM,
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


    # ──  return type is now tuple[str, str, list] used for the chat memory and the db memory .
    # ── (final_response_text, context_summary, messages)
    # ── context_summary = short sentence for ALL query types → used by main.py for lc_memory
    # ── final_response_text = full data response → used by main.py for history (DB)
    async def process_query(self, messages: list, user_name: str = None, session_id: str = None,is_graph: bool = False ) -> tuple[str, str, list]:
        try:
            
            # user_name is always from the frontend request; use it for all tool calls
            
            if not user_name:
                raise ValueError("user_name is required (from frontend request)")
            logger.info(f"💬 Processing query for user_name: {user_name}")

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
                                     "all assets", "all complaints", "all bdm", "all ppm")
                    if any(p in user_query.lower() for p in list_patterns):
                        old_limit = args.get("limit")
                        args["limit"] = None
                        logger.info("📋 List query detected — clearing limit=%s to enable large_dataset detection", old_limit)

                    tool_result = tool_fn.invoke(dict(args))

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

                    
                    if p_count == 0 and total_for_count == 0:
                        logger.info("📊 No records found for tool %s", tool_name)
                        self._log_query_summary(current_user_query)
                        return "No results found for the given query.", "No results found for the given query.", messages

                    
                    display_count = total_for_count if total_for_count > len(p_list) else p_count

                    
                    #  call 2 -updated from 2 intents (count/list) to 3 intents (count/aggregate/list)
                    intent_msg = self.model.invoke([
                        HumanMessage(content=f"""
                        Classify this user query into one of three intents:
                        - "count"     → user wants ONLY a single total number
                                        (e.g. "how many assets exist?", "total complaints count")
                        - "aggregate" → user wants a grouped summary or breakdown by category
                                        (e.g. "how many assets per division?", "breakdown by building",
                                        "total complaints by priority", "summarize by status",
                                        "group by floor and building", "compare by make or model")
                        - "list"      → user wants full records shown as a table
                                        (e.g. "show me assets", "list complaints", "get PPM records")

                        IMPORTANT RULES:
                        - "how many per X" or "count by X" or "breakdown by X" = aggregate (NOT count)
                        - "how many total" or "how many exist" with no grouping = count
                        - "show", "list", "display", "get", "fetch" = list

                        Query: "{user_query}"

                        Reply with ONLY one word: count or aggregate or list
                        """)
                    ])
                    self._accumulate_tokens(intent_msg)

                    
                    # is_aggregate_query is the new 3rd intent
                    intent = intent_msg.content.strip().lower()
                    is_count_query     = intent == "count"
                    is_aggregate_query = intent == "aggregate"  
                    # anything else = list (existing behaviour)

                    if is_count_query:
                        logger.info("🔢 Intent=COUNT — sending count only to model | query='%s'", user_query)
                    elif is_aggregate_query:
                        logger.info("📊 Intent=AGGREGATE — sending grouped summary to model | query='%s'", user_query)  # ✅ ADDED
                    else:
                        logger.info("📋 Intent=LIST — sending full records to model | query='%s'", user_query)

                    MAX_DISPLAY = 100
                    p_list_for_model = p_list if len(p_list) <= MAX_DISPLAY else p_list[:MAX_DISPLAY]
                    is_large_result = len(p_list) > MAX_DISPLAY
                    
                    
                    # If it is list query AND records > MAX_DISPLAY(100):
                    #   - send empty records to model, get context summary only
                    #   - return raw JSON directly to frontend (bypasses Step 3 model call)
                    if is_large_result and not is_count_query:
                        logger.info("📌 Large dataset (%d records) → sending raw JSON to frontend + context from model only", len(p_list))

                        messages.append(
                            ToolMessage(
                                content=json.dumps({
                                    "message": f"{display_count} records found (large dataset)",
                                    "total_count": display_count,
                                    "records": []   # no records sent to model
                                }),
                                tool_call_id=tool_call["id"]
                            )
                        )
                        messages.append(
                            HumanMessage(content=(
                                "Provide a brief context/summary of the above query result. "
                                "Do NOT list individual records. Keep it concise."
                            ))
                        )
                        context_ai_msg = self.model.invoke(messages)
                        context_summary = context_ai_msg.content or ""
                        logger.info("✅ Context summary generated for large dataset")

                        large_dataset_response = json.dumps({
                            "type": "large_dataset",
                            "total_count": display_count,
                            "records_count": len(p_list),
                            "context_summary": context_summary,
                            "records": p_list   # full raw data sent directly to frontend
                        })
                        logger.info("✅ Large dataset JSON prepared: %d records", len(p_list))
                        return large_dataset_response, messages
                                        

                    
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
                        context_summary = context_ai_msg.content or f"Found {display_count} records for your request."
                        logger.info("✅ Context summary generated for large dataset | context='%s'", context_summary[:80])

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
                    messages.append(HumanMessage(content=(
                        "Use the above tool results and give the final answer. "
                        "Reply in one crisp and friendly sentence using the total_count. "
                        "Include what was asked (e.g. 'There are X open complaints.'). "
                        "Do not render any table."
                    )))

                # aggregate gets its own clear prompt
                # tells the model exactly what the data is and how to render it
                elif is_aggregate_query:
                    logger.info("📊 Sending aggregate prompt to model")
                    messages.append(HumanMessage(content=(
                        f"The user asked: '{user_query}'. "
                        f"The system returned {display_count} grouped summary rows. "
                        "Summarize and render the results as a Markdown table."
                    )))
                
                else:
                    logger.info("📋 Sending table prompt to model")
                    messages.append(HumanMessage(content=(
                        f"The user asked: '{user_query}'. "
                        f"The system found {display_count} records and is displaying {len(p_list_for_model)} of them. "
                        "Write 1 friendly sentence summarizing what was found, then render all records as a Markdown table below it."
                    )))

                 # CALL 4 — Final answer generation
                final_ai_msg = self.model.invoke(messages)
                self._accumulate_tokens(final_ai_msg)
                final_content = final_ai_msg.content

                # FINAL SAFETY NET (NO EMPTY STRING EVER)

                if not final_content or str(final_content).strip() == "":
                    final_content = "No results found for the given query."
                    logger.info("final_ai_content is empty")

                # aggregate context summary same as count (one sentence)
                # because aggregate answer starts with a summary sentence
                if is_count_query:
                    context_summary = final_content
                    logger.info("🧠 Count query context_summary='%s'", context_summary[:80])
                elif is_aggregate_query:
                    #take first line as context summary
                    # full grouped table is too large for lc_memory
                    first_line = final_content.split("\n")[0].strip()
                    context_summary = first_line if first_line else f"Found grouped summary with {display_count} rows."
                    logger.info("🧠 Aggregate query context_summary='%s'", context_summary[:80])
                    if is_graph:
                        logger.info("📊 [GRAPH] Wrapping aggregate as graph JSON | records=%d", len(p_list_for_model))
                        graph_response = self.build_graph_response(context_summary, p_list_for_model)
                        self._log_query_summary(current_user_query)
                        return graph_response, context_summary, messages

                    
                else:
                    
                    first_line = final_content.split("\n")[0].strip()
                    context_summary = first_line if first_line else f"Found {display_count} records for your request."
                    logger.info("🧠 Small list context_summary='%s'", context_summary[:80])

                logger.info("✅ Final response generated after tool execution")
                self._log_query_summary(current_user_query)
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
                data_patterns = ("how many", "list", "count", "total", "number of", "show me", "get ", "fetch ")
                needs_bdm    = any(w in q for w in ("complaint", "bdm", "breakdown"))
                needs_assets = any(w in q for w in ("asset", "equipment"))
                needs_ppm    = any(w in q for w in ("ppm", "preventive", "planned", "scheduled"))

                if any(p in q for p in data_patterns) and (needs_bdm or needs_assets or needs_ppm):
                    tool_name = "BDM" if needs_bdm else ("ASSETS" if needs_assets else "PPM")
                    logger.warning("⚠️ Model skipped tool for data query — forcing %s", tool_name)
                    tool_fn = self.tool_map[tool_name]
                    args = {"user_name": user_name, "limit": None}
                    logger.info("🔍 Calling forced tool | tool=%s | user_name=%s", tool_name, user_name)
                    tool_result = tool_fn.invoke(dict(args))

                    try:
                        parsed = json.loads(tool_result) if isinstance(tool_result, str) else tool_result
                    except json.JSONDecodeError:
                        parsed = {}
                     #handle indexed dict from cache same as normal path
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
                        self._log_query_summary(current_user_query)
                        return "No results found for the given query.", "No results found for the given query.", messages
                    # Inject synthetic tool call + result so model formats from live data

                    fake_tool_id = "forced-" + tool_name.lower() + "-1"
                    synthetic_ai = AIMessage(content="", tool_calls=[{"name": tool_name, "id": fake_tool_id, "args": {"user_name": user_name}}])
                    messages.append(synthetic_ai)

                    #  CALL 5 — Intent check for FORCED path
                    #  updated to 3 intents same as CALL 2 above
                    intent_msg = self.model.invoke([
                        HumanMessage(content=f"""
                        Classify this user query into one of three intents:
                        - "count"     → user wants ONLY a single total number
                                        (e.g. "how many assets exist?", "total complaints count")
                        - "aggregate" → user wants a grouped summary or breakdown by category
                                        (e.g. "how many assets per division?", "breakdown by building",
                                        "total complaints by priority", "summarize by status",
                                        "group by floor and building", "compare by make or model")
                        - "list"      → user wants full records shown as a table
                                        (e.g. "show me assets", "list complaints", "get PPM records")

                        IMPORTANT RULES:
                        - "how many per X" or "count by X" or "breakdown by X" = aggregate (NOT count)
                        - "how many total" or "how many exist" with no grouping = count
                        - "show", "list", "display", "get", "fetch" = list

                        Query: "{user_query}"

                        Reply with ONLY one word: count or aggregate or list
                        """)
                    ])
                    self._accumulate_tokens(intent_msg)

                    #  — 3 intents for forced path same as normal path
                    intent = intent_msg.content.strip().lower()
                    is_count_query     = intent == "count"
                    is_aggregate_query = intent == "aggregate"  

                    if is_count_query:
                        logger.info("🔢 Intent=COUNT [FORCED] | query='%s'", user_query)
                    elif is_aggregate_query:
                        logger.info("📊 Intent=AGGREGATE [FORCED] | query='%s'", user_query)  # ✅ ADDED
                    else:
                        logger.info("📋 Intent=LIST [FORCED] | query='%s'", user_query)

                    MAX_DISPLAY = 100
                    p_list_for_model = p_list if len(p_list) <= MAX_DISPLAY else p_list[:MAX_DISPLAY]
                    is_large_result = len(p_list) > MAX_DISPLAY
                    
                     # Large dataset.
                    # Same logic as in the up  but for the forced path.
                    if is_large_result and not is_count_query:
                        logger.info("📌 Large dataset (%d records) [FORCED] → sending raw JSON to frontend + context from model only", len(p_list))

                        messages.append(
                            ToolMessage(
                                content=json.dumps({
                                    "message": f"{display_count} records found (large dataset)",
                                    "total_count": display_count,
                                    "records": []   # no records sent to model
                                }),
                                tool_call_id=fake_tool_id
                            )
                        )
                        messages.append(
                            HumanMessage(content=(
                                "Provide a brief context/summary of the above query result. "
                                "Do NOT list individual records. Keep it concise."
                            ))
                        )
                        context_ai_msg = self.model.invoke(messages)
                        context_summary = context_ai_msg.content or ""
                        logger.info("✅ Context summary generated for large dataset [FORCED]")

                        return json.dumps({
                            "type": "large_dataset",
                            "total_count": display_count,
                            "records_count": len(p_list),
                            "context_summary": context_summary,
                            "records": p_list   # full raw data sent directly to frontend
                        }), messages

                    
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
                        context_summary = context_ai_msg.content or f"Found {display_count} records for your request."

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
                        messages.append(HumanMessage(content=(
                            "Use the above tool results and give the final answer. "
                            "Reply in one crisp and friendly sentence using the total_count. "
                            "Do not render any table."
                        )))
                    elif is_aggregate_query:
                        
                        messages.append(HumanMessage(content=(
                            f"The user asked: '{user_query}'. "
                            f"The system returned {display_count} grouped summary rows. "
                            "Summarize and render the results as a Markdown table."
                        )))
                        
                    else:
                        messages.append(HumanMessage(content=(
                            f"The user asked: '{user_query}'. "
                            f"The system found {display_count} records and is displaying {len(p_list_for_model)} of them. "
                            "Write 1 friendly sentence summarizing what was found, then render all records as a Markdown table below it."
                        )))

                    final_ai_msg = self.model.invoke(messages)
                    self._accumulate_tokens(final_ai_msg)
                    content = final_ai_msg.content or "No results found for the given query."
                    logger.info("✅ Response after forced tool call")

                  
                    if is_count_query:
                        context_summary = content
                        logger.info("🧠 [FORCED] Count context_summary='%s'", context_summary[:80])
                    elif is_aggregate_query:
                        
                        first_line = content.split("\n")[0].strip()
                        context_summary = first_line if first_line else f"Found grouped summary with {display_count} rows."
                        logger.info("🧠 [FORCED] Aggregate context_summary='%s'", context_summary[:80])
                        if is_graph:
                            logger.info("📊 [GRAPH FORCED] Wrapping aggregate as graph JSON | records=%d", len(p_list_for_model))
                            graph_response =self.build_graph_response(context_summary, p_list_for_model)
                            self._log_query_summary(current_user_query)
                            return graph_response, context_summary, messages

                        
                    else:
                        first_line = content.split("\n")[0].strip()
                        context_summary = first_line if first_line else f"Found {display_count} records for your request."
                        logger.info("🧠 [FORCED] List context_summary='%s'", context_summary[:80])

                    self._log_query_summary(current_user_query)
                    return content, context_summary, messages

                
                content = ai_msg.content
                if not content or str(content).strip() == "":
                    content = "No results found for the given query."
                logger.info("✅ No tool call — direct response")
                self._log_query_summary(current_user_query)
                return content, content, messages

        except Exception as e:
            logger.error(f"❌ Query processing error: {e}", exc_info=True)
            raise

langchain_service = LangChainService()