"""
Analysis Agent

Receives the Understanding Agent's query summary and the pre-identified
modules. Decides which fields to retrieve and which values to filter on
for each module.

Why modules come from outside:
    The Understanding Agent already identified which modules are relevant.
    This agent only receives metadata for those modules, keeping the
    system prompt lean (no wasted tokens on irrelevant modules).

Flow:
  query_summary + modules (from Understanding Agent)
    → Build system prompt with only selected modules' metadata
    → LLM with structured output (AnalysisOutput)
    → Validate — strip any hallucinated modules or fields
    → Return { modules, filter_fields, filter_values }
"""
import logging

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.api.advance.analysis.schemas import AnalysisOutput
from app.api.advance.analysis.prompt import get_system_prompt
from app.api.advance.analysis.metadata import MODULE_SCHEMAS, get_metadata

logger = logging.getLogger("advance.analysis")


# =============================================================================
# MAIN FUNCTION
# =============================================================================
def analyze_query(query_summary: str, modules: list[str]) -> dict:
    """
    Run the Analysis Agent on a cleaned query summary.

    Args:
        query_summary : Clean query text produced by the Understanding Agent.
        modules       : FM modules identified by the Understanding Agent.
                        Only metadata for these modules is loaded into the prompt.

    Returns:
        {
            "reasoning":     str,
            "modules":       [list of validated module names],
            "filter_fields": { module: { field: description } },
            "filter_values": { module: { field: value } },
        }
    """
    # -------------------------------------------------------------------------
    # Log what metadata is being loaded (field count per module)
    # This lets you verify the lean-prompt effect before the LLM call
    # -------------------------------------------------------------------------
    loaded_meta = get_metadata(modules)
    meta_summary = ", ".join(
        f"{mod}({len(fields)} fields)" for mod, fields in loaded_meta.items()
    )
    logger.info("[Analysis Agent] metadata loaded — %s", meta_summary)

    # -------------------------------------------------------------------------
    # Build the system prompt with only the selected modules' metadata
    # -------------------------------------------------------------------------
    system_prompt = get_system_prompt(modules)

    # -------------------------------------------------------------------------
    # LLM call
    # -------------------------------------------------------------------------
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,
        thinking_budget=512,
    )
    # include_raw=True gives us the raw AIMessage (with usage_metadata)
    # alongside the parsed Pydantic output
    structured_llm = llm.with_structured_output(AnalysisOutput, include_raw=True)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query_summary),
    ]
    result      = structured_llm.invoke(messages)
    response: AnalysisOutput = result["parsed"]
    usage       = result["raw"].usage_metadata or {}

    logger.info(
        "[Analysis Agent] tokens — input: %d | output: %d | total: %d",
        usage.get("input_tokens",  0),
        usage.get("output_tokens", 0),
        usage.get("total_tokens",  0),
    )

    # -------------------------------------------------------------------------
    # Validate — strip any hallucinated modules or fields
    # Only allow modules that exist in the full registry AND were requested
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

    return {
        "reasoning":     response.reasoning,
        "modules":       valid_modules,
        "filter_fields": valid_filter_fields,
        "filter_values": valid_filter_values,
    }
