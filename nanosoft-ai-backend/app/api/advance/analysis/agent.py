import logging
import re
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings
from app.api.advance.analysis.prompt import get_dynamic_system_prompt
from app.api.advance.analysis.rules import MODULE_SCHEMAS, STANDARD_CONTEXT_FIELDS
from app.api.advance.Understanding_Agent.agent import classify_query
import json

logger = logging.getLogger("advance.analysis.agent")


class AnalysisSchema(BaseModel):
    """Schema for structured analysis agent output."""
    question: str = Field(
        description="The question or user query to analyze."
    )
    modules: list[str] = Field(
        description="List of modules needed for the query. Allowed values: bdm, ppm, assets, fa, sb.",
        default_factory=list
    )
    filter_fields: dict[str, dict[str, str]] = Field(
        description="Dictionary mapping each selected module to its selected fields and their descriptions (schema projection).",
        default_factory=dict
    )
    extracted_filter_values: dict[str, str] = Field(
        description="Flat dictionary mapping field names to their extracted filter values from the user query.",
        default_factory=dict
    )


# Guardrail Configuration (same as Understanding Agent)
GUARDRAIL_PATTERNS = [
    # Match attempts to override prompts or system instructions
    r"(?i)\b(ignore|override|bypass|forget)\b.*\b(instructions|system|rules|prompt|guidelines)\b",
    r"(?i)\b(developer|system|admin)\b.*\b(mode|role|instructions)\b",
    r"(?i)you are now.*\b(not|different|new)\b",
]

# Instantiate LLM once at module level for optimal performance
_llm = ChatGoogleGenerativeAI(
    model=settings.GOOGLE_AI_MODEL,
    google_api_key=settings.GOOGLE_API_KEY,
    temperature=0,
)
_structured_llm = _llm.with_structured_output(AnalysisSchema)



def analyze_query(query: str) -> dict:
    """Analyze a user query, dynamically selecting modules and filter fields, and extracting values."""
    # Code-side guardrail verification
    for pattern in GUARDRAIL_PATTERNS:
        if re.search(pattern, query):
            logger.warning("guardrail_blocked query=%r pattern=%r", query, pattern)
            raise ValueError("Potential prompt injection detected. Query blocked by guardrails.")

    # 1. Run understanding agent
    understanding = classify_query(query)
    intent = understanding.get("intent", "db_query")

    if intent in ("general", "web_search"):
        result = {
            "intent": intent,
            "general_response": understanding.get("general_response"),
            "web_search_summary": understanding.get("web_search_summary"),
            "brief_explanation": understanding.get("brief_explanation"),
            "question": query,
            "modules": [],
            "filter_fields": {},
            "extracted_filter_values": {},
        }
        logger.info("")
        logger.info("ANALYSIS AGENT (Bypassed):")
        logger.info("  QUERY        : %s", query)
        logger.info("  INTENT       : %s", intent)
        if intent == "general":
            logger.info("  RESPONSE     : %s", result["general_response"])
        else:
            logger.info("  SEARCH SUMM  : %s", result["web_search_summary"])
        return result

    

    schema_block = json.dumps(MODULE_SCHEMAS, indent=2)
    system_prompt = get_dynamic_system_prompt(schema_block)
    logger.info("query=%r prompt_len=%d", query, len(system_prompt))

    # Pass only the understanding agent's structured output
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(understanding, indent=2)),
    ]
    response = _structured_llm.invoke(messages)
    
    # Prune hallucinated modules/fields not present in MODULE_SCHEMAS
    valid_modules = [m for m in response.modules if m in MODULE_SCHEMAS]
    valid_filter_fields = {}
    for mod in valid_modules:
        valid_filter_fields[mod] = {}
        # 1. Start with fields returned by the LLM
        if mod in response.filter_fields:
            for field, desc in response.filter_fields[mod].items():
                if field in MODULE_SCHEMAS[mod]:
                    valid_filter_fields[mod][field] = desc
        # 2. Merge baseline standard context fields
        if mod in STANDARD_CONTEXT_FIELDS:
            for field in STANDARD_CONTEXT_FIELDS[mod]:
                if field in MODULE_SCHEMAS[mod] and field not in valid_filter_fields[mod]:
                    valid_filter_fields[mod][field] = MODULE_SCHEMAS[mod][field]

    # Prune extracted filter values that do not belong to any valid module's schema
    valid_filter_values = {}
    for field, val in response.extracted_filter_values.items():
        if any(field in MODULE_SCHEMAS[mod] for mod in valid_modules):
            valid_filter_values[field] = val

    result = {
        "intent": "db_query",
        "question": response.question,
        "modules": valid_modules,
        "filter_fields": valid_filter_fields,
        "extracted_filter_values": valid_filter_values,
    }

    logger.info("")
    logger.info("ANALYSIS AGENT:")
    logger.info("  UNDERSTANDING: %s", understanding)
    logger.info("  INTENT       : %s", result.get("intent"))
    logger.info("  MODULES      : %s", result.get("modules"))
    logger.info("  FILTER FIELDS: %s", result.get("filter_fields"))
    logger.info("  FILTERS      : %s", result.get("extracted_filter_values"))

    return result


