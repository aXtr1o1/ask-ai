"""
Shared Gemini Streaming Helper

Wraps google.genai generate_content_stream() to:
  1. Separate thought chunks from response text chunks.
  2. Call thought_cb(text) for each thought chunk the moment it arrives —
     no buffering, no delay — so the frontend receives tokens in real time.
  3. Accumulate full_thought and full_text for the caller to parse.

Usage (structured output):
    thought, json_text, usage = stream_with_thoughts(
        contents  = contents,
        config    = GenerateContentConfig(response_mime_type="application/json", ...),
        thought_cb= lambda chunk: q.put(chunk),
    )
    response = MyPydanticModel.model_validate_json(json_text)

Usage (free text):
    thought, text, usage = stream_with_thoughts(
        contents  = contents,
        config    = GenerateContentConfig(...),
        thought_cb= lambda chunk: q.put(chunk),
    )
"""
import logging
import re
from typing import Callable

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger("advance.gemini_stream")


def stream_with_thoughts(
    contents:    list,
    config:      types.GenerateContentConfig,
    model:       str              = "gemini-2.5-flash",
    thought_cb:  Callable | None  = None,
) -> tuple[str, str, dict]:
    """
    Stream a Gemini response, forwarding thought tokens in real time.

    Args:
        contents:   Messages in google.genai format
                    [{"role": "user", "parts": [{"text": "..."}]}, ...]
        config:     GenerateContentConfig — include thinking_config here.
        model:      Gemini model name.
        thought_cb: Optional. Called with each thought TEXT CHUNK as it arrives
                    from the API. The caller is responsible for forwarding these
                    to the frontend (e.g., via asyncio queue).

    Returns:
        (full_thought, full_text, usage_dict)
        full_text  — JSON string for json_mode, or free text otherwise.
        usage_dict — {"input_tokens": int, "output_tokens": int, "total_tokens": int}
    """
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    thought_parts: list[str] = []
    text_parts:    list[str] = []
    usage:         dict      = {}

    for chunk in client.models.generate_content_stream(
        model    = model,
        contents = contents,
        config   = config,
    ):
        # Usage metadata is populated in the final chunk
        if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
            um = chunk.usage_metadata
            usage = {
                "input_tokens":  getattr(um, "prompt_token_count",     0) or 0,
                "output_tokens": getattr(um, "candidates_token_count", 0) or 0,
                "thought_tokens": getattr(um, "thought_token_count",    0) or 0,
                "total_tokens":  getattr(um, "total_token_count",      0) or 0,
            }

        if not chunk.candidates:
            continue

        candidate = chunk.candidates[0]
        content   = candidate.content
        if content is None or content.parts is None:
            continue          # metadata-only / safety-rating chunk — skip

        for part in content.parts:
            text = part.text or ""
            if not text:
                continue

            if getattr(part, "thought", False):
                # ── Thought chunk: forward immediately ───────────────────────
                if thought_cb:
                    thought_cb(text)
                thought_parts.append(text)
            else:
                # ── Response text (JSON or free text) ────────────────────────
                text_parts.append(text)

    full_text = "".join(text_parts)

    # Strip markdown fences the model sometimes wraps JSON in
    full_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", full_text.strip(), flags=re.MULTILINE)

    return "".join(thought_parts), full_text.strip(), usage


def history_to_contents(history: list[dict]) -> list:
    """
    Convert structured ConversationTurn history to google.genai contents format
    for the Understanding Agent.

    Each turn produces TWO messages:
      user  → the raw user_query (what the user actually typed)
      model → "intent: X | modules: Y | summary: Z"
              (the Understanding Agent's own prior output — feeds its own
               reasoning back so it can resolve follow-up references cleanly)

    Input (structured turns from ConversationMemory.get_history()):
        [
            {
                "user_query":    "show me overdue assets",
                "query_summary": "List all assets with overdue maintenance status",
                "intent":        "db_query",
                "modules":       ["assets"],
                ...
            },
            ...
        ]

    Output (google.genai contents):
        [
            {"role": "user",  "parts": [{"text": "Query: \"show me overdue assets\""}]},
            {"role": "model", "parts": [{"text": "intent: db_query | modules: assets | summary: List all assets with overdue maintenance status"}]},
            ...
        ]
    """
    contents = []
    for turn in history:
        intent      = turn.get("intent", "general")
        modules     = turn.get("modules", [])
        summary     = turn.get("query_summary", "")
        user_query  = turn.get("user_query", "")

        # ── User message: the raw query the user sent ──────────────────────
        contents.append({
            "role":  "user",
            "parts": [{"text": f'Query: "{user_query}"'}],
        })

        # ── Model message: the Understanding Agent's own prior output ──────
        # Using structured text so the LLM can read its own prior reasoning
        # clearly — no ambiguity, no verbose formatting agent text.
        modules_str = ", ".join(modules) if modules else "none"
        model_text  = f"intent: {intent} | modules: {modules_str} | summary: {summary}"
        contents.append({
            "role":  "model",
            "parts": [{"text": model_text}],
        })

    return contents