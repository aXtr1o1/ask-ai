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
    query:      str
    session_id: str
    user_name:  str
    user_id:    str

    # ── Understanding Agent output ─────────────────────────────────────────────
    intent:                str           # drives conditional edge — "db_query" | "general" | "web_search"
    query_summary:         Optional[str] # refined question passed downstream
    modules:               list          # FM modules needed e.g. ["bdm", "ppm"]
    response_format:       str           # suggested format from Understanding Agent
    user_specified_format: bool          # True if user explicitly stated a format preference
    general_response:      Optional[str] # populated when intent = general
    web_search_summary:    Optional[str] # populated when intent = web_search

    # ── Analysis Agent output ──────────────────────────────────────────────────
    filter_fields: dict                  # { module: { field: description } }
    filter_values: dict                  # { field: value } for retrieval filtering
    limit:         Optional[int]         # optional row limit passed to retrieval

    # ── Retrieval + Preprocessing output ──────────────────────────────────────
    retrieved_data: dict                 # preprocessed records { module: { p_list, p_count } }

    # ── Execution Agent output ─────────────────────────────────────────────────
    execution_result:   Optional[dict]   # raw queue + step_results from run_execution()
    formatting_context: Optional[dict]   # resolved format, shape, final_answer from context_builder

    # ── Formatting Agent output ────────────────────────────────────────────────
    formatted_result:   Optional[dict]   # { response_type, layout, explanation, final_answer }