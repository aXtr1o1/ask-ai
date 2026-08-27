"""
Response rendering for Normal ASK-AI.

Given the result of running one or more modules (app/services/langchain_service.py
_run_module), decide how to present it: a plain count sentence, an inline table,
a large-dataset direct render, a graph, or a multi-dataset summary — reusing the
same display-length threshold the app has always used.
"""
import json
import logging

from langchain_core.messages import HumanMessage

logger = logging.getLogger('chatbot_app')

# Records beyond this count are sent to the frontend directly instead of being
# summarized by the model (keeps prompts small; aggregate rows are always few).
MAX_DISPLAY_LIST = 25
MAX_DISPLAY_AGGREGATE = 500


class LangChainToolPathsMixin:
    def _handle_single_module(self, result: dict, user_query: str, is_graph: bool) -> tuple[str, str]:
        p_list = result["p_list"]
        display_count = result["display_count"]
        response_type = result["response_type"]
        is_aggregate = result["is_aggregate"]
        friendly_name = result["friendly_name"]

        if display_count == 0:
            self._last_pending_table = None
            msg = f"No {friendly_name} found for your request."
            return msg, msg

        # A graph requires grouped rows — only honor graph intent on aggregate results.
        if is_aggregate and (response_type == "graph" or is_graph):
            self._last_pending_table = None
            context_summary = "Here is the graph result for your query."
            return self.build_graph_response(context_summary, p_list), context_summary

        if response_type == "count" and not is_aggregate:
            self._last_pending_table = None
            ai_msg = self.model.invoke([HumanMessage(content=self._build_final_prompt(
                is_count_query=True, is_aggregate_query=False, user_query=user_query,
                display_count=display_count, p_list_for_model=[],
            ))])
            self._accumulate_tokens(ai_msg)
            content = self._get_content_str(ai_msg) or f"There are {display_count} {friendly_name}."
            return content, content

        max_display = MAX_DISPLAY_AGGREGATE if is_aggregate else MAX_DISPLAY_LIST
        p_list_for_model = p_list if len(p_list) <= max_display else p_list[:max_display]

        if len(p_list) > max_display and not is_aggregate:
            self._last_pending_table = None
            ai_msg = self.model.invoke([HumanMessage(content=(
                f"The user asked: '{user_query}'. The system found {display_count} {friendly_name} records. "
                "Write 1-2 friendly sentences summarizing this. Do NOT list individual records."
            ))])
            self._accumulate_tokens(ai_msg)
            context_summary = self._get_content_str(ai_msg) or f"Found {display_count} {friendly_name} for your request."
            large_dataset_response = json.dumps({
                "type": "large_dataset",
                "context_summary": context_summary,
                "records": p_list,
            })
            logger.info("📌 Large dataset (%d records) → sending raw JSON to frontend", len(p_list))
            return large_dataset_response, context_summary

        ai_msg = self.model.invoke([HumanMessage(content=self._build_final_prompt(
            is_count_query=False, is_aggregate_query=is_aggregate, user_query=user_query,
            display_count=display_count, p_list_for_model=p_list_for_model,
        ))])
        self._accumulate_tokens(ai_msg)
        final_content = self._get_content_str(ai_msg) or f"Found {display_count} {friendly_name} for your request."

        summary_lines = []
        for line in final_content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("|"):
                break
            if stripped:
                summary_lines.append(stripped)
        context_summary = " ".join(summary_lines) if summary_lines else f"Found {display_count} {friendly_name} for your request."

        # Stashed for chat_websocket_handler's yes/no "view as table" follow-up flow.
        self._last_pending_table = p_list_for_model

        return final_content, context_summary

    def _handle_multi_module(self, results: list, user_query: str) -> tuple[str, str]:
        non_empty = [r for r in results if r["display_count"] > 0]
        if not non_empty:
            msg = "No records were found for your request."
            return msg, msg

        lines = [f"- {r['friendly_name']}: {r['display_count']} records" for r in non_empty]
        ai_msg = self.model.invoke([HumanMessage(content=(
            f"The user asked: '{user_query}'.\n"
            "Datasets retrieved:\n" + "\n".join(lines) +
            "\n\nWrite a 2-3 sentence friendly summary naming each dataset and its record count."
        ))])
        self._accumulate_tokens(ai_msg)
        context_summary = self._get_content_str(ai_msg) or "Here are the results of your query."

        multiple_datasets_response = json.dumps({
            "type": "multiple_datasets",
            "context_summary": context_summary,
            "datasets": [
                {
                    "name": r["friendly_name"],
                    "records": r["p_list"],
                    "total_count": r["display_count"],
                }
                for r in non_empty
            ],
        })
        return multiple_datasets_response, context_summary
