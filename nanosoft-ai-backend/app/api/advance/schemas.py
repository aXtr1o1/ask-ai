from pydantic import BaseModel, Field
from typing import TypedDict, Optional


# ── API Request ───────────────────────────────────────────────────────────────
class AdvanceAskRequest(BaseModel):
    query:      str = Field(..., description="The user's question or query")
    session_id: str = Field(..., description="Unique session identifier")
    user_name:  str = Field(default="", description="The user's name from frontend")
    user_id:    str = Field(default="", description="The user's ID from frontend")


# ── Internal Pipeline State ───────────────────────────────────────────────────
# LangGraph shared memory — carries ONLY what one node needs to pass to the next.
# Thoughts, latency, and reasoning are logged inside each agent — not stored here.
class AdvancePipelineState(TypedDict):

    # ── Input (set once by service.py) ────────────────────────────────────────
    query: str
    session_id: str
    user_name: str
    user_id: str

    # ── Understanding Agent output ───────────────────────────────────────────
    intent: str
    query_summary: Optional[str]
    modules: list
    response_format: str
    user_specified_format: bool
    general_response: Optional[str]
    web_search_summary: Optional[str]

    # ── Understanding Agent token usage ──────────────────────────────────────
    ua_token_usage: dict

    # ── Analysis Agent output ────────────────────────────────────────────────
    filter_fields: dict
    filter_values: dict
    limit: Optional[int]

    # ── Analysis Agent token usage ────────────────────────────────────────────
    aa_token_usage: dict

    # ── Retrieval + Preprocessing output ─────────────────────────────────────
    retrieved_data: dict

    # ── Execution Agent output ───────────────────────────────────────────────
    execution_result: Optional[dict]
    formatting_context: Optional[dict]

    # ── Execution Agent token usage ──────────────────────────────────────────
    ea_token_usage: dict

    # ── Formatting Agent output ──────────────────────────────────────────────
    formatted_result: Optional[dict]

    # ── Formatting Agent token usage ──────────────────────────────────────────
    fa_token_usage: dict

    # ── Final usage / billing ─────────────────────────────────────────────────
    total_tokens: int
    credits_used: float