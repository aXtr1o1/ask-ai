import logging
import re
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from google import genai
from google.genai import types
from app.config import settings
from app.api.advance.Understanding_Agent.prompt import SYSTEM_PROMPT

logger = logging.getLogger("advance.Understanding_Agent")


class IntentClassificationSchema(BaseModel):
    """Schema for structured intent classification output."""
    intent: Literal["general", "db_query", "web_search"] = Field(
        description="The classified intent of the query."
    )
    brief_explanation: str = Field(
        description="A detailed explanation justifying the classification decision."
    )
    general_response: str | None = Field(
        description="The generated direct response to the user's query if intent is 'general', else null.",
        default=None
    )


# Guardrail Configuration
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
_structured_llm = _llm.with_structured_output(IntentClassificationSchema)


def classify_query(query: str) -> dict:
    """Classify a user query into 'general', 'db_query', or 'web_search'."""
    logger.info("query=%r prompt_len=%d", query, len(SYSTEM_PROMPT))

    # Code-side guardrail verification
    for pattern in GUARDRAIL_PATTERNS:
        if re.search(pattern, query):
            logger.warning("guardrail_blocked query=%r pattern=%r", query, pattern)
            raise ValueError("Potential prompt injection detected. Query blocked by guardrails.")

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f'Query: "{query}"'),
    ]

    response = _structured_llm.invoke(messages)

    web_search_summary = None
    if response.intent == "web_search":
        logger.info("web_search intent detected — executing Google Search grounding")
        try:
            client = genai.Client(api_key=settings.GOOGLE_API_KEY)
            search_prompt = (
                f"Search for information relevant to this facility management query: {query}\n"
                f"Provide a concise, factual summary of the most relevant findings."
            )
            search_response = client.models.generate_content(
                model=settings.GOOGLE_AI_MODEL,
                contents=search_prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            summary = ""
            if search_response.candidates:
                for part in (search_response.candidates[0].content.parts or []):
                    if hasattr(part, "text") and part.text:
                        summary += part.text
            web_search_summary = summary.strip() or "Web search returned no relevant results."
            logger.info("web_search_summary successfully retrieved")
        except Exception as e:
            logger.error("Web search grounding failed: %s", e, exc_info=True)
            web_search_summary = f"Web search failed: {e}"

    result = {
        "intent": response.intent,
        "brief_explanation": response.brief_explanation,
        "web_search_summary": web_search_summary,
        "general_response": response.general_response
    }

    logger.info("")
    logger.info("UNDERSTANDING AGENT:")
    logger.info("  QUERY  : %s", query)
    logger.info("  INTENT : %s", result["intent"])
    if result["general_response"]:
        logger.info("  REPLY  : %s", result["general_response"])
    elif result["web_search_summary"]:
        logger.info("  SEARCH  : %s", result["web_search_summary"])
    else:
        logger.info("  EXPLANATION : %s", result["brief_explanation"])

    return result

