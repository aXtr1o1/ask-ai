import json
import logging
import re
from app.services.langchain_helpers import _append_explicit_today
from app.services.keyword_match_context import search_context_prompt_block

logger = logging.getLogger('chatbot_app')

class LangChainResponseBuilderMixin:
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

