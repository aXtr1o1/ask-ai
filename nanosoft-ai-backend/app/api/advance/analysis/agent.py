"""
FM Analysis Agent

Receives the Understanding Agent summary (db_query only) and decides:
  - Which modules to query
  - Which fields to retrieve from each module (filter_fields)
  - Which values to pre-filter on per module (filter_values)

How metadata feeds the LLM:
  MODULE_SCHEMAS from metadata.py is serialized into JSON and embedded
  in the system prompt (see analysis/prompt.py → get_system_prompt).
  The LLM reads the full field schema directly and reasons from it.
  No hardcoded field selection rules.

Flow:
  Understanding Agent output (db_query only)
    → LLM with structured output (AnalysisOutput)
    → Validate against MODULE_SCHEMAS (strip hallucinations)
    → Merge standard context fields
    → Return { modules, filter_fields, filter_values }
"""
import logging

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.api.advance.analysis.schemas import AnalysisOutput
from app.api.advance.analysis.prompt import get_system_prompt
from app.api.advance.analysis.metadata import MODULE_SCHEMAS

logger = logging.getLogger("advance.analysis")

# System prompt built once at startup — MODULE_SCHEMAS is static
_SYSTEM_PROMPT = get_system_prompt()


# =============================================================================
# MAIN FUNCTION: analyze_query
# =============================================================================
def analyze_query(query_summary: str) -> dict:
    """
    Run the Analysis Agent on a cleaned query summary.
    This should ONLY be called if the intent is 'db_query'.

    Returns:
      {
        "modules":       [list of modules],
        "filter_fields": { module: { field: description } },
        "filter_values": { module: { field: value } },
      }
    """
    # -------------------------------------------------------------------------
    # Analysis Agent LLM
    # Reads the query summary + full MODULE_SCHEMAS from the prompt.
    # Outputs: modules + filter_fields + filter_values.
    # -------------------------------------------------------------------------
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,
        thinking_budget=1024,  # internal reasoning tokens to select correct fields and filter values
    )
    structured_llm = llm.with_structured_output(AnalysisOutput)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=query_summary),
    ]
    response = structured_llm.invoke(messages)

    # -------------------------------------------------------------------------
    # Step 3: Validate — strip any hallucinated modules or fields
    # -------------------------------------------------------------------------
    valid_modules = [m for m in response.modules if m in MODULE_SCHEMAS]

    valid_filter_fields: dict[str, dict[str, str]] = {}
    for mod in valid_modules:
        valid_filter_fields[mod] = {
            field: desc
            for field, desc in response.filter_fields.get(mod, {}).items()
            if field in MODULE_SCHEMAS[mod]
        }

    valid_filter_values: dict[str, dict[str, str]] = {}
    for mod in valid_modules:
        valid_filter_values[mod] = {
            field: val
            for field, val in response.filter_values.get(mod, {}).items()
            if field in MODULE_SCHEMAS.get(mod, {})
        }

    result = {
        "reasoning":     response.reasoning,
        "modules":       valid_modules,
        "filter_fields": valid_filter_fields,
        "filter_values": valid_filter_values,
    }

    return result
