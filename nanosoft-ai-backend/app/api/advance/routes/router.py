import logging

from fastapi import APIRouter, HTTPException

from app.api.advance.schemas import AdvanceAskRequest, AdvanceAskResponse
from app.api.advance.service.service import run_advance_pipeline

logger = logging.getLogger("advance.router")

advance_router = APIRouter()


@advance_router.post(
    "/advance/ask-ai",
    response_model = AdvanceAskResponse,
    summary        = "Advance Ask-AI Pipeline",
    description    = (
        "Runs the user query through the LangGraph pipeline:\n\n"
        "1. **Understanding Agent** — classifies intent and extracts a clean query summary.\n"
        "2. **Analysis Agent** *(db_query only)* — produces filter_fields + filter_values.\n\n"
        "For `general` and `web_search` intents the answer is returned immediately "
        "without hitting the Analysis Agent."
    ),
    tags=["advance"],
)
async def advance_ask_ai(request: AdvanceAskRequest) -> AdvanceAskResponse:
    query      = request.query.strip()
    session_id = request.session_id.strip()

    logger.info("[advance/ask-ai] ▶ NEW REQUEST | session=%s | query=%s", session_id, query)

    try:
        final_state = await run_advance_pipeline(query, session_id)
    except Exception as exc:
        logger.error("[advance/ask-ai] ❌ Pipeline error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}")

    intent = final_state.get("intent", "general")
    logger.info("[advance/ask-ai] ✔ Complete | intent=%s", intent)

    return AdvanceAskResponse(
        query_summary       = final_state.get("query_summary"),
        general_response    = final_state.get("general_response"),
        web_search_summary  = final_state.get("web_search_summary"),
        filter_fields       = final_state.get("filter_fields", {}),
        filter_values       = final_state.get("filter_values", {}),
    )