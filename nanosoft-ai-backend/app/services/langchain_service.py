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
            # In test/CI environments there may be no valid API key.
            # Defer hard failure until the model is actually used.
            self.model = None

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
                    user_query = self._extract_user_query_from_messages(messages)

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
                        logger.info("📋 List query detected — clearing limit=%s", old_limit)

                    tool_result = tool_fn.invoke(dict(args))

                    p_list, p_count, total_for_count = self._process_tool_result_data(tool_result, tool_name)

                    # If tool result couldn't be parsed, skip to next tool
                    if p_count == 0 and total_for_count == 0 and not p_list:
                        # Check if this is a parsing error rather than empty results
                        if isinstance(tool_result, str) and not tool_result.strip().startswith('{'):
                            messages.append(
                                ToolMessage(content=tool_result, tool_call_id=tool_call["id"])
                            )
                            continue
                    # ── If tool actually ran in aggregate mode → force aggregate intent
                    # This overrides whatever the intent classifier says later
                    tool_was_aggregate = args.get("is_aggregate") is True
                    if tool_was_aggregate:
                        logger.info("📊 Tool ran in aggregate mode → forcing AGGREGATE intent (skipping classifier)")
                        is_aggregate_query = True
                        is_count_query = False

                    
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
                         "how many per X" or "count by X" or "breakdown by X" = aggregate (NOT count)
                        - "how many total" or "how many exist" with no grouping = count
                        - "show", "list", "display", "get", "fetch" = list
                        - "give me X", "show X", "get X" where X is a number = list (NOT count)
                          The number means a limit — user wants to SEE records, not count them.
                        

                        Query: "{user_query}"

                        Reply with ONLY one word: count or aggregate or list
                        """)
                    ])
                    self._accumulate_tokens(intent_msg)

                    
                    # is_aggregate_query is the new 3rd intent
                    if not tool_was_aggregate:
                        intent = self._classify_query_intent(user_query)
                        is_count_query     = intent == "count"
                        is_aggregate_query = intent == "aggregate"
                    else:
                        intent = "aggregate"  # already forced above

                    if is_count_query:
                        logger.info("🔢 Intent=COUNT — sending count only to model | query='%s'", user_query)
                    elif is_aggregate_query:
                        logger.info("📊 Intent=AGGREGATE — sending grouped summary to model | query='%s'", user_query)
                    else:
                        logger.info("📋 Intent=LIST — sending full records to model | query='%s'", user_query)

                    MAX_DISPLAY = 100
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
                        # ── Only build graph if tool actually ran in aggregate mode ──
                        if tool_was_aggregate:
                            logger.info("📊 [GRAPH] Wrapping aggregate as graph JSON | records=%d", len(p_list_for_model))
                            graph_response = self.build_graph_response(context_summary, p_list_for_model)
                            self._log_query_summary(current_user_query)
                            return graph_response, context_summary, messages
                        else:
                            logger.warning("⚠️ [GRAPH] Intent=AGGREGATE but tool ran in RAW mode — skipping graph, returning text")

                    
                else:
                    
                    first_line = final_content.split("\n")[0].strip()
                    context_summary = first_line if first_line else f"Found {display_count} records for your request."
                    logger.info("🧠 Small list context_summary='%s'", context_summary[:80])

                logger.info("✅ Final response generated after tool execution")
                self._log_query_summary(current_user_query)
                entity = "data"
                if "asset" in final_content.lower():
                    entity = "assets"
                elif "complaint" in final_content.lower():
                    entity = "complaints"
                elif "ppm" in final_content.lower():
                    entity = "ppm tasks"

                if is_graph and not is_aggregate_query:
                    final_content = (
                        f"Here are the results for your query:\n\n{final_content}\n\n"
                        f"**Graph not available for this query**\n"
                        f"To generate a chart, the data needs to be grouped by a category.\n"
                        f"Since your query *'{user_query}'* does not include any grouping or category, a graph cannot be created.\n\n"
                        f"**Tip:** Try modifying your question by adding a category (for example: by type, date, or status) so that I can generate a meaningful chart"

                    )
                return final_content, context_summary, messages

            else:
                # tells the model exactly what the data is and how to render it


                user_query = self._extract_user_query_from_messages(messages)
                q = user_query.lower()
                data_patterns = ("how many", "list", "count", "total", "number of", "show me", "get ", "fetch ")
                needs_bdm    = any(w in q for w in ("complaint", "bdm", "breakdown"))
                needs_assets = any(w in q for w in ("asset", "equipment"))
                needs_ppm    = any(w in q for w in ("ppm", "preventive", "planned", "scheduled"))

                if any(p in q for p in data_patterns) and (needs_bdm or needs_assets or needs_ppm):
                    tool_name = "BDM" if needs_bdm else ("ASSETS" if needs_assets else "PPM")
                    logger.warning("⚠️ Model skipped tool for data query — forcing %s", tool_name)
                    tool_fn = self.tool_map[tool_name]
                    aggregate_keywords = ("by ", "per ", "group by", "breakdown", "summarize", "compare")
                    args = {
                        "user_name": user_name,
                        "limit": None,
                        "is_aggregate": any(kw in user_query.lower() for kw in aggregate_keywords)
                    }
                    logger.info("🔍 Calling forced tool | tool=%s | user_name=%s", tool_name, user_name)
                    tool_result = tool_fn.invoke(dict(args))

                    p_list, p_count, total_for_count = self._process_tool_result_data(tool_result, tool_name)

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
                        - "give me X", "show X", "get X" where X is a number = list (NOT count)
                          The number means a limit — user wants to SEE records, not count them
                          
                        Query: "{user_query}"

                        Reply with ONLY one word: count or aggregate or list
                        """)
                    ])
                    self._accumulate_tokens(intent_msg)

                    #  — 3 intents for forced path same as normal path
                    tool_was_aggregate = args.get("is_aggregate") is True
                    if not tool_was_aggregate:
                        intent = self._classify_query_intent(user_query)
                        is_count_query     = intent == "count"
                        is_aggregate_query = intent == "aggregate"
                    else:
                        intent = "aggregate"
                        is_aggregate_query = True
                        is_count_query = False
                    if is_count_query:
                        logger.info("🔢 Intent=COUNT [FORCED] | query='%s'", user_query)
                    elif is_aggregate_query:
                        logger.info("📊 Intent=AGGREGATE [FORCED] | query='%s'", user_query)  # ✅ ADDED
                    else:
                        logger.info("📋 Intent=LIST [FORCED] | query='%s'", user_query)

                    MAX_DISPLAY = 100
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
                            # ── Only build graph if tool actually ran in aggregate mode ──
                            tool_was_aggregate = args.get("is_aggregate") is True
                            if tool_was_aggregate:
                                logger.info("📊 [GRAPH FORCED] Wrapping aggregate as graph JSON | records=%d", len(p_list_for_model))
                                graph_response = self.build_graph_response(context_summary, p_list_for_model)
                                self._log_query_summary(current_user_query)
                                return graph_response, context_summary, messages
                            else:
                                logger.warning("⚠️ [GRAPH FORCED] Intent=AGGREGATE but tool ran in RAW mode — skipping graph, returning text")                            
                                                    
                    else:
                        first_line = content.split("\n")[0].strip()
                        context_summary = first_line if first_line else f"Found {display_count} records for your request."
                        logger.info("🧠 [FORCED] List context_summary='%s'", context_summary[:80])

                    self._log_query_summary(current_user_query)
                    entity = "data"
                    if "asset" in content.lower():
                        entity = "assets"
                    elif "complaint" in content.lower():
                        entity = "complaints"
                    elif "ppm" in content.lower():
                        entity = "ppm tasks"

                    if is_graph and not is_aggregate_query:
                        content = (
                        f"Here are the results for your query:\n\n{content}\n\n"
                        f"**Graph not available for this query**\n"
                        f"To generate a chart, the data needs to be grouped by a category.\n"
                        f"Since your query *'{user_query}'* does not include any grouping or category, a graph cannot be created.\n\n"
                        f"**Tip:** Try modifying your question by adding a category (for example: by type, date, or status) so that I can generate a meaningful chart"

                        )
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