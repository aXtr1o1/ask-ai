"""
Understanding Agent — Data Shapes

  UnderstandingOutput → what the Understanding Agent produces.
                        Only intent classification and a cleaned query summary.
                        No module identification, no field extraction — that is
                        the Analysis Agent's responsibility.

Used by:
  agent.py → structured_llm.with_structured_output(UnderstandingOutput)
"""
from typing import Literal
from pydantic import BaseModel, Field


# =============================================================================
# LLM OUTPUT SCHEMA
#
# Fields:
#   intent          → classified query type (drives the pipeline branch)
#   query_summary   → clean, corrected restatement of the user query
#   general_response→ direct answer for 'general' intent; null otherwise
# =============================================================================
class UnderstandingOutput(BaseModel):
    """Structured output from the Understanding Agent."""

    intent: Literal["general", "db_query", "web_search"] = Field(
        description="Classified intent of the query."
    )
    query_summary: str = Field(
        description=(
            "Clean, standardised restatement of the user query. "
            "Correct spelling, resolve abbreviations, and restate in plain FM language. "
            "Preserve all specific values mentioned (building names, priorities, statuses, "
            "equipment types, dates, technician names) exactly as stated by the user."
        )
    )
    general_response: str | None = Field(
        default=None,
        description=(
            "Direct conversational answer for 'general' intent queries. "
            "Null for db_query and web_search."
        )
    )
