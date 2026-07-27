"""
Understanding Agent

First stage of the FM pipeline. Reads the raw user query and produces:
  - intent          : general | db_query | web_search
  - query_summary   : clean, complete restatement of the query
  - modules         : which FM modules are relevant (db_query only)
  - general_response: direct answer for general queries
  - web_search_summary: live web results for web_search queries

Thought tokens are streamed in real-time via thought_callback.
"""
import logging
import time

from google import genai
from google.genai import types

from app.config import settings
from app.api.advance.Understanding_Agent.conversation_memory import conversation_memory
from app.api.advance.Understanding_Agent.schemas import UnderstandingOutput
from app.api.advance.Understanding_Agent.prompt import build_system_prompt
from app.api.advance.gemini_stream import stream_with_thoughts, history_to_contents

logger = logging.getLogger("advance.understanding")

# Build system prompt once at startup (MODULE_FIELDS is static)
_SYSTEM_PROMPT = build_system_prompt()


# =============================================================================
# MAIN FUNCTION
# =============================================================================
def classify_query(
    query:          str,
    session_id:     str,
    thought_callback = None,
) -> dict:
    """
    Classify a user query using Gemini streaming.

    thought_callback(text_chunk: str): called with each thought token as it
    arrives from the API. Pass None for batch / test-pipeline mode.

    Returns a dict with:
      intent, query_summary, modules, response_format, user_specified_format,
      web_search_summary, general_response, thought, latency
    """
    logger.info("[Understanding Agent] query    : %s", query)
    start_total = time.perf_counter()

    # ── Build contents ────────────────────────────────────────────────────────
    history  = conversation_memory.get_history(session_id)
    contents = history_to_contents(history)
    contents.append({"role": "user", "parts": [{"text": f'Query: "{query}"'}]})

    config = types.GenerateContentConfig(
        system_instruction = _SYSTEM_PROMPT,
        response_mime_type = "application/json",
        temperature        = 0.3,
        thinking_config    = types.ThinkingConfig(
            thinking_budget  = 256,
            include_thoughts = True,
        ),
    )

    # ── Stream ────────────────────────────────────────────────────────────────
    start_llm = time.perf_counter()
    thought, json_text, usage = stream_with_thoughts(
        contents   = contents,
        config     = config,
        thought_cb = thought_callback,
    )
    llm_time = time.perf_counter() - start_llm

    # ── Parse structured output ───────────────────────────────────────────────
    try:
        response = UnderstandingOutput.model_validate_json(json_text)
    except Exception as exc:
        logger.error("[Understanding Agent] JSON parse failed: %s\nRaw: %.300s", exc, json_text)
        raise ValueError(f"Understanding Agent returned unparseable JSON: {exc}") from exc

    # ── Log ───────────────────────────────────────────────────────────────────
    logger.info("[Understanding Agent] tokens   : input=%d output=%d total=%d",
                usage.get("input_tokens", 0), usage.get("output_tokens", 0), usage.get("total_tokens", 0))
    logger.info("[Understanding Agent] latency  : llm=%.2fs", llm_time)
    logger.info("[Understanding Agent] intent   : %s", response.intent)
    logger.info("[Understanding Agent] summary  : %s", response.query_summary)
    logger.info("[Understanding Agent] modules  : %s", response.modules)
    logger.info("[Understanding Agent] format   : %s | user_specified: %s",
                response.response_format, response.user_specified_format)

    # ── Web search grounding ──────────────────────────────────────────────────
    web_search_summary = None
    web_search_time    = 0.0
    if response.intent == "web_search":
        start_ws = time.perf_counter()
        try:
            client = genai.Client(api_key=settings.GOOGLE_API_KEY)
            search_response = client.models.generate_content(
                model   = "gemini-2.5-flash",
                contents = (
                    f"Search for information relevant to this facility management query: {query}\n"
                    f"Provide a concise, factual summary of the most relevant findings."
                ),
                config  = types.GenerateContentConfig(
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
            logger.error("[Understanding Agent] web_search failed: %s", e)
            web_search_summary = f"Web search failed: {e}"
        finally:
            web_search_time = time.perf_counter() - start_ws
        logger.info("[Understanding Agent] latency  : web_search=%.2fs", web_search_time)

    total_time = time.perf_counter() - start_total
    logger.info("[Understanding Agent] latency  : total=%.2fs", total_time)

    return {
        "intent":                response.intent,
        "query_summary":         response.query_summary or query,      # fallback to raw query if None (general intent)
        "modules":               response.modules,
        "response_format":       response.response_format or "PLAIN_TEXT",
        "user_specified_format": bool(response.user_specified_format),  # None → False
        "web_search_summary":    web_search_summary,
        "general_response":      response.general_response,
        "thought":               thought,
        "latency": {
            "llm_time":        round(llm_time,        2),
            "web_search_time": round(web_search_time, 2),
            "total_time":      round(total_time,       2),
        },
    }
