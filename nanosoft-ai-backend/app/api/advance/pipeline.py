import logging
from langgraph.graph import StateGraph, START, END

from app.api.advance.schemas import AdvancePipelineState
from app.api.advance.Understanding_Agent.agent import classify_query
from app.api.advance.Understanding_Agent.conversation_memory import conversation_memory
from app.api.advance.analysis.agent import analyze_query

logger = logging.getLogger("advance.pipeline")


def understanding_node(state: AdvancePipelineState) -> dict:
    result = classify_query(
        query            = state["query"],
        session_id       = state["session_id"],
        thought_callback = None,
    )
    logger.info("[Pipeline] ✔ understanding_node | intent=%s | modules=%s",
                result["intent"], result["modules"])
    return {
        "intent":                result["intent"],
        "query_summary":         result["query_summary"],
        "modules":               result["modules"],
        "response_format":       result.get("response_format", "PLAIN_TEXT"),
        "user_specified_format": result.get("user_specified_format", False),
        "general_response":      result.get("general_response"),
        "web_search_summary":    result.get("web_search_summary"),
    }


def analysis_node(state: AdvancePipelineState) -> dict:
    result = analyze_query(
        query_summary    = state["query_summary"] or state["query"],
        modules          = state["modules"],
        thought_callback = None,
        last_db_turn     = conversation_memory.get_last_db_turn(state["session_id"]),
    )
    logger.info("[Pipeline] ✔ analysis_node | modules=%s | filter_fields=%s",
                result["modules"], result["filter_fields"])
    return {
        "filter_fields": result["filter_fields"],
        "filter_values": result["filter_values"],
        "limit":         result.get("limit"),
    }


def route_after_understanding(state: AdvancePipelineState) -> str:
    intent = state.get("intent", "general")
    logger.info("[Pipeline] ↳ EDGE: intent=%s", intent)
    return "analysis_node" if intent == "db_query" else END


def _build_pipeline() -> StateGraph:
    builder = StateGraph(AdvancePipelineState)
    builder.add_node("understanding_node", understanding_node)
    builder.add_node("analysis_node",      analysis_node)
    builder.add_edge(START, "understanding_node")
    builder.add_conditional_edges(
        "understanding_node",
        route_after_understanding,
        {"analysis_node": "analysis_node", END: END},
    )
    builder.add_edge("analysis_node", END)
    return builder.compile()


advance_pipeline = _build_pipeline()
logger.info("[Pipeline] advance_pipeline compiled and ready")