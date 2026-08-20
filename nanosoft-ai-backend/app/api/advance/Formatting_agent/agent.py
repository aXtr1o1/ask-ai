"""
FM Formatting Agent

Sits after execution_node and before the API/frontend response.

RESPONSIBILITIES:
  Write the explanation/context for the response.

DATA FLOW:
  TABLE / GRAPH   — LLM receives query + planned_steps only (no row values).
                    Frontend renders the data. LLM writes the analytical
                    context paragraph that appears above the rendered data.

  PLAIN_TEXT      — LLM receives query + planned_steps + final_answer.
                    LLM writes the complete polished response.

Public API:
  format_response(formatting_context, query_summary, thought_callback) → dict
"""
from __future__ import annotations

import json
import logging
import time

from google.genai import types

from app.api.advance.Formatting_agent.prompt   import build_formatting_prompt
from app.api.advance.Formatting_agent._helpers import _log_input, _log_output
from app.api.advance.gemini_stream             import stream_with_thoughts

logger = logging.getLogger("advance.formatting")

_DATA_HEAVY_FORMATS = {"TABLE", "GRAPH"}

_FORMAT_TO_RESPONSE_TYPE = {
    "TABLE":      "table-response",
    "GRAPH":      "graph-response",
    "PLAIN_TEXT": "plain-response",
}


# =============================================================================
# PUBLIC API
# =============================================================================

def format_response(
    formatting_context: dict,
    query_summary:      str | None = None,
    thought_callback               = None,
) -> dict:
    """
    Call the Formatting Agent LLM to write the explanation for the response.

    Args:
        formatting_context: Output of build_formatting_context() — contains
                            planned_steps, response_format, shape_descriptor,
                            format_overridden, and (for PLAIN_TEXT) final_answer.
        query_summary:      The user's query summary for context.
        thought_callback:   Optional callable — receives thought token chunks
                            in real time for SSE streaming to the frontend.

    Returns:
        {
            "response_type":  str,   # "table-response" | "graph-response" | "plain-response"
            "layout":         str,   # "TABLE" | "GRAPH" | "PLAIN_TEXT"
            "explanation":    str,   # LLM-written analytical context or full answer
            "final_answer":   Any,   # raw computed value (None for data-heavy formats)
        }
    """
    # ── Extract from formatting_context ───────────────────────────────────────
    planned_steps     = formatting_context.get("planned_steps",     [])
    response_format   = formatting_context.get("response_format",   "PLAIN_TEXT").upper()
    final_answer      = formatting_context.get("final_answer",      None)
    shape_descriptor  = formatting_context.get("shape_descriptor",  {})
    # Dashboard component list produced by DashboardComposer (deterministic, no LLM).
    # May be an empty list if composition was skipped or failed gracefully.
    dashboard         = formatting_context.get("dashboard",          [])

    # Extract component titles + types for the prompt — structure only, no values.
    # The LLM uses this to reference the exact visuals the user is seeing.
    dashboard_summary = [
        {"type": item.get("type", ""), "title": item.get("title", "")}
        for item in dashboard
        if isinstance(item, dict) and item.get("type") and item.get("title")
    ]

    is_data_heavy = response_format in _DATA_HEAVY_FORMATS

    _log_input(response_format, query_summary or "", planned_steps, final_answer)

    # ── Build human message ────────────────────────────────────────────────────
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
        shape_descriptor  = shape_descriptor,
        dashboard_summary = dashboard_summary,
    )

    # ── Stream LLM ────────────────────────────────────────────────────────────
    config = types.GenerateContentConfig(
        system_instruction = system_prompt,
        temperature        = 1.0,
        thinking_config    = types.ThinkingConfig(
            thinking_budget  = 256,
            include_thoughts = True,
        ),
    )

    explanation   = ""
    input_tokens  = 0
    output_tokens = 0
    latency_ms    = 0.0

    try:
        t_start = time.perf_counter()
        _, raw_text, usage = stream_with_thoughts(
            contents   = [{"role": "user", "parts": [{"text": human_content}]}],
            config     = config,
            thought_cb = thought_callback,
        )
        latency_ms    = (time.perf_counter() - t_start) * 1000
        explanation   = raw_text.strip()
        input_tokens  = usage.get("input_tokens",  0)
        output_tokens = usage.get("output_tokens", 0)

        _log_output(
            response_format = response_format,
            explanation     = explanation,
            latency_ms      = latency_ms,
            input_tokens    = input_tokens,
            output_tokens   = output_tokens,
        )

    except Exception as exc:
        logger.error("[Formatting Agent] LLM failed: %s", exc)
        explanation = ""

    return {
        "response_type": _FORMAT_TO_RESPONSE_TYPE.get(response_format, "plain-response"),
        "layout":        response_format,
        "explanation":   explanation,
        "final_answer":  final_answer,   # None for TABLE/GRAPH — frontend uses execution result
        # Typed presentation component list from DashboardComposer.
        # Always present (may be empty list).  Frontend uses this for the
        # dynamic dashboard renderer when the list is non-empty.
        "dashboard":     dashboard,
    }