from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import logging

from app.api.advance.stream.stream_handler import run_query_stream

logger = logging.getLogger(__name__)

advance_router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    session_id: str = "default-session"

@advance_router.post("/query_stream")
def api_query_stream(request: QueryRequest):
    """
    Advance Ask AI streaming endpoint using Server-Sent Events (SSE) / NDJSON.
    This routes to the new high-performance multi-agent pipeline.
    """
    logger.info(f"Received Advance AI query stream request for session {request.session_id}")
    return StreamingResponse(
        run_query_stream(request.query, request.session_id), 
        media_type="application/x-ndjson"
    )
