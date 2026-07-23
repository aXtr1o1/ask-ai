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
        description="A brief explanation of why you selected the specific modules, fields, and filter values based on the query."
    )

    modules: list[str] = Field(
        default_factory=list,
        description=(
            "FM database modules required to answer the query. "
            "Only from: assets, bdm, ppm, fa, sb."
        )
    )
    filter_fields: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description=(
            "Per-module field projection. "
            "Maps module → { FieldName: short description of why this field is needed }. "
            "Only include fields that exist in the module's metadata schema. "
            "These are the columns that will be retrieved and passed to the execution agent."
        )
    )
    filter_values: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description=(
            "Per-module pre-filter conditions. "
            "Maps module → { FieldName: value to filter on }. "
            "Only include values that are explicitly present in or directly implied by the query. "
            "These conditions narrow the retrieved records before analysis begins."
        )
    )
    thought: str = Field(
        default="",
        description="Your internal reasoning and step-by-step thinking process before generating the final output. Always provide your complete thought process here."
    )
