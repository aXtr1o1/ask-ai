"""
Queue Runner — executes the planned queue step by step using tools only.

No LLM calls happen here. Data flows through the Execution Context.

Execution Context (a plain dict):
  {
    "filtered_records": { module: [rows] },  # set ONCE before queue starts, never changes
  }

Step results accumulate in step_results:
  { "step_0": { tool output dict }, "step_1": { tool output dict }, ... }

$step_N.key references in args are resolved from step_results before each tool call.
"""
import inspect
import logging
from typing import Any

from app.api.advance.execution.tools import (
    count_records,
    sum_values,
    get_average,
    get_minimum,
    get_maximum,
    calculate_time_between,
    group_by_and_count,
    get_unique_values,
    join_records,
    do_math,
    final_answer_tool,
)
from app.api.advance.execution.agent_logger import log_step

logger = logging.getLogger("advance.execution.queue_runner")


# =============================================================================
# TOOL REGISTRY — name → LangChain tool object
# =============================================================================
TOOL_REGISTRY: dict[str, Any] = {
    "count_records":          count_records,
    "sum_values":             sum_values,
    "get_average":            get_average,
    "get_minimum":            get_minimum,
    "get_maximum":            get_maximum,
    "calculate_time_between": calculate_time_between,
    "group_by_and_count":     group_by_and_count,
    "get_unique_values":      get_unique_values,
    "join_records":           join_records,
    "do_math":                do_math,
    "final_answer_tool":      final_answer_tool,
}


# =============================================================================
# HELPERS
# =============================================================================

def _needs_state(tool_obj: Any) -> bool:
    """
    Check if a tool's underlying Python function accepts a 'state' parameter.
    Tools built with InjectedState() have 'state' in their signature but hidden
    from the LLM schema — we must inject it manually when calling directly.
    """
    raw_fn = getattr(tool_obj, "func", tool_obj)
    return "state" in inspect.signature(raw_fn).parameters


def _resolve_ref(val: Any, step_results: dict) -> Any:
    """
    Resolve a "$step_N.key" reference to its actual value from step_results.
    Non-reference values pass through unchanged.

    Formats:
      "$step_0.count"    → step_results["step_0"]["count"]
      "$step_2.result"   → step_results["step_2"]["result"]
      "$step_1"          → step_results["step_1"]  (whole dict)
      42 / "text" / ...  → returned as-is (plain values)
    """
    if not isinstance(val, str) or not val.startswith("$step_"):
        return val  # plain value — pass through

    ref = val[1:]           # strip "$"  →  "step_1.count"
    parts = ref.split(".", 1)
    step_key = parts[0]     # "step_1"

    step_result = step_results.get(step_key)
    if step_result is None:
        raise ValueError(
            f"Reference '{val}' refers to step '{step_key}' which has not run yet "
            f"or does not exist. Available steps: {list(step_results.keys())}"
        )

    if len(parts) == 1:
        return step_result  # whole dict

    field = parts[1]        # "count"
    if not isinstance(step_result, dict) or field not in step_result:
        available = list(step_result.keys()) if isinstance(step_result, dict) else "N/A"
        raise KeyError(
            f"Reference '{val}': field '{field}' not found in step '{step_key}'. "
            f"Available keys: {available}"
        )
    return step_result[field]


def _resolve_args(args: dict, step_results: dict) -> dict:
    """Resolve all $step_N.key references in an args dict.
    Handles plain values, single string references, and lists of references.
    """
    resolved = {}
    for k, v in args.items():
        if isinstance(v, list):
            # Resolve each item in the list individually
            resolved[k] = [_resolve_ref(item, step_results) for item in v]
        else:
            resolved[k] = _resolve_ref(v, step_results)
    return resolved


# =============================================================================
# PUBLIC API
# =============================================================================

def run_queue(queue: list[dict], filtered_records: dict) -> dict:
    """
    Execute the queue step by step. Return all step results.

    Tools access data via the Execution Context (not the LLM).
    $step_N.key references are resolved from previous step outputs.

    Args:
        queue:            List of StepDef dicts produced by planner.plan_queue()
        filtered_records: Actual data rows per module — set once, never changes

    Returns:
        ExecutionResult dict:
        {
          "queue":        original planned queue,
          "step_results": { "step_0": {...}, "step_1": {...}, ... },
          "queue_total":  int,
          "tools_called": int,
          "status":       "COMPLETE" | "INCOMPLETE",
        }
    """
    # Execution Context — tools read filtered_records from here
    execution_context: dict = {
        "filtered_records": filtered_records,
    }

    step_results: dict[str, Any] = {}
    tools_called = 0

    logger.info("[Queue Runner] Starting execution — %d steps in queue.", len(queue))

    for step_def in queue:
        step_idx  = step_def["step"]
        tool_name = step_def["tool"]
        raw_args  = step_def.get("args", {})
        step_key  = f"step_{step_idx}"

        # ── 1. Resolve $step_N.key references in args ──────────────────────
        try:
            resolved_args = _resolve_args(raw_args, step_results)
        except (ValueError, KeyError) as exc:
            logger.error(
                "[Queue Runner] Step %d (%s) — arg resolution failed: %s",
                step_idx, tool_name, exc
            )
            step_results[step_key] = {"error": str(exc)}
            tools_called += 1
            continue

        logger.info(
            "[Queue Runner] Step %d | %-24s | args: %s",
            step_idx, tool_name, resolved_args
        )

        # ── 2. Look up the tool ─────────────────────────────────────────────
        tool_obj = TOOL_REGISTRY.get(tool_name)
        if tool_obj is None:
            logger.error("[Queue Runner] Step %d — unknown tool: '%s'", step_idx, tool_name)
            step_results[step_key] = {"error": f"Unknown tool: {tool_name}"}
            tools_called += 1
            continue

        # ── 3. Call the tool's underlying Python function directly ──────────
        # We bypass LangGraph's ToolNode / schema validation so we can inject
        # 'state' (the execution_context) ourselves for tools that need it.
        raw_fn = getattr(tool_obj, "func", tool_obj)
        try:
            if _needs_state(tool_obj):
                result = raw_fn(state=execution_context, **resolved_args)
            else:
                result = raw_fn(**resolved_args)
        except Exception as exc:
            logger.error(
                "[Queue Runner] Step %d (%s) — tool raised exception: %s",
                step_idx, tool_name, exc,
                exc_info=True,
            )
            step_results[step_key] = {"error": str(exc)}
            tools_called += 1
            continue

        step_results[step_key] = result
        tools_called += 1

        log_step(step_idx, tool_name, result)

    # ── Completion check ────────────────────────────────────────────────────
    status = "COMPLETE" if tools_called == len(queue) else "INCOMPLETE"
    logger.info(
        "[Queue Runner] Done — %s | %d/%d steps executed.",
        status, tools_called, len(queue)
    )

    return {
        "queue":        queue,
        "step_results": step_results,
        "queue_total":  len(queue),
        "tools_called": tools_called,
        "status":       status,
    }
