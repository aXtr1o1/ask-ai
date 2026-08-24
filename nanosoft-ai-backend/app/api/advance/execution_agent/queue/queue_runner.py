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

Status values returned by run_queue():
  COMPLETE  — every step ran and zero steps produced an error
  PARTIAL   — every step ran but one or more intermediate steps errored
  FAILED    — final_answer_tool itself errored, meaning no usable answer exists
"""
import logging
from typing import Any

from app.api.advance.execution_agent.tools.tools import (
    # Basic Tools
    count_records,
    sum_values,
    get_average,
    group_by_and_count,
    group_by_and_aggregate,
    join_and_aggregate,
    get_record_fields,
    filter_by_prior_results,
    intersect_record_sets,
    do_math,
    sort_and_limit,
    final_answer_tool,
    # Intelligence Tools
    calculate_age_from_now,
    group_by_time_period,
    calculate_mtbf,
    flag_by_threshold,
    calculate_rate_of_change,
    calculate_percentile,
    forecast_linear,
    compare_date_fields,
    compare_date_fields,
    merge_and_score,
    add_duration_to_date,
    join_and_filter_by_date_diff,
    calculate_date_difference_stats,
)
from app.api.advance.execution_agent.agent.agent_logger    import log_step
from app.api.advance.execution_agent.queue.queue_helpers import (
    _needs_state,
    _step_failed,
    _DependencyError,
    _SafeSkipError,
    _guard_resolved_args,
    _coerce_numeric_args,
    _resolve_args,
)

logger = logging.getLogger("advance.execution.queue_runner")


# =============================================================================
# TOOL REGISTRY — maps tool name → callable tool object
# =============================================================================
TOOL_REGISTRY: dict[str, Any] = {
    # ── Basic Tools ─────────────────────────────────────────────────────────────
    "count_records":           count_records,
    "sum_values":              sum_values,
    "get_average":             get_average,
    "group_by_and_count":      group_by_and_count,
    "group_by_and_aggregate":  group_by_and_aggregate,
    "join_and_aggregate":      join_and_aggregate,
    "get_record_fields":       get_record_fields,
    "filter_by_prior_results": filter_by_prior_results,
    "intersect_record_sets":   intersect_record_sets,
    "do_math":                 do_math,
    "sort_and_limit":          sort_and_limit,
    "final_answer_tool":       final_answer_tool,
    # ── Intelligence Tools ───────────────────────────────────────────────────
    "calculate_age_from_now":       calculate_age_from_now,
    "group_by_time_period":         group_by_time_period,
    "calculate_mtbf":               calculate_mtbf,
    "flag_by_threshold":            flag_by_threshold,
    "calculate_rate_of_change":     calculate_rate_of_change,
    "calculate_percentile":         calculate_percentile,
    "forecast_linear":              forecast_linear,
    "compare_date_fields":          compare_date_fields,
    "merge_and_score":              merge_and_score,
    "add_duration_to_date":         add_duration_to_date,
    "join_and_filter_by_date_diff": join_and_filter_by_date_diff,
    "calculate_date_difference_stats": calculate_date_difference_stats,
}


# =============================================================================
# PUBLIC API
# =============================================================================

def run_queue(queue: list[dict], filtered_records: dict, progress_callback: callable = None) -> dict:
    """Execute the planned queue step by step and return all step results.

    Each step's args are resolved from prior step outputs ($step_N.key references),
    then guarded for unsafe values, then passed to the tool's Python function directly.
    The execution context (filtered_records) is injected into tools that need it.

    Args:
        queue:             List of step dicts produced by the planner agent.
        filtered_records:  Actual data rows per module — set once, never changes.
        progress_callback: Optional callable(message) for streaming progress updates.

    Returns:
        {
          "queue":        original planned queue,
          "step_results": { "step_0": {...}, "step_1": {...}, ... },
          "queue_total":  int,
          "tools_called": int,
          "error_count":  int,
          "status":       "COMPLETE" | "PARTIAL" | "FAILED",
        }
    """
    execution_context: dict = {"filtered_records": filtered_records}
    step_results: dict[str, Any] = {}
    tools_called = 0
    error_count  = 0

    for step_def in queue:
        step_idx  = step_def["step"]
        tool_name = step_def["tool"]
        raw_args  = step_def.get("args", {})
        step_key  = f"step_{step_idx}"

        # ── 1. Resolve $step_N.key references in args ──────────────────────────
        try:
            resolved_args = _resolve_args(raw_args, step_results)

        except _DependencyError as exc:
            # An upstream step that this step depends on already failed
            logger.warning("[Queue Runner] Step %d (%s) — skipped: dependency failed. %s", step_idx, tool_name, exc)
            step_results[step_key] = {"_dep_failed": str(exc)}
            tools_called += 1
            error_count  += 1
            log_step(step_idx, tool_name, step_results[step_key])
            continue

        except (ValueError, KeyError, IndexError) as exc:
            logger.error("[Queue Runner] Step %d (%s) — arg resolution failed: %s", step_idx, tool_name, exc)
            step_results[step_key] = {"_result_type": "error", "error": str(exc)}
            tools_called += 1
            error_count  += 1
            log_step(step_idx, tool_name, step_results[step_key])
            continue

        # ── 1b. Coerce numeric operands for arithmetic tools ───────────────────
        resolved_args = _coerce_numeric_args(tool_name, resolved_args)

        # ── 1c. Guard against semantically unsafe argument values ──────────────
        try:
            _guard_resolved_args(tool_name, resolved_args)
        except _SafeSkipError as exc:
            logger.warning("[Queue Runner] Step %d (%s) — safe-skipped: %s", step_idx, tool_name, exc)
            step_results[step_key] = exc.safe_result
            tools_called += 1
            # Not counted as error — this is a graceful skip, not a failure
            log_step(step_idx, tool_name, exc.safe_result)
            continue

        # ── 2. Look up the tool in the registry ───────────────────────────────
        tool_obj = TOOL_REGISTRY.get(tool_name)
        if tool_obj is None:
            logger.error("[Queue Runner] Step %d — unknown tool: '%s'", step_idx, tool_name)
            step_results[step_key] = {"_result_type": "error", "error": f"Unknown tool: {tool_name}"}
            tools_called += 1
            error_count  += 1
            log_step(step_idx, tool_name, step_results[step_key])
            continue

        # ── 3. Call the tool's Python function directly ───────────────────────
        # We bypass LangGraph's ToolNode so we can inject 'state' (the execution
        # context) ourselves for tools that need filtered_records.
        if progress_callback:
            progress_callback(f"Running '{tool_name}' (step {step_idx})...")

        raw_fn = getattr(tool_obj, "func", tool_obj)
        try:
            if _needs_state(tool_obj):
                result = raw_fn(state=execution_context, **resolved_args)
            else:
                result = raw_fn(**resolved_args)
        except Exception as exc:
            logger.error("[Queue Runner] Step %d (%s) — tool raised exception: %s", step_idx, tool_name, exc, exc_info=True)
            step_results[step_key] = {"_result_type": "error", "error": str(exc)}
            tools_called += 1
            error_count  += 1
            log_step(step_idx, tool_name, step_results[step_key])
            continue

        step_results[step_key] = result
        tools_called += 1
        log_step(step_idx, tool_name, result)

    # ── Determine final status ─────────────────────────────────────────────────
    # Use the actual step index from the last queue item — NOT len(queue)-1.
    # The LLM may number steps starting from 1 or use non-sequential indices.
    last_step_idx  = queue[-1]["step"] if queue else 0
    final_step_key = f"step_{last_step_idx}"
    final_result   = step_results.get(final_step_key, {})

    if _step_failed(final_result):
        status = "FAILED"    # final_answer_tool itself errored — no usable output
    elif error_count > 0:
        status = "PARTIAL"   # intermediate steps errored but an answer was produced
    else:
        status = "COMPLETE"  # every step succeeded cleanly

    return {
        "queue":        queue,
        "step_results": step_results,
        "queue_total":  len(queue),
        "tools_called": tools_called,
        "error_count":  error_count,
        "status":       status,
    }