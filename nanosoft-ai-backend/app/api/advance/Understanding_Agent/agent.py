"""
FM Understanding Agent

First stage of the pipeline. Reads the raw user query, classifies its intent,
and produces a clean query summary.

This agent has NO knowledge of database schema, field names, or modules.
Its only job is intent classification and query cleaning.

Flow:
  Raw user query
    → LLM with structured output (UnderstandingOutput)
    → If web_search: run Google Search grounding
    → Return { intent, query_summary, general_response, web_search_summary }

Only db_query results are passed to the Analysis Agent.
general and web_search are returned directly to the caller.
"""
import logging

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from google import genai
from google.genai import types

from app.config import settings
from app.api.advance.Understanding_Agent.schemas import UnderstandingOutput
from app.api.advance.Understanding_Agent.prompt import SYSTEM_PROMPT

logger = logging.getLogger("advance.understanding")


# =============================================================================
# MAIN FUNCTION: classify_query
# =============================================================================
def classify_query(query: str) -> dict:
    """
    Classify a user query and return a clean summary.

    Returns a dict with:
      intent            — "general" | "db_query" | "web_search"
      query_summary     — cleaned, standardised query text
      web_search_summary— web search result (web_search only)
      general_response  — direct answer (general only)
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,
        thinking_budget=512,
    )
    structured_llm = llm.with_structured_output(UnderstandingOutput)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f'Query: "{query}"'),
    ]
    response = structured_llm.invoke(messages)

    # Web search grounding — only when intent is web_search
    web_search_summary = None
    if response.intent == "web_search":
        try:
            client = genai.Client(api_key=settings.GOOGLE_API_KEY)
            search_response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=(
                    f"Search for information relevant to this facility management query: {query}\n"
                    f"Provide a concise, factual summary of the most relevant findings."
                ),
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
        except Exception as e:
            logger.error("web_search_failed error=%s", e)
            web_search_summary = f"Web search failed: {e}"

    result = {
        "intent":             response.intent,
        "query_summary":      response.query_summary,
        "web_search_summary": web_search_summary,
        "general_response":   response.general_response,
    }

    return result
