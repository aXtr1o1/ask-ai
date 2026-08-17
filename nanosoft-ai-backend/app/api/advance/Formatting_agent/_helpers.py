"""
Formatting Agent — Internal Helpers

  _stringify   — convert any value to a clean string for LLM injection
  _log_input   — log what the Formatting Agent receives (format, steps, answer)
  _log_output  — log what the Formatting Agent returns (explanation, latency, tokens)
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("advance.formatting")

_SEP = "─" * 60
_DATA_HEAVY_FORMATS = {"TABLE", "GRAPH"}


# =============================================================================
# _stringify
# =============================================================================

def _stringify(value: Any) -> str:
    """Convert any value to a plain string for safe LLM injection or display."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, default=str)
    return str(value).strip()


# =============================================================================
# _log_input
# =============================================================================

def _log_input(
    response_format: str,
    query_summary:   str,
    planned_steps:   list,
    final_answer:    Any,
) -> None:
    """Log what the Formatting Agent receives before calling the LLM."""
    is_data_heavy = response_format in _DATA_HEAVY_FORMATS
    mode = "DATA-HEAVY (no values sent)" if is_data_heavy else "PLAIN_TEXT (result included)"
    logger.info("┌─ [Formatting Agent] INPUT  [%s]", mode)
    logger.info("│  format  : %s", response_format)
    logger.info("│  question: %s", (query_summary or "(none)")[:120])
    logger.info("│  steps   : %d planned", len(planned_steps))
    for s in planned_steps:
        arg_str = " | ".join(f"{k}={v}" for k, v in s.get("args", {}).items())
        logger.info("│    step %-2s → %-24s %s", s.get("step", "?"), s.get("tool", "?"), arg_str[:80])
    if not is_data_heavy and final_answer is not None:
        preview = str(final_answer)[:300]
        logger.info("│  answer  : %s%s", preview, "…" if len(str(final_answer)) > 300 else "")
    logger.info("└─ %s", _SEP)


# =============================================================================
# _log_output
# =============================================================================

def _log_output(
    response_format: str,
    explanation:     str,
    latency_ms:      float,
    input_tokens:    int,
    output_tokens:   int,
) -> None:
    """Log what the Formatting Agent returns after the LLM call."""
    logger.info("┌─ [Formatting Agent] OUTPUT")
    logger.info("│  format   : %s", response_format)
    logger.info("│  latency  : %.0f ms | tokens: %d in / %d out", latency_ms, input_tokens, output_tokens)
    logger.info("│  response : %s%s", explanation[:200], "…" if len(explanation) > 200 else "")
    logger.info("└─ %s", _SEP)
