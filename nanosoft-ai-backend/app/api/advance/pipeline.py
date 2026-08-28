import logging
from langgraph.graph import StateGraph, START, END

from app.api.advance.schemas import AdvancePipelineState
from app.api.advance.Understanding_Agent.agent import classify_query
from app.api.advance.Understanding_Agent.conversation_memory import conversation_memory
from app.api.advance.analysis.agent import analyze_query
from app.api.advance.retrieval.layer import run_retrieval_layer
from app.api.advance.preprocessing.layer import preprocess_records
from app.api.advance.execution_agent.agent.agent          import run_execution
from app.api.advance.execution_agent.output.context_builder import build_formatting_context
from app.api.advance.Formatting_agent.agent import format_response

logger = logging.getLogger("advance.pipeline")

def understanding_node(*state: AdvancePipelineState) -> dict:
    result = classify_query(
        query=state["query"],
        session_id=state["session_id"],
        thought_callback=None,
    )
    logger.info(
        "[Pipeline] ✔ understanding_node | intent=%s | modules=%s",
        result["intent"],
        result["modules"],
    )
    return {
        "intent": result["intent"],
        "query_summary": result["query_summary"],
        "modules": result["modules"],
        "response_format": result.get("response_format", "PLAIN_TEXT"),
        "user_specified_format": result.get("user_specified_format", False),
        "general_response": result.get("general_response"),
        "web_search_summary": result.get("web_search_summary"),
        "ua_token_usage": result.get("token_usage", {}),
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
        "limit": result.get("limit"),
        "aa_token_usage": result.get("token_usage", {}),
    }


def retrieval_node(state: AdvancePipelineState) -> dict:
    result = run_retrieval_layer(
        user_name=state.get("user_name", ""),
        user_id=state.get("user_id", ""),
        modules=state["modules"],
        filter_values=state.get("filter_values", {}),
        filter_fields=state.get("filter_fields", {}),
        limit=state.get("limit")
    )
    logger.info("[Pipeline] ✔ retrieval_node | retrieved for modules=%s", list(result.keys()))
    return {
        "retrieved_data": result
    }


def preprocessing_node(state: AdvancePipelineState) -> dict:
    retrieved_data = state.get("retrieved_data", {})
    if retrieved_data:
        preprocessed_data = preprocess_records(retrieved_data)
        logger.info("[Pipeline] ✔ preprocessing_node | cleaned data")
    else:
        preprocessed_data = {}
    return {
        "retrieved_data": preprocessed_data
    }


def execution_node(state: AdvancePipelineState) -> dict:
    """Run the Execution Agent: plan the tool queue (LLM once), then execute (no LLM)."""
    preprocessed_data  = state.get("retrieved_data", {})
    modules            = state.get("modules", [])
    question           = state.get("query_summary") or state.get("query", "")
    filter_fields      = state.get("filter_fields", {})
    response_format    = state.get("response_format", "PLAIN_TEXT")
    user_specified     = state.get("user_specified_format", False)

    logger.info("[Pipeline] → execution_node | question=%s | modules=%s",
                question[:100], modules)

    execution_result = run_execution(
        question          = question,
        filter_fields     = filter_fields,
        modules           = modules,
        filtered_records  = preprocessed_data,
        response_format   = response_format,
        user_specified    = user_specified,
    )

    # Build the formatting context — resolves format, shape, final answer
    formatting_context = build_formatting_context(
        execution_result = execution_result,
        suggested_format = response_format,
        user_specified   = user_specified,
    )

    logger.info("[Pipeline] ✔ execution_node | status=%s | format=%s",
                execution_result.get("status"), formatting_context.get("response_format"))

    return {
        "execution_result": execution_result,
        "formatting_context": formatting_context,
        "ea_token_usage": execution_result.get("token_usage", {}),
    }



def formatting_node(state: AdvancePipelineState) -> dict:
    formatting_context = state.get("formatting_context") or {}
    query_summary = state.get("query_summary") or state.get("query", "")

    logger.info(
        "[Pipeline] → formatting_node | format=%s",
        formatting_context.get("response_format", "?"),
    )

    formatted_result = format_response(
        formatting_context=formatting_context,
        query_summary=query_summary,
    )

    ua_tokens = int(
        (state.get("ua_token_usage") or {}).get("total_tokens", 0)
    )
    aa_tokens = int(
        (state.get("aa_token_usage") or {}).get("total_tokens", 0)
    )
    ea_tokens = int(
        (state.get("ea_token_usage") or {}).get("total_tokens", 0)
    )
    fa_tokens = int(
        (formatted_result.get("token_usage") or {}).get("total_tokens", 0)
    )

    total_tokens = (
        ua_tokens
        + aa_tokens
        + ea_tokens
        + fa_tokens
    )

    logger.info(
        "[Pipeline] 📊 TOKEN USAGE | UA=%s AA=%s EA=%s FA=%s TT=%s",
        ua_tokens,
        aa_tokens,
        ea_tokens,
        fa_tokens,
        total_tokens,
    )

    return {
        "formatted_result": formatted_result,
        "fa_token_usage": formatted_result.get("token_usage", {}),
        "total_tokens": total_tokens,
    }

def route_after_understanding(state: AdvancePipelineState) -> str:
    intent = state.get("intent", "general")
    logger.info("[Pipeline] ↳ EDGE: intent=%s", intent)
    return "analysis_node" if intent == "db_query" else END


def _build_pipeline() -> StateGraph:
    builder = StateGraph(AdvancePipelineState)
    builder.add_node("understanding_node", understanding_node)
    builder.add_node("analysis_node",      analysis_node)
    builder.add_node("retrieval_node",     retrieval_node)
    builder.add_node("preprocessing_node", preprocessing_node)
    builder.add_node("execution_node",     execution_node)
    builder.add_node("formatting_node",    formatting_node)
    builder.add_edge(START, "understanding_node")
    builder.add_conditional_edges(
        "understanding_node",
        route_after_understanding,
        {"analysis_node": "analysis_node", END: END},
    )
    builder.add_edge("analysis_node",      "retrieval_node")
    builder.add_edge("retrieval_node",     "preprocessing_node")
    builder.add_edge("preprocessing_node", "execution_node")
    builder.add_edge("execution_node",     "formatting_node")
    builder.add_edge("formatting_node",    END)
    return builder.compile()


advance_pipeline = _build_pipeline()
logger.info("[Pipeline] advance_pipeline compiled and ready")