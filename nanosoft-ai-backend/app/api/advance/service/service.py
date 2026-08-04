import logging
import asyncio

from app.api.advance.pipeline import advance_pipeline
from app.api.advance.Understanding_Agent.conversation_memory import conversation_memory

logger = logging.getLogger("advance.service")


def _build_initial_state(query: str, session_id: str) -> dict:
    return {
        # Input
        "query":                 query,
        "session_id":            session_id,
        # Understanding Agent defaults
        "intent":                "",
        "query_summary":         None,
        "modules":               [],
        "response_format":       "PLAIN_TEXT",
        "user_specified_format": False,
        "general_response":      None,
        "web_search_summary":    None,
        # Analysis Agent defaults
        "filter_fields":         {},
        "filter_values":         {},
        "limit":                 None,
    }


def _store_conversation_turn(
    session_id:  str,
    query:       str,
    final_state: dict,
    intent:      str,
) -> None:
    try:
        conversation_memory.add_turn(
            session_id       = session_id,
            user_query       = query,
            query_summary    = final_state.get("query_summary") or query,
            intent           = intent,
            modules          = final_state.get("modules", []),
            filter_fields    = final_state.get("filter_fields", {}),
            filter_values    = final_state.get("filter_values", {}),
            general_response = final_state.get("general_response"),
        )
    except Exception as exc:
        logger.warning("[service] Memory store failed: %s", exc)


async def run_advance_pipeline(query: str, session_id: str) -> dict:
    initial_state = _build_initial_state(query, session_id)

    final_state = await asyncio.to_thread(
        advance_pipeline.invoke,
        initial_state,
    )

    intent = final_state.get("intent", "general")
    _store_conversation_turn(session_id, query, final_state, intent)

    return final_state