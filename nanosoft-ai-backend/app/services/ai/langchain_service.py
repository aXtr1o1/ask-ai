"""
services/ai/langchain_service.py
─────────────────────────────────
Core AI query processor — the heart of the chatbot.

4-Call Flow (every data query goes through this):
    CALL-1 → First model invoke: does LLM want to call a tool?
    CALL-2 → Intent classification: count / aggregate / list
    CALL-3 → Large dataset context: generate friendly summary for large results
    CALL-4 → Final answer: format the tool result into a user-facing response

Tool call paths:
    PATH A → LLM called a tool normally (CALL-1 returned tool_calls)
    PATH B → LLM skipped tool for a data query → forced tool call (fallback)
    PATH C → No tool needed → pure conversational response

Key concepts:
    - Tools are built per client and cached in _client_tools dict
    - context_summary is stored in lc_memory (short) — NOT full response
    - full response (with tables/JSON) is stored in history only
    - pending_table is stashed on self for main.py to pick up for two-step yes/no flow
"""

import logging
from typing import Any
import re as _re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.config import settings
from app.dynamic.tools.tool_builder import build_tools_for_client
from app.dynamic.service import get_conn, get_services_for_client
from app.services.ai.intent_classifier import classify_intent
import json

logger = logging.getLogger("services.ai.langchain_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


def extract_date_from_query(query: str):
    """
    Extract a date keyword from user query for the forced tool call path.

    Used in PATH B (forced tool call) when the LLM skips calling a tool
    but the query clearly has a date reference.

    Returns (date_from, date_to) keywords or (None, None) if no date found.
    """
    q = query.lower()
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
    else:
        return None, None


class LangChainService:
    def __init__(self):
        try:
            # Base LLM — tools are NOT bound here
            # Tools are bound per client in _get_model_and_tools()
            self._base_llm = ChatGoogleGenerativeAI(
                model=settings.GOOGLE_AI_MODEL,
                google_api_key=settings.GOOGLE_API_KEY
            )

            # Cache: { "client_name:user_id" → (model_with_tools, tool_map) }
            # Built once per client session, reused for all queries in that session
            self._client_tools: dict = {}

            # Stash for two-step yes/no table flow
            # After LLM asks "Would you like to see the table?", records are stored here
            # main.py checks this after each response and saves to session state
            self._last_pending_table = None

            logger.info("🚀 [LANGCHAIN] LangChainService initialized | mode=dynamic | no hardcoded tools")
        except Exception as e:
            logger.error("❌ [LANGCHAIN] Init failed | error=%s", e, exc_info=True)
            raise

    # ── TOOL MANAGEMENT ───────────────────────────────────────────────────────

    def _get_model_and_tools(self, client_name: str, user_id: int):
        """
        Get or build (model_with_tools, tool_map) for a client.

        Cached per client_name:user_id — built once, reused for all queries.
        On first call: loads services from DB, builds tools, binds to model.
        On subsequent calls: returns cached result immediately.

        Returns:
            model     → LLM with tools bound (use for all model invocations)
            tool_map  → { "ASSETS": tool, ... } for manual invocation
        """
        cache_key = f"{client_name}:{user_id}"

        if cache_key in self._client_tools:
            del self._client_tools[cache_key]
        if cache_key not in self._client_tools:
            logger.info("[LANGCHAIN] Building tools for new client | client_name=%s | user_id=%s", client_name, user_id)
            tools, tool_map = build_tools_for_client(client_name, user_id)

            if not tools:
                # No tools registered — model can only do conversational responses
                logger.warning("[LANGCHAIN] ⚠️ No tools found | client_name=%s | model will work without tools", client_name)
                model = self._base_llm
            else:
                # Bind tools so LLM knows which tools it can call
                model = self._base_llm.bind_tools(tools)

            self._client_tools[cache_key] = (model, tool_map)
            logger.info(
                "✅ [LANGCHAIN] Tools cached | client_name=%s | tools=%s",
                client_name, list(tool_map.keys()),
            )

        return self._client_tools[cache_key]

    # ── TOKEN TRACKING ────────────────────────────────────────────────────────

    def _accumulate_tokens(self, ai_response):
        """
        Accumulate token counts from each model call.
        Totals are logged at end of query and used for usage tracking.
        """
        if hasattr(ai_response, 'usage_metadata') and ai_response.usage_metadata:
            self._total_input_tokens  += ai_response.usage_metadata.get('input_tokens')  or 0
            self._total_output_tokens += ai_response.usage_metadata.get('output_tokens') or 0
            self._total_tokens        += ai_response.usage_metadata.get('total_tokens')  or 0

    def _log_query_summary(self, user_query: str):
        """Log final token usage summary for this query."""
        logger.info(
            "📊 [LANGCHAIN] Token summary | query='%s' | input=%d | output=%d | total=%d",
            user_query[:60],
            self._total_input_tokens,
            self._total_output_tokens,
            self._total_tokens,
        )

    # ── CONTENT HELPERS ───────────────────────────────────────────────────────

    def extract_chunk_text(self, chunk) -> str:
        """Extract text string from a model response chunk."""
        content = chunk.content
        if not content:
            return ""
        if isinstance(content, list):
            return content[0].get("text", "") if content else ""
        if isinstance(content, str):
            return content
        return str(content)

    def build_graph_response(self, context_summary: str, records: list) -> str:
        """
        Build a graph response JSON for the frontend chart renderer.

        Auto-detects label_key (string field) and value_key (numeric field)
        from the first record in the list.

        Returns JSON string with type="graph" so frontend knows to render a chart.
        """
        label_key = "label"
        value_key = "value"

        if records and isinstance(records[0], dict):
            keys = list(records[0].keys())
            for k in keys:
                val = records[0].get(k)
                if isinstance(val, (int, float)):
                    value_key = k
                else:
                    label_key = k

        graph_response = {
            "type":            "graph",
            "chart_type":      "bar",
            "context_summary": context_summary,
            "label_key":       label_key,
            "value_key":       value_key,
            "records":         records,
        }
        logger.info(
            "[LANGCHAIN] Graph response built | label_key=%s | value_key=%s | records=%d",
            label_key, value_key, len(records),
        )
        return json.dumps(graph_response)

    def _build_final_prompt(
        self,
        is_count_query: bool,
        is_aggregate_query: bool,
        user_query: str,
        display_count: int,
        p_list_for_model: list,
    ) -> str:
        """
        Build CALL-4 prompt — instructs LLM how to format the tool result.

        Three formats based on intent:
            count     → one sentence with total (no table)
            aggregate → 2-4 sentence insight + ask if user wants breakdown table
            list      → 2-3 sentence summary + ask if user wants full table
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
                "Do NOT render any table. Do NOT include any markdown table. "
                "End your response with exactly this line:\n"
                "**Would you like to see the detailed breakdown table for a better understanding?**"
            )
        else:
            return (
                f"USER QUERY: {user_query}\n"
                f"TOTAL RECORDS: {display_count}\n"
                f"DISPLAYED RECORDS: {len(p_list_for_model)}\n"
                f"DATA PREVIEW: {p_list_for_model}\n\n"
                "TASK: Act as a technical analyst. Summarize the findings in 2-3 friendly, "
                "grammatically professional sentences. Focus on synthesizing patterns. "
                "If the displayed records are fewer than the total found, explicitly mention "
                "this is a partial view of the total data. "
                "STRICT RULES:\n"
                "1. Do NOT start with 'Here are' or 'Here is'.\n"
                "2. Start with 'I found...', 'I've retrieved...', or 'Your search returned...'.\n"
                "3. Use NO markdown (no bold, no italics) in the summary text.\n"
                "4. Do NOT include a table.\n"
                "5. Use clear, active-voice grammar.\n\n"
                "FINAL LINE (MUST BE EXACT):\n"
                "**Would you like to see the full table for a better understanding?**"
            )

    # ── MAIN ENTRY POINT ──────────────────────────────────────────────────────

    async def process_query(
        self,
        messages:     list,
        user_name:    str  = None,   # client_name e.g. "poc"
        user_id:      str  = None,   # numeric user_id e.g. "1"
        session_id:   str  = None,
        is_graph:     bool = False,
    ) -> tuple[str, str, list]:
        """
        Main entry point for processing a user query.

        Args:
            messages:   full message history [SystemMessage, ...HumanMessage/AIMessage, HumanMessage]
            user_name:  client_name (same as client_name in DB)
            user_id:    user's numeric ID as string
            session_id: WebSocket session ID (for logging)
            is_graph:   True if frontend requested graph response

        Returns:
            (final_response_text, context_summary, messages)
            - final_response_text → what gets sent to frontend (may be JSON for tables/graphs)
            - context_summary     → short summary stored in lc_memory (prevents token bloat)
            - messages            → updated message history
        """
        try:
            if not user_name:
                raise ValueError("user_name (client_name) is required")

            # Normalize user_id to int
            try:
                uid = int(user_id) if user_id is not None else None
            except (ValueError, TypeError):
                uid = None

            if uid is None:
                raise ValueError("user_id is required and must be an integer")

            # user_name == client_name in the dynamic system
            client_name = user_name

            logger.info(
                "[LANGCHAIN] Processing query | client_name=%s | user_id=%s | session=%s | is_graph=%s",
                client_name, uid, session_id, is_graph,
            )

            # Reset token counters for this query
            self._total_input_tokens  = 0
            self._total_output_tokens = 0
            self._total_tokens        = 0

            # Get or build tools for this client (cached after first call)
            model, tool_map = self._get_model_and_tools(client_name, uid)
            logger.info("[LANGCHAIN] Available tools | client=%s | tools=%s", client_name, list(tool_map.keys()))

            # Extract the current user query from the end of message history
            current_user_query = ""
            for m in reversed(messages):
                if isinstance(m, HumanMessage):
                    current_user_query = (m.content or "") if isinstance(m.content, str) else ""
                    break

            # Log recent message context for debugging
            logger.info("[LANGCHAIN] Messages sent to model | total=%d", len(messages))
            for i, msg in enumerate(messages[-3:]):
                msg_type        = type(msg).__name__
                content_preview = (msg.content[:100] if isinstance(msg.content, str) else str(msg.content)[:100])
                logger.info("   [%d] %s: %s", i, msg_type, content_preview)

            # ══════════════════════════════════════════════════════════════════
            # CALL-1: First model invocation
            # LLM decides whether to call a tool or respond directly
            # ══════════════════════════════════════════════════════════════════
            logger.info("[LANGCHAIN] CALL-1 → First model invoke | client=%s", client_name)
            ai_msg = model.invoke(messages)
            self._accumulate_tokens(ai_msg)
            logger.info(
                "[LANGCHAIN] CALL-1 result | tool_calls=%s | tools=%s",
                bool(ai_msg.tool_calls),
                [tc['name'] for tc in ai_msg.tool_calls] if ai_msg.tool_calls else "none",
            )

            # ══════════════════════════════════════════════════════════════════
            # PATH A: LLM called a tool — normal flow
            # ══════════════════════════════════════════════════════════════════
            if ai_msg.tool_calls:
                messages.append(ai_msg)
                is_count_query     = False
                is_aggregate_query = False
                display_count      = 0
                p_list_for_model   = []

                for tool_call in ai_msg.tool_calls:
                    tool_name = tool_call["name"]
                    tool_fn   = tool_map.get(tool_name)

                    if tool_fn is None:
                        logger.error(
                            "❌ [LANGCHAIN] Unknown tool | tool_name=%s | available=%s",
                            tool_name, list(tool_map.keys()),
                        )
                        continue

                    # Inject system args — user_name and user_id are always set by us
                    # Never let the LLM control these — it could inject wrong values
                    if tool_call.get("args") is None:
                        tool_call["args"] = {}
                    args = dict(tool_call["args"])
                    args.pop("user_id", None)        # remove any LLM-provided user_id
                    args["user_name"] = client_name  # always use authenticated client_name
                    args["user_id"]   = str(uid)     # always use authenticated user_id

                    # Get current user query for limit override logic
                    user_query = ""
                    for m in reversed(messages):
                        if isinstance(m, HumanMessage):
                            user_query = (m.content or "") if isinstance(m.content, str) else ""
                            break

                    # Override limit for count queries — LLM sometimes sets limit for counts
                    count_patterns = ("how many", "total", "number of", "count of", "count ", "how many ")
                    if any(p in user_query.lower() for p in count_patterns) and args.get("limit") is not None:
                        logger.info("[LANGCHAIN] Count query detected — clearing limit=%s", args.get("limit"))
                        args["limit"] = None

                    # Override limit for list queries without explicit number
                    list_patterns = ("list", "show me", "get ", "fetch ", "display",
                                     "give me", "provide", "retrieve", "show ", "all ")
                    _has_number = bool(_re.search(r'\b\d+\b', user_query))
                    if any(p in user_query.lower() for p in list_patterns) and not _has_number:
                        logger.info("[LANGCHAIN] List query without number — clearing limit=%s", args.get("limit"))
                        args["limit"] = None

                    logger.info("[LANGCHAIN] Invoking tool | name=%s | args_keys=%s", tool_name, list(args.keys()))
                    logger.info("[LANGCHAIN] SP Payload | name=%s | payload=\n%s", tool_name, json.dumps(args, indent=2, default=str))

                    try:
                        tool_result = tool_fn.invoke(dict(args))
                        logger.info("✅ [LANGCHAIN] Tool call succeeded | name=%s", tool_name)
                    except Exception as e:
                        logger.error("❌ [LANGCHAIN] Tool call failed | name=%s | error=%s", tool_name, e)
                        raise e

                    # Parse tool result JSON
                    parsed = tool_result
                    if isinstance(tool_result, str):
                        try:
                            parsed = json.loads(tool_result)
                        except json.JSONDecodeError:
                            logger.warning("[LANGCHAIN] Tool returned non-JSON | name=%s", tool_name)
                            messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))
                            continue

                    # Extract p_list and p_count from result
                    if isinstance(parsed, dict):
                        if "p_list" in parsed:
                            p_count = parsed.get("p_count", 0)
                            p_list  = parsed.get("p_list", [])
                        else:
                            p_list  = list(parsed.values())
                            p_count = len(p_list)
                    else:
                        p_list  = parsed if isinstance(parsed, list) else []
                        p_count = len(p_list)

                    # Check for total_count_over field — SP may return total across all pages
                    total_for_count = p_count
                    if p_list and isinstance(p_list[0], dict):
                        for key in ("total_count", "total_count_over", "full_count", "overall_count"):
                            val = p_list[0].get(key)
                            if isinstance(val, (int, float)) and val >= 0:
                                total_for_count = int(val)
                                logger.info("[LANGCHAIN] Using total from row field '%s' = %s", key, total_for_count)
                                break

                    logger.info(
                        "[LANGCHAIN] Tool result parsed | name=%s | p_list=%d | p_count=%s | total=%s",
                        tool_name, len(p_list), p_count, total_for_count,
                    )

                    # Determine if this was an aggregate call based on args sent
                    tool_was_aggregate = args.get("is_aggregate") is True
                    tool_has_groupby   = bool(args.get("group_by_columns"))

                    # Override intent based on what the tool actually ran
                    if tool_was_aggregate:
                        if tool_has_groupby:
                            logger.info("[LANGCHAIN] Tool ran aggregate WITH group_by → intent=AGGREGATE")
                            is_aggregate_query = True
                            is_count_query     = False
                        else:
                            logger.info("[LANGCHAIN] Tool ran aggregate WITHOUT group_by → intent=COUNT")
                            is_aggregate_query = False
                            is_count_query     = True

                    # No records found — return early
                    if p_count == 0 and total_for_count == 0:
                        logger.info("[LANGCHAIN] No records found | tool=%s", tool_name)
                        self._log_query_summary(current_user_query)
                        return "No results found for the given query.", "No results found for the given query.", messages

                    display_count = total_for_count if total_for_count > len(p_list) else p_count

                    # ══════════════════════════════════════════════════════════
                    # CALL-2: Intent classification
                    # Only run if tool did not override intent already
                    # ══════════════════════════════════════════════════════════

                    # Check if previous AI message was a clarification
                    # If so, combine previous query + current reply for intent classification
                    clarification_markers = ["do you mean", "please clarify"]
                    previous_ai_was_clarification = False
                    ai_messages_list = [m for m in messages if isinstance(m, AIMessage)]
                    if ai_messages_list:
                        last_ai_content = ai_messages_list[-1].content or ""
                        previous_ai_was_clarification = any(
                            kw in last_ai_content.lower() for kw in clarification_markers
                        )

                    if previous_ai_was_clarification:
                        human_messages_list = [m for m in messages if isinstance(m, HumanMessage)]
                        previous_query = ""
                        if len(human_messages_list) >= 2:
                            prev = human_messages_list[-2].content
                            previous_query = prev if isinstance(prev, str) else ""
                        combined_query_for_intent = f"{previous_query} {user_query}".strip()
                    else:
                        combined_query_for_intent = user_query

                    if not tool_was_aggregate:
                        logger.info("[LANGCHAIN] CALL-2 → Intent classification | query='%s'", combined_query_for_intent[:80])
                        intent, intent_msg = classify_intent(model, combined_query_for_intent)
                        self._accumulate_tokens(intent_msg)
                        is_count_query     = intent == "count"
                        is_aggregate_query = intent == "aggregate"
                        logger.info("[LANGCHAIN] CALL-2 result | intent=%s", intent)
                    else:
                        intent = "count" if is_count_query else "aggregate"
                        logger.info("[LANGCHAIN] Skipping CALL-2 — tool already set intent=%s", intent)

                    # Max 25 records sent to model to avoid token overflow
                    MAX_DISPLAY      = 25
                    p_list_for_model = p_list if len(p_list) <= MAX_DISPLAY else p_list[:MAX_DISPLAY]
                    is_large_result  = len(p_list) > MAX_DISPLAY

                    # ══════════════════════════════════════════════════════════
                    # CALL-3: Large dataset context generation
                    # Only triggered when result > 25 records + not count/aggregate
                    # ══════════════════════════════════════════════════════════
                    if is_large_result and not is_count_query and not is_aggregate_query:
                        logger.info(
                            "[LANGCHAIN] CALL-3 → Large dataset | records=%d | client=%s",
                            len(p_list), client_name,
                        )
                        messages.append(ToolMessage(
                            content=json.dumps({
                                "message":     f"{display_count} records found (large dataset)",
                                "total_count": display_count,
                                "records":     [],
                            }),
                            tool_call_id=tool_call["id"],
                        ))
                        messages.append(HumanMessage(content=(
                            f"The user asked: '{user_query}'. "
                            f"The system found {display_count} records. "
                            "Write 1 friendly sentence confirming what was found and the total count. "
                            "Do NOT list individual records. Keep it concise."
                        )))
                        context_ai_msg  = model.invoke(messages)
                        self._accumulate_tokens(context_ai_msg)
                        context_summary = context_ai_msg.content or f"Found {display_count} records."
                        logger.info("[LANGCHAIN] CALL-3 result | context_summary='%s'", context_summary[:80])

                        # Return full records as JSON for frontend to render
                        large_dataset_response = json.dumps({
                            "context_summary": context_summary,
                            "records":         p_list,
                        })
                        self._log_query_summary(current_user_query)
                        return large_dataset_response, context_summary, messages

                    messages.append(ToolMessage(
                        content=json.dumps({
                            "message":          f"{display_count} records found",
                            "records_returned": len(p_list),
                            "total_count":      display_count,
                            "displayed_count":  len(p_list_for_model),
                            # Don't send records to model for count queries — saves tokens
                            "records":          [] if is_count_query else p_list_for_model,
                        }),
                        tool_call_id=tool_call["id"],
                    ))

                # ══════════════════════════════════════════════════════════════
                # CALL-4: Final answer generation
                # Formats the tool result into a user-facing response
                # ══════════════════════════════════════════════════════════════
                logger.info("[LANGCHAIN] CALL-4 → Final answer | intent=%s | display_count=%d", intent, display_count)
                messages.append(HumanMessage(content=self._build_final_prompt(
                    is_count_query, is_aggregate_query, user_query,
                    display_count, p_list_for_model,
                )))
                final_ai_msg = model.invoke(messages)
                self._accumulate_tokens(final_ai_msg)
                final_content = final_ai_msg.content
                logger.info("[LANGCHAIN] CALL-4 result | response_length=%d", len(final_content or ""))

                if not final_content or str(final_content).strip() == "":
                    final_content = "No results found for the given query."

                # Build context_summary — short version stored in lc_memory
                # This prevents token bloat from storing large table responses in memory
                if is_count_query:
                    context_summary = final_content
                    logger.info("[LANGCHAIN] context_summary=count_response | '%s'", context_summary[:80])
                elif is_aggregate_query:
                    lines = final_content.split("\n")
                    summary_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith("|")]
                    context_summary = " ".join(summary_lines) if summary_lines else f"Found grouped summary with {display_count} rows."
                    logger.info("[LANGCHAIN] context_summary=aggregate_summary | '%s'", context_summary[:80])

                    # Return graph JSON if frontend requested graph for aggregate result
                    if tool_was_aggregate and is_graph:
                        graph_response = self.build_graph_response("Here is the graph result for your query.", p_list_for_model)
                        self._log_query_summary(current_user_query)
                        return graph_response, context_summary, messages
                else:
                    lines = final_content.split("\n")
                    summary_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith("|")]
                    context_summary = " ".join(summary_lines) if summary_lines else f"Found {display_count} records."
                    logger.info("[LANGCHAIN] context_summary=list_summary | '%s'", context_summary[:80])

                # Stash pending table for two-step yes/no flow
                # main.py will save this to session state and clear after user replies
                if not is_count_query:
                    self._last_pending_table = p_list_for_model

                # Add graph unavailable message if frontend wants graph but query isn't aggregate
                if is_graph and not is_aggregate_query:
                    final_content = (
                        f"Here are the results for your query:\n\n{final_content}\n\n"
                        f"**Graph not available for this query**\n"
                        f"To generate a chart, the data needs to be grouped by a category.\n"
                        f"Since your query *'{user_query}'* does not include any grouping, a graph cannot be created.\n\n"
                        f"**Tip:** Try modifying your question by adding a category (for example: by type, date, or status)."
                    )

                self._log_query_summary(current_user_query)
                return final_content, context_summary, messages

            # ══════════════════════════════════════════════════════════════════
            # PATH B: LLM skipped tool — check if it should have called one
            # ══════════════════════════════════════════════════════════════════
            else:
                logger.warning(
                    "⚠️ [LANGCHAIN] Model did NOT call tools | available_tools=%s",
                    list(tool_map.keys()),
                )
                logger.info("[LANGCHAIN] Model response (no tool): %s", (ai_msg.content or "")[:100])

                # Extract user query
                user_query = ""
                for m in reversed(messages):
                    if isinstance(m, HumanMessage):
                        user_query = (m.content or "") if isinstance(m.content, str) else ""
                        break

                q = user_query.lower()
                data_patterns = ("how many", "list", "show me", "get ", "fetch ", "display",
                                 "give me", "provide", "retrieve", "show", "tell me how many", "all ")

                # Check if any tool keyword matches the query
                forced_tool_name = None

                # First check by tool key name directly
                for tool_key in tool_map.keys():
                    if tool_key.lower() in q:
                        forced_tool_name = tool_key
                        break

                # Then check routing_keywords from registry
                if forced_tool_name is None:
                    conn     = get_conn()
                    services = get_services_for_client(conn, client_name)
                    for svc in services:
                        keywords = svc.get("routing_keywords") or []
                        if any(kw.lower() in q for kw in keywords):
                            forced_tool_name = svc["service_key"].upper()
                            break

                # If a matching tool found AND query looks like a data query → force call it
                if forced_tool_name and any(p in q for p in data_patterns):
                    logger.warning(
                        "⚠️ [LANGCHAIN] Forcing tool call | tool=%s | query='%s'",
                        forced_tool_name, user_query[:80],
                    )

                    tool_fn = tool_map[forced_tool_name]
                    forced_date_from, forced_date_to = extract_date_from_query(user_query)
                    aggregate_keywords = ("by ", "per ", "group by", "breakdown", "summarize", "compare")

                    args = {
                        "user_name":    client_name,
                        "user_id":      str(uid),
                        "limit":        None,
                        "is_aggregate": any(kw in user_query.lower() for kw in aggregate_keywords),
                    }
                    if forced_date_from is not None:
                        args["date_from"] = forced_date_from
                    if forced_date_to is not None:
                        args["date_to"] = forced_date_to

                    logger.info("[LANGCHAIN] Forced tool args | tool=%s | args=%s", forced_tool_name, args)
                    logger.info("[LANGCHAIN] SP Payload (forced) | name=%s | payload=\n%s", forced_tool_name, json.dumps(args, indent=2, default=str))

                    try:
                        tool_result = tool_fn.invoke(dict(args))
                        logger.info("✅ [LANGCHAIN] Forced tool call succeeded | tool=%s", forced_tool_name)
                    except Exception as e:
                        logger.error("❌ [LANGCHAIN] Forced tool call failed | tool=%s | error=%s", forced_tool_name, e)
                        raise e

                    # Parse result same as PATH A
                    try:
                        parsed = json.loads(tool_result) if isinstance(tool_result, str) else tool_result
                    except json.JSONDecodeError:
                        parsed = {}

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

                    # Build synthetic AIMessage so ToolMessage has a valid tool_call_id
                    fake_tool_id = f"forced-{forced_tool_name.lower()}-1"
                    synthetic_ai = AIMessage(
                        content="",
                        tool_calls=[{"name": forced_tool_name, "id": fake_tool_id, "args": {"user_name": client_name}}],
                    )
                    messages.append(synthetic_ai)

                    # CALL-2 for forced path
                    logger.info("[LANGCHAIN] CALL-2 (forced path) → Intent classification")
                    tool_was_aggregate = args.get("is_aggregate") is True
                    tool_has_groupby   = bool(args.get("group_by_columns"))

                    if not tool_was_aggregate:
                        intent, intent_msg = classify_intent(model, user_query)
                        self._accumulate_tokens(intent_msg)
                        is_count_query     = intent == "count"
                        is_aggregate_query = intent == "aggregate"
                    else:
                        if tool_has_groupby:
                            is_aggregate_query = True
                            is_count_query     = False
                        else:
                            is_aggregate_query = False
                            is_count_query     = True

                    MAX_DISPLAY      = 25
                    p_list_for_model = p_list if len(p_list) <= MAX_DISPLAY else p_list[:MAX_DISPLAY]
                    is_large_result  = len(p_list) > MAX_DISPLAY

                    # CALL-3 for forced path (large dataset)
                    if is_large_result and not is_count_query and not is_aggregate_query:
                        logger.info("[LANGCHAIN] CALL-3 (forced path) → Large dataset | records=%d", len(p_list))
                        messages.append(ToolMessage(
                            content=json.dumps({
                                "message":     f"{display_count} records found (large dataset)",
                                "total_count": display_count,
                                "records":     [],
                            }),
                            tool_call_id=fake_tool_id,
                        ))
                        messages.append(HumanMessage(content=(
                            f"The user asked: '{user_query}'. "
                            f"The system found {display_count} records. "
                            "Write 1 friendly sentence confirming what was found and the total count."
                        )))
                        context_ai_msg  = model.invoke(messages)
                        self._accumulate_tokens(context_ai_msg)
                        context_summary = context_ai_msg.content or f"Found {display_count} records."
                        large_dataset_response = json.dumps({
                            "context_summary": context_summary,
                            "records":         p_list,
                        })
                        self._log_query_summary(current_user_query)
                        return large_dataset_response, context_summary, messages

                    messages.append(ToolMessage(
                        content=json.dumps({
                            "message":          f"{display_count} records found",
                            "records_returned": len(p_list),
                            "total_count":      display_count,
                            "displayed_count":  len(p_list_for_model),
                            "records":          [] if is_count_query else p_list_for_model,
                        }),
                        tool_call_id=fake_tool_id,
                    ))

                    # CALL-4 for forced path
                    logger.info("[LANGCHAIN] CALL-4 (forced path) → Final answer")
                    messages.append(HumanMessage(content=self._build_final_prompt(
                        is_count_query, is_aggregate_query, user_query,
                        display_count, p_list_for_model,
                    )))
                    final_ai_msg = model.invoke(messages)
                    self._accumulate_tokens(final_ai_msg)
                    content = final_ai_msg.content or "No results found for the given query."
                    logger.info("[LANGCHAIN] CALL-4 (forced path) result | length=%d", len(content))

                    if is_count_query:
                        context_summary = content
                    elif is_aggregate_query:
                        first_line      = content.split("\n")[0].strip()
                        context_summary = first_line if first_line else f"Found grouped summary with {display_count} rows."
                        if is_graph and tool_was_aggregate:
                            graph_response = self.build_graph_response("Here is the graph result for your query.", p_list_for_model)
                            return graph_response, context_summary, messages
                    else:
                        first_line      = content.split("\n")[0].strip()
                        context_summary = first_line if first_line else f"Found {display_count} records."

                    if not is_count_query:
                        self._last_pending_table = p_list_for_model
                    else:
                        self._last_pending_table = None

                    if is_graph and not is_aggregate_query:
                        content = (
                            f"Here are the results for your query:\n\n{content}\n\n"
                            f"**Graph not available for this query**\n"
                            f"To generate a chart, the data needs to be grouped by a category.\n"
                            f"Since your query *'{user_query}'* does not include any grouping, a graph cannot be created.\n\n"
                            f"**Tip:** Try modifying your question by adding a category."
                        )

                    self._log_query_summary(current_user_query)
                    return content, context_summary, messages

                # ══════════════════════════════════════════════════════════════
                # PATH C: Pure conversational — no tool needed
                # Handles greetings, definitions, general knowledge queries
                # ══════════════════════════════════════════════════════════════
                content = ai_msg.content
                if not content or str(content).strip() == "":
                    content = "No results found for the given query."
                logger.info("✅ [LANGCHAIN] PATH C → Conversational response | length=%d", len(content))
                self._log_query_summary(current_user_query)
                return content, content, messages

        except Exception as e:
            logger.error("❌ [LANGCHAIN] Query processing failed | error=%s", e, exc_info=True)
            raise


# Singleton — one instance shared across all WebSocket connections
langchain_service = LangChainService()