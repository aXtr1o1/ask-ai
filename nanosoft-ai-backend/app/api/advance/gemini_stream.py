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
                "total_tokens":  getattr(um, "total_token_count",      0) or 0,
            }

        if not chunk.candidates:
            continue

        for part in chunk.candidates[0].content.parts:
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
    Convert conversation_memory history to google.genai contents format.

    Input  (LangChain-dict):  [{"role": "user", "content": "..."}, ...]
    Output (google.genai):    [{"role": "user", "parts": [{"text": "..."}]}, ...]

    Note: "assistant" role is mapped to "model" (google.genai convention).
    """
    contents = []
    for msg in history:
        role = "model" if msg.get("role") == "assistant" else "user"
        contents.append({
            "role":  role,
            "parts": [{"text": msg.get("content", "")}],
        })
    return contents
