"""
FM Formatting Agent

Sits after execution and before the API/frontend response.

RESPONSIBILITIES:
  1. Write the explanation/context for the response.
  2. Assess how well the Understanding Agent's chosen format fits the query
     (confidence score 1–10).
  3. If confidence < 8, append a format-suggestion line in the explanation
     so the user knows they can ask for a different view.

DATA FLOW:
  TABLE / GRAPH   — LLM receives steps only (no final_answer). Frontend renders data.
                    LLM writes the analytical context paragraph above the rendered data.
  LIGHTWEIGHT     — LLM receives steps + final_answer. LLM writes the full answer.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.api.advance.Understanding_Agent.conversation_memory import conversation_memory

from app.config import settings
from app.api.advance.Formatting_agent.prompt import build_formatting_prompt

logger = logging.getLogger("advance.formatting")

DASH = "-" * 60

_FORMAT_TO_RESPONSE_TYPE = {
    "TABLE":          "table-response",
    "GRAPH":          "graph-response",
    "BULLET_LIST":    "bullet-response",
    "NUMBERED_LIST":  "numbered-list-response",
    "PLAIN_TEXT":     "plain-response",
}

_DATA_HEAVY_FORMATS = {"TABLE", "GRAPH"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, default=str)
    return str(value).strip()


def _parse_llm_response(raw: str) -> tuple[str, int]:
    """
    Parse the LLM output into (explanation, confidence_score).

    Expected format:
        [EXPLANATION]
        <text>

        [CONFIDENCE]
        <integer>
    """
    explanation   = raw.strip()
    confidence    = 10  # default if parsing fails

    # Try to split on [CONFIDENCE]
    parts = re.split(r"\[CONFIDENCE\]", raw, flags=re.IGNORECASE)
    if len(parts) == 2:
        conf_block = parts[1].strip()
        expl_block = re.sub(r"^\[EXPLANATION\]", "", parts[0], flags=re.IGNORECASE).strip()
        explanation = expl_block
        # Extract first integer from confidence block
        m = re.search(r"\d+", conf_block)
        if m:
            confidence = max(1, min(10, int(m.group())))
    else:
        # Fallback: strip [EXPLANATION] header if present, take the whole thing
        explanation = re.sub(r"^\[EXPLANATION\]", "", raw, flags=re.IGNORECASE).strip()

    return explanation, confidence


def _log_input(response_format: str, query_summary: str, planned_steps: list, final_answer: Any) -> None:
    is_data_heavy = response_format.upper() in _DATA_HEAVY_FORMATS
    mode = "DATA-HEAVY (steps only)" if is_data_heavy else "LIGHTWEIGHT (steps + data)"
    logger.info("")
    logger.info(DASH)
    logger.info("► FORMATTING AGENT — INPUT  [%s]", mode)
    logger.info("  Format        : %s", response_format)
    logger.info("  Query Summary : %s", query_summary or "(not provided)")
    logger.info("  Planned Steps :")
    for s in planned_steps:
        args_str = " | ".join(f"{k}={v}" for k, v in s.get("args", {}).items())
        logger.info("    [step %s] %-22s %s", s.get("step", "?"), s.get("tool", "?"), args_str)
    if not is_data_heavy and final_answer is not None:
        preview = str(final_answer)[:400]
        logger.info("  Final Answer  : %s%s", preview, "…" if len(str(final_answer)) > 400 else "")
    logger.info(DASH)


def _log_output(
    response_format: str,
    explanation: str,
    confidence: int,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    latency_ms: float,
) -> None:
    logger.info("")
    logger.info(DASH)
    logger.info("► FORMATTING AGENT — OUTPUT")
    logger.info("  Format         : %s", response_format)
    logger.info("  Confidence     : %d/10%s", confidence,
                "  ✓ (no suggestion added)" if confidence >= 8 else "  ⚠ (format suggestion appended)")
    logger.info("  Latency        : %.0f ms", latency_ms)
    logger.info("  Tokens         : %d input  |  %d output  |  %d total",
                input_tokens, output_tokens, total_tokens)
    logger.info("  Response       (%d chars):", len(explanation))
    words = explanation.split()
    line, lines = [], []
    for w in words:
        line.append(w)
        if len(" ".join(line)) > 90:
            lines.append("    " + " ".join(line))
            line = []
    if line:
        lines.append("    " + " ".join(line))
    for ln in lines:
        logger.info("%s", ln)
    logger.info(DASH)
    logger.info("")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def format_pipeline_response(
    response: dict,
    *,
    session_id: str,
    user_query: str,
    query_summary: str | None = None,
    default_response_type: str = "analytical-answer",
) -> dict:
    """
    Format the pipeline output using an LLM with thinking.

    Returns:
        {
          "response_type":    str,
          "layout":           str,
          "explanation":      str,     # may include format suggestion if confidence < 8
          "formatted_answer": str,
          "format_confidence": int,    # 1–10
          "token_usage":      {input, output, total},
          "latency_ms":       float,
        }
    """
    # Hardcoded layout escape hatch (upstream error responses)
    hardcoded_layout = (response.get("layout") or "").upper().strip()
    if hardcoded_layout:
        return {
            "response_type":     response.get("response_type", default_response_type),
            "layout":            hardcoded_layout,
            "explanation":       _stringify(response.get("formatted_answer")),
            "format_confidence": 10,
        }

    # ── Pull context ───────────────────────────────────────────────────────
    formatting_context  = response.get("formatting_context", {})
    planned_steps       = formatting_context.get("planned_steps", [])
    response_format     = formatting_context.get("response_format", "PLAIN_TEXT").upper()
    final_answer        = formatting_context.get("final_answer", None)  # None for data-heavy
    shape_descriptor    = formatting_context.get("shape_descriptor", {})
    alternatives        = formatting_context.get("alternatives", [])
    format_overridden   = formatting_context.get("format_overridden", False)

    raw_data = _stringify(response.get("formatted_answer"))

    _log_input(response_format, query_summary, planned_steps, final_answer)

    # ── Build human message ────────────────────────────────────────────────
    is_data_heavy = response_format in _DATA_HEAVY_FORMATS
    if is_data_heavy:
        human_content = (
            f"Format: {response_format}\n\n"
            f"User question:\n{query_summary or '(not provided)'}\n\n"
            f"Computation steps:\n{json.dumps(planned_steps, indent=2)}\n"
        )
    else:
        human_content = (
            f"Format: {response_format}\n\n"
            f"User question:\n{query_summary or '(not provided)'}\n\n"
            f"Computation steps:\n{json.dumps(planned_steps, indent=2)}\n\n"
            f"Computed result:\n{json.dumps(final_answer, indent=2, default=str)}\n"
        )

    system_prompt = build_formatting_prompt(
        response_format,
        shape_descriptor   = shape_descriptor,
        alternatives       = alternatives,
        format_overridden  = format_overridden,
    )

    # ── Invoke LLM ────────────────────────────────────────────────────────
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.3,
        thinking_budget=256,
    )

    explanation   = ""
    confidence    = 10
    input_tokens  = 0
    output_tokens = 0
    total_tokens  = 0
    latency_ms    = 0.0

    try:
        logger.info("[FORMATTING AGENT] Invoking LLM — format: %s", response_format)

        t_start = time.perf_counter()
        llm_response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_content),
        ])
        latency_ms = (time.perf_counter() - t_start) * 1000

        raw_text    = llm_response.content.strip() if hasattr(llm_response, "content") else ""
        explanation, confidence = _parse_llm_response(raw_text)

        usage = getattr(llm_response, "usage_metadata", None) or {}
        if isinstance(usage, dict):
            input_tokens  = usage.get("input_tokens",  0) or usage.get("prompt_token_count",     0)
            output_tokens = usage.get("output_tokens", 0) or usage.get("candidates_token_count", 0)
            total_tokens  = usage.get("total_tokens",  0) or (input_tokens + output_tokens)
        elif hasattr(usage, "prompt_token_count"):
            input_tokens  = usage.prompt_token_count     or 0
            output_tokens = usage.candidates_token_count or 0
            total_tokens  = (input_tokens + output_tokens)

        _log_output(
            response_format=response_format,
            explanation=explanation,
            confidence=confidence,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
        )

    except Exception as e:
        logger.error("[FORMATTING AGENT] LLM failed: %s", e)
        explanation = ""
    conversation_memory.add_conversation(
    session_id=session_id,
    user_query=user_query,
    assistant_response=explanation,
)
    
    

    return {
        "response_type":     _FORMAT_TO_RESPONSE_TYPE.get(response_format, default_response_type),
        "layout":            response_format,
        "explanation":       explanation,
        "formatted_answer":  raw_data,
        "format_confidence": confidence,
        "token_usage": {
            "input":  input_tokens,
            "output": output_tokens,
            "total":  total_tokens,
        },
        "latency_ms": round(latency_ms, 1),
    }
