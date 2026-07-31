"""
Analysis Agent — Data Shapes

This file holds ALL data structure definitions for the Analysis Agent.

  AnalysisOutput → Pydantic model the LLM is structured to produce.
                   Defines which modules to query, which fields to retrieve
                   (filter_fields), and which values to filter on (filter_values).

Used by:
  agent.py → _structured_llm.with_structured_output(AnalysisOutput)
"""
from pydantic import BaseModel, Field


# =============================================================================
# LLM OUTPUT SCHEMA — what the Analysis Agent produces
#
# Fields:
#   modules       → FM modules needed to answer the query
#   filter_fields → per module: { FieldName: description } — columns to retrieve
#   filter_values → per module: { FieldName: value } — conditions to filter rows
#
# Both filter_fields and filter_values are keyed by module name.
# The retrieval layer reads these directly to load and slice the data.
# =============================================================================
class AnalysisOutput(BaseModel):
    """Structured output from the Analysis Agent."""
    reasoning: str = Field(
        description="A brief explanation of why you chose these fields and filters for the query."
    )

    limit: int | None = Field(
        default=None,
        description=(
            "Maximum number of records to return if the user explicitly specifies a numeric limit "
            "(e.g. 'top 5', 'first 10'). Set to null if no specific count is requested."
        )
    )

    filter_fields: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description=(
            "Per-module field projection. "
            "Maps module → { FieldName: short description of why this field is needed }. "
            "Only include fields that exist in the module's schema. "
            "If unsure which fields are needed, leave this empty — the retrieval layer will fetch all fields."
        )
    )
    filter_values: dict[str, dict[str, str | list[str]]] = Field(
        default_factory=dict,
        description=(
            "Per-module pre-filter conditions. "
            "Maps module → { FieldName: value to filter on }. "
            "Only include values explicitly stated in the query. "
            "If unsure, leave this empty — the retrieval layer fetches all records."
        )
    )
