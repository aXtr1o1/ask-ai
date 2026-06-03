import json
import logging
import re
from langchain_core.messages import ToolMessage, HumanMessage, SystemMessage, AIMessage
from app.services.tool_payload_validator import normalize_tool_args
from app.services.langchain_helpers import (
    extract_date_from_query,
    _strip_redundant_table_offer,
    _enrich_entity_from_args,
    _append_explicit_today,
    _query_wants_list_display,
    _infer_intent_from_query
)
from app.services.keyword_match_context import (
    extract_from_tool_response,
    format_keyword_count_reply
)


logger = logging.getLogger('chatbot_app')

class LangChainToolPathsMixin:
    async def _handle_multi_tool_path(self, ai_msg, messages: list, user_name: str, user_id: str, current_user_query: str) -> tuple[str, str, list]:
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

    async def _handle_single_tool_path(self, ai_msg, messages: list, user_name: str, user_id: str, current_user_query: str, is_graph: bool = False) -> tuple[str, str, list]:
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

