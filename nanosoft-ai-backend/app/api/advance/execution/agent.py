"""
FM Analytics Execution Agent — Queue-Driven, Tool-Only Architecture

Flow:
  Phase 1 — Planning (LLM called ONCE):
    question + schema  →  LLM  →  JSON queue of tool steps

  Phase 2 — Execution (no LLM, no loop):
    queue  →  run step by step  →  tools only  →  Execution Context
    filtered_records sit in Execution Context — tools read from there

  Final output:
    Raw tool results. LLM is never involved after Phase 1.
    Completion verified by: tools_called == queue_total

Public API:
  run_execution(question, filter_fields, modules, filtered_records) → ExecutionResult
"""
import json
import logging
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.api.advance.execution.prompts      import PLANNER_SYSTEM_PROMPT
from app.api.advance.execution.queue_runner import run_queue
from app.api.advance.execution.agent_logger import (
    log_question, log_queue, log_completion
)

logger = logging.getLogger("advance.execution.agent")


# =============================================================================
# HELPERS — JSON extraction from LLM response
# =============================================================================

def _extract_text(response_content) -> str:
    """Pull plain text from a Gemini response (handles list-of-blocks format)."""
    if isinstance(response_content, str):
        return response_content
    if isinstance(response_content, list):
        for block in response_content:
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                return block["text"]
    return str(response_content)


def _strip_markdown(raw: str) -> str:
    """Remove markdown code fences if the model wrapped JSON in them."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.IGNORECASE)
        raw = raw.rstrip("`").strip()
    return raw


def _validate_queue(queue: list) -> None:
    """Basic structural validation of the planned queue."""
    if not isinstance(queue, list) or len(queue) == 0:
        raise ValueError("Agent returned an empty or non-list queue.")
    for i, step in enumerate(queue):
        if not isinstance(step, dict):
            raise ValueError(f"Queue step {i} is not a dict: {step}")
        if "step" not in step or "tool" not in step:
            raise ValueError(f"Queue step {i} missing 'step' or 'tool' key: {step}")
    last_tool = queue[-1].get("tool")
    if last_tool != "final_answer_tool":
        raise ValueError(
            f"Last step must be 'final_answer_tool', got '{last_tool}'."
        )


# =============================================================================
# PUBLIC API
# =============================================================================

def run_execution(
    question:         str,
    filter_fields:    dict,
    modules:          list[str],
    filtered_records: dict,
) -> dict:
    """
    Main entry point for the execution layer.

    Phase 1 — Planning (LLM called once):
      Receives: question + schema (field names only — NO actual data rows).
      Returns: a complete queue of tool steps as JSON.

    Phase 2 — Execution (no LLM):
      Executes each step using tools directly.
      Tools read filtered_records from the Execution Context.
      No data goes back to the LLM.

    Args:
        question:         FM analytics question text
        filter_fields:    Schema metadata { module: { field: description } }
        modules:          Module names e.g. ["ppm", "bdm"]
        filtered_records: Actual data rows per module (never sent to LLM)

    Returns:
        ExecutionResult:
        {
          "queue":        list of planned steps,
          "step_results": { "step_0": {tool output}, "step_1": {tool output}, ... },
          "queue_total":  int,
          "tools_called": int,
          "status":       "COMPLETE" | "INCOMPLETE",
        }
    """
    # ── Phase 1: Plan the queue (LLM called once) ──────────────────────────
    log_question(question, modules)

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,
        thinking_budget=512,
    )

    schema_text = (
        json.dumps(filter_fields, indent=2)
        if filter_fields
        else "No column definitions provided."
    )

    response = llm.invoke([
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Question: {question}\n\n"
            f"Available modules: {modules}\n\n"
            f"Column definitions per module:\n{schema_text}\n\n"
            f"Produce the execution queue as a JSON array."
        )),
    ])

    if hasattr(response, "usage_metadata") and response.usage_metadata:
        usage = response.usage_metadata
        logger.info(
            "[Agent] LLM tokens — input: %d | output: %d | total: %d",
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
            usage.get("total_tokens", 0),
        )

    raw_text = _extract_text(response.content)
    raw_json = _strip_markdown(raw_text)
    logger.info("[Agent] Raw queue (first 500 chars): %s", raw_json[:500])

    try:
        queue = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        logger.error("[Agent] JSON parse failed: %s\nRaw: %s", exc, raw_json)
        raise ValueError(
            f"Agent returned invalid JSON.\nError: {exc}\nRaw:\n{raw_json}"
        ) from exc

    _validate_queue(queue)
    log_queue(queue)

    # ── Phase 2: Execute the queue (no LLM) ────────────────────────────────
    result = run_queue(queue, filtered_records)

    # ── Log completion ──────────────────────────────────────────────────────
    step_results = result.get("step_results", {})
    last_key     = f"step_{len(queue) - 1}"
    last_output  = step_results.get(last_key, {})
    final_value  = last_output.get("final_value", last_output)

    log_completion(
        status       = result["status"],
        tools_called = result["tools_called"],
        queue_total  = result["queue_total"],
        final_value  = final_value,
    )

    return result
