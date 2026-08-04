from pydantic import BaseModel, Field
from typing import TypedDict, Optional


# ── API Request ───────────────────────────────────────────────────────────────
class AdvanceAskRequest(BaseModel):
    query:      str = Field(..., description="The user's question or query")
    session_id: str = Field(..., description="Unique session identifier")


# ── API Response ──────────────────────────────────────────────────────────────
class AdvanceAskResponse(BaseModel):
    query_summary:      str | None = None   # always returned
    general_response:   str | None = None   # populated when intent = general
    web_search_summary: str | None = None   # populated when intent = web_search
    filter_fields:      dict       = {}     # populated when intent = db_query
    filter_values:      dict       = {}     # populated when intent = db_query


# ── Internal Pipeline State ───────────────────────────────────────────────────
# LangGraph shared memory — carries ONLY what one node needs to pass to the next.
# Thoughts, latency, and reasoning are already logged inside each agent.
# They do NOT need to travel through the shared state.
class AdvancePipelineState(TypedDict):
    # ── Input (set once by service.py) ────────────────────────────────────────
    query:      str
    session_id: str

    # ── Understanding Agent → routing + Analysis Agent ─────────────────────────
    intent:                str           # drives conditional edge in pipeline
    query_summary:         Optional[str] # passed to Analysis Agent as its input
    modules:               list          # passed to Analysis Agent for metadata loading
    response_format:       str           # for future formatting layer
    user_specified_format: bool          # for future formatting layer

    # ── Understanding Agent → Router (response fields) ─────────────────────────
    general_response:   Optional[str]    # returned when intent = general
    web_search_summary: Optional[str]    # returned when intent = web_search

    # ── Analysis Agent → Router (response fields) ──────────────────────────────
    filter_fields: dict                  # returned when intent = db_query
    filter_values: dict                  # returned when intent = db_query
    limit:         Optional[int]         # reserved for future retrieval layer