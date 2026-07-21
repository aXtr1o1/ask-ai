"""
Understanding Agent

First stage of the FM pipeline. Reads the raw user query and produces:
  - intent          : general | db_query | web_search
  - query_summary   : clean, complete restatement of the query
  - modules         : which FM modules are relevant (db_query only)
  - general_response: direct answer for general queries
  - web_search_summary: live web results for web_search queries

Flow:
  Raw user query
    → LLM with structured output (UnderstandingOutput)
    → If web_search: run Google Search grounding
    → Return result dict

Only db_query results (with modules) are forwarded to the Analysis Agent.
general and web_search are returned directly to the caller.
"""
import logging
import time

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from google import genai
from google.genai import types

from app.config import settings
from app.api.advance.Understanding_Agent.schemas import UnderstandingOutput
from app.api.advance.Understanding_Agent.prompt import build_system_prompt

logger = logging.getLogger("advance.understanding")

# Build the system prompt once at startup (MODULE_FIELDS is static)
_SYSTEM_PROMPT = build_system_prompt()


# =============================================================================
# MAIN FUNCTION
# =============================================================================
def classify_query(query: str) -> dict:
    """
    Classify a user query and return a structured result.

    Returns a dict with:
      intent             — "general" | "db_query" | "web_search"
      query_summary      — cleaned, complete restatement of the query
      modules            — FM modules relevant to the query (db_query only)
      web_search_summary — web search result (web_search only)
      general_response   — direct answer (general only)
    """
    start_total = time.perf_counter()

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,
        thinking_budget=512,
    )
    # include_raw=True gives us the raw AIMessage (with usage_metadata)
    # alongside the parsed Pydantic output
    structured_llm = llm.with_structured_output(UnderstandingOutput, include_raw=True)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f'Query: "{query}"'),
    ]
    start_llm   = time.perf_counter()
    result      = structured_llm.invoke(messages)
    llm_time    = time.perf_counter() - start_llm

    response: UnderstandingOutput = result["parsed"]
    usage       = result["raw"].usage_metadata or {}

    logger.info(
        "[Understanding Agent] tokens — input: %d | output: %d | total: %d",
        usage.get("input_tokens",  0),
        usage.get("output_tokens", 0),
        usage.get("total_tokens",  0),
    )
    logger.info(
        "[Understanding Agent] latency — llm: %.2fs",
        llm_time,
    )

    # -------------------------------------------------------------------------
    # Web search grounding — only when intent is web_search
    # -------------------------------------------------------------------------
    web_search_summary = None
    web_search_time    = 0.0
    if response.intent == "web_search":
        start_ws = time.perf_counter()
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
        finally:
            web_search_time = time.perf_counter() - start_ws
        logger.info(
            "[Understanding Agent] latency — web_search: %.2fs",
            web_search_time,
        )

    total_time = time.perf_counter() - start_total
    logger.info(
        "[Understanding Agent] latency — total: %.2fs",
        total_time,
    )

    return {
        "intent":              response.intent,
        "query_summary":       response.query_summary,
        "modules":             response.modules,          # <-- new
        "web_search_summary":  web_search_summary,
        "general_response":    response.general_response,
        "latency": {
            "llm_time":         round(llm_time,         2),
            "web_search_time":  round(web_search_time,  2),
            "total_time":       round(total_time,        2),
        },
    }
