"""
Understanding Agent — Data Shapes

  UnderstandingOutput → what the Understanding Agent produces.

  Fields:
    intent          → classified query type  (drives pipeline branching)
    query_summary   → clean, corrected restatement of the user query
    modules         → FM modules relevant to the query  (db_query only)
    general_response→ direct answer for 'general' intent; null otherwise

Used by:
    agent.py  →  structured_llm.with_structured_output(UnderstandingOutput)
"""
from typing import Literal
from pydantic import BaseModel, Field


# =============================================================================
# LLM OUTPUT SCHEMA
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
            "equipment types, dates, technician names) exactly as stated by the user. "
            "This summary is the only information the Analysis Agent will receive, "
            "so it must be complete enough for the next stage to act on without seeing "
            "the original query."
        )
    )

    modules: list[str] = Field(
        default_factory=list,
        description=(
            "FM database modules required to answer this query. "
            "Only populate for 'db_query' intent. "
            "Valid values: assets, bdm, ppm, fa, sb. "
            "Leave empty for 'general' and 'web_search' intents."
        )
    )

    general_response: str | None = Field(
        default=None,
        description=(
            "Direct conversational answer for 'general' intent queries. "
            "Null for db_query and web_search."
        )
    )
