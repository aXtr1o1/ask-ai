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

    response_format: Literal["TABLE", "BULLET_LIST", "NUMBERED_LIST", "GRAPH", "PLAIN_TEXT"] | None = Field(
        default=None,
        description=(
            "The format the answer should be presented in. "
            "Only populate for 'db_query' intent. "
            "Base this on the question TYPE (what is being asked) — you do not see the data. "
            "Leave null for 'general' and 'web_search' intents."
        )
    )

    user_specified_format: bool = Field(
        default=False,
        description=(
            "True ONLY if the user explicitly stated a format preference in their query. "
            "False if you chose the format autonomously based on question type."
        )
    )

    general_response: str | None = Field(
        default=None,
        description=(
            "Direct conversational answer for 'general' intent queries. "
            "Null for db_query and web_search."
        )
    )

    thought: str = Field(
        default="",
        description="Your internal reasoning and step-by-step thinking process before generating the final output. Always provide your complete thought process here."
    )

    ui_messages: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "A dictionary of short, human-readable UI sentences explaining each step of the pipeline. "
            "Required keys for db_query: 'understanding_success', 'analysis', 'analysis_success', "
            "'retrieval', 'retrieval_success', 'execution', 'execution_success', 'formatting'. "
            "Example 'analysis': 'Extracting location filters for the assets database...' "
            "Do not mention exact values or share sensitive data in any sentence."
        )
    )

