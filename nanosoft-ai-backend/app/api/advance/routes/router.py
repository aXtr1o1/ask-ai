import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.advance.schemas import AdvanceAskRequest
from app.api.advance.service.service import stream_advance_pipeline

logger = logging.getLogger("advance.router")

advance_router = APIRouter()


@advance_router.post(
    "/advance/ask-ai",
    summary     = "Advance Ask-AI Pipeline (SSE)",
    description = (
        "Streams the pipeline as Server-Sent Events (SSE).\n\n"
        "Stages: **Understanding Agent** always runs. "
        "**Analysis Agent** runs only when intent is `db_query`."
    ),
    tags=["advance"],
)
async def advance_ask_ai(request: AdvanceAskRequest) -> StreamingResponse:
    query      = request.query.strip()
    session_id = request.session_id.strip()

    logger.info("[advance/ask-ai] ▶ SSE REQUEST | session=%s | query=%s", session_id, query)

    return StreamingResponse(
        stream_advance_pipeline(query, session_id, request.user_name, request.user_id),
        media_type = "text/event-stream",
        headers    = {
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering if behind a proxy
        },
    )