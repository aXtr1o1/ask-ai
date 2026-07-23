"""
FM Formatting Agent

Sits after execution and before the API/frontend response.
Normalises the raw pipeline output into a stable envelope the frontend can render.

ONE MODE for all formats:
  The LLM always receives: query_summary + planned_steps + final_answer.
  It reasons over the actual computed data, understands the layout, and writes
  the most appropriate response — whether that is a rich analytical paragraph
  (for TABLE/GRAPH) or a full natural-language answer (for PLAIN_TEXT/LIST formats).

  Thinking is enabled so the model can reason deeply before writing.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.api.advance.Formatting_agent.prompt import FORMATTING_SYSTEM_PROMPT

logger = logging.getLogger("advance.formatting")

DASH  = "-" * 60


# ---------------------------------------------------------------------------
# Format → frontend response_type mapping
# ---------------------------------------------------------------------------
_FORMAT_TO_RESPONSE_TYPE = {
    "TABLE":          "table-response",
    "GRAPH":          "graph-response",
    "BULLET_LIST":    "bullet-response",
    "NUMBERED_LIST":  "numbered-list-response",
    "PLAIN_TEXT":     "plain-response",
}


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


def _log_input(
    response_format: str,
    query_summary: str,
    planned_steps: list,
    final_answer: Any,
) -> None:
    """Log exactly what is being sent into the Formatting Agent LLM."""
    logger.info("")
    logger.info(DASH)
    logger.info("► FORMATTING AGENT — INPUT")
    logger.info("  Format        : %s", response_format)
    logger.info("  Query Summary : %s", query_summary or "(not provided)")
    logger.info("  Planned Steps :")
    for s in planned_steps:
        args_str = " | ".join(f"{k}={v}" for k, v in s.get("args", {}).items())
        logger.info("    [step %s] %-22s %s", s.get("step", "?"), s.get("tool", "?"), args_str)
    if final_answer is not None:
        preview = str(final_answer)[:400]
        logger.info("  Final Answer  : %s%s", preview, "…" if len(str(final_answer)) > 400 else "")
    logger.info(DASH)


def _log_output(
    response_format: str,
    explanation: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    latency_ms: float,
) -> None:
    """Log the LLM output, token usage, and latency for the Formatting Agent."""
    logger.info("")
    logger.info(DASH)
    logger.info("► FORMATTING AGENT — OUTPUT")
    logger.info("  Format         : %s", response_format)
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
    for l in lines:
        logger.info("%s", l)
    logger.info(DASH)
    logger.info("")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def format_pipeline_response(
    response: dict,
    *,
    query_summary: str | None = None,
    default_response_type: str = "analytical-answer",
) -> dict:
    """
    Format the pipeline output using an LLM with thinking enabled.

    Args:
        response        : The full execution result dict.  Must contain
                          response["formatting_context"] built by context_builder.
        query_summary   : The clean query restatement from the Understanding Agent.
        default_response_type: Fallback response_type string.

    Returns a dict:
        {
          "response_type":    str,
          "layout":           str,
          "explanation":      str,
          "formatted_answer": str | JSON,
          "token_usage":      {"input": int, "output": int, "total": int},
          "latency_ms":       float,
        }
    """
    # Hardcoded layout escape hatch (upstream error responses)
    hardcoded_layout = (response.get("layout") or "").upper().strip()
    if hardcoded_layout:
        return {
            "response_type": response.get("response_type", default_response_type),
            "layout":        hardcoded_layout,
            "explanation":   _stringify(response.get("formatted_answer")),
        }

    # ── Pull context built by the execution layer ──────────────────────────
    formatting_context = response.get("formatting_context", {})
    planned_steps   = formatting_context.get("planned_steps", [])
    response_format = formatting_context.get("response_format", "PLAIN_TEXT").upper()
    final_answer    = formatting_context.get("final_answer", None)

    # Raw data for the frontend (passed through untouched for TABLE/GRAPH)
    raw_data = _stringify(response.get("formatted_answer"))

    # ── Log what goes into the LLM ────────────────────────────────────────
    _log_input(response_format, query_summary, planned_steps, final_answer)

    # ── Build human message — same for all formats ─────────────────────────
    human_content = (
        f"Layout: {response_format}\n\n"
        f"Question the user asked:\n{query_summary or '(not provided)'}\n\n"
        f"Computation steps that were executed to produce the answer:\n"
        f"{json.dumps(planned_steps, indent=2)}\n\n"
        f"Computed result (the actual data from the pipeline):\n"
        f"{json.dumps(final_answer, indent=2, default=str)}\n"
    )

    # ── Invoke LLM with thinking enabled ─────────────────────────────────
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.3,
        thinking_budget=256,
    )

    explanation   = ""
    input_tokens  = 0
    output_tokens = 0
    total_tokens  = 0
    latency_ms    = 0.0

    try:
        logger.info("[FORMATTING AGENT] Invoking LLM with thinking — format: %s", response_format)

        t_start = time.perf_counter()
        llm_response = llm.invoke([
            SystemMessage(content=FORMATTING_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ])
        latency_ms = (time.perf_counter() - t_start) * 1000

        explanation = llm_response.content.strip() if hasattr(llm_response, "content") else ""

        # ── Extract token usage from response metadata ─────────────────────
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
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
        )

    except Exception as e:
        logger.error("[FORMATTING AGENT] LLM failed: %s", e)
        explanation = ""

    return {
        "response_type":    _FORMAT_TO_RESPONSE_TYPE.get(response_format, default_response_type),
        "layout":           response_format,
        "explanation":      explanation,
        "formatted_answer": raw_data,
        "token_usage": {
            "input":  input_tokens,
            "output": output_tokens,
            "total":  total_tokens,
        },
        "latency_ms": round(latency_ms, 1),
    }
