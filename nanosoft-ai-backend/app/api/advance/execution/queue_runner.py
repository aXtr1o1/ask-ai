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

Fix 1 — Dependency-aware error detection:
  Before resolving a $step_N.key ref, we check if step_N itself already failed.
  If it did, we immediately mark the current step as "DEPENDENCY_FAILED" and skip
  calling the tool. This stops silent error cascades dead in their tracks.

Fix 2 — Accurate status reporting:
  STATUS is now one of three values:
    COMPLETE  — all steps ran and zero steps produced an error or dependency failure
    PARTIAL   — all steps ran but one or more steps produced an error (non-fatal)
    FAILED    — final_answer_tool itself errored, meaning no usable answer exists
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
    sort_and_limit,
    group_by_and_aggregate,
    count_records_multi,
    get_record_fields,
    final_answer_tool,
)
from app.api.advance.execution.agent_logger import log_step

logger = logging.getLogger("advance.execution.queue_runner")


# =============================================================================
# TOOL REGISTRY — name → LangChain tool object
# =============================================================================
TOOL_REGISTRY: dict[str, Any] = {
    "count_records":           count_records,
    "sum_values":              sum_values,
    "get_average":             get_average,
    "get_minimum":             get_minimum,
    "get_maximum":             get_maximum,
    "calculate_time_between":  calculate_time_between,
    "group_by_and_count":      group_by_and_count,
    "get_unique_values":       get_unique_values,
    "join_records":            join_records,
    "do_math":                 do_math,
    "sort_and_limit":          sort_and_limit,
    "group_by_and_aggregate":  group_by_and_aggregate,
    "count_records_multi":     count_records_multi,
    "get_record_fields":       get_record_fields,
    "final_answer_tool":       final_answer_tool,
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


def _step_failed(step_result: Any) -> bool:
    """
    Return True if a step result represents a failure.
    A step failed if its output dict contains an 'error' or '_dep_failed' key.
    Plain values (ints, strings, lists) are never treated as failures.
    """
    if isinstance(step_result, dict):
        return "error" in step_result or "_dep_failed" in step_result
    return False


def _resolve_ref(val: Any, step_results: dict) -> Any:
    """
    Resolve a "$step_N.key" reference to its actual value from step_results.
    Non-reference values pass through unchanged.

    Fix 1 — Dependency awareness:
      Before resolving the field, we check if the referenced step itself failed.
      If it did, we raise DependencyError immediately instead of propagating
      a garbage value into the next tool call.

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

    # ── Fix 1: detect upstream failure before touching the result ──────────
    if _step_failed(step_result):
        upstream_error = (
            step_result.get("error")
            or step_result.get("_dep_failed")
            or "upstream step failed"
        )
        raise _DependencyError(
            f"Step '{step_key}' previously failed — cannot resolve '{val}'. "
            f"Upstream error: {upstream_error}"
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


class _DependencyError(Exception):
    """Raised when a $ref points to a step that already failed."""


def _resolve_value(value: Any, step_results: dict) -> Any:
    """
    Recursively resolve $step_N.key references inside any JSON structure.

    Supported:
      - "$step_0.count"
      - ["$step_0.count", "$step_1.result"]
      - {"Count": "$step_0.count"}
      - Nested dict/list combinations
    """

    # ------------------------------------------------------------------
    # String -> resolve $step reference
    # ------------------------------------------------------------------
    if isinstance(value, str):
        # Guard: LLM sometimes serialises dicts/lists as a Python-style string.
        # e.g. "{'By Mail': '$step_0.count', 'By Call': '$step_1.count'}"
        # Parse it so nested $step refs get resolved correctly.
        if value.startswith(("{", "[")):
            import ast
            try:
                parsed = ast.literal_eval(value)
                if isinstance(parsed, (dict, list)):
                    return _resolve_value(parsed, step_results)
            except (ValueError, SyntaxError):
                pass
        return _resolve_ref(value, step_results)

    # ------------------------------------------------------------------
    # List -> resolve every item recursively
    # ------------------------------------------------------------------
    if isinstance(value, list):
        resolved_list = [_resolve_value(item, step_results) for item in value]

        # Preserve existing flatten behaviour
        if (
            resolved_list
            and all(isinstance(item, list) for item in resolved_list)
        ):
            flattened = []
            for sublist in resolved_list:
                flattened.extend(sublist)
            return flattened

        return resolved_list

    # ------------------------------------------------------------------
    # Dictionary -> resolve every value recursively
    # ------------------------------------------------------------------
    if isinstance(value, dict):
        return {
            key: _resolve_value(val, step_results)
            for key, val in value.items()
        }

    # ------------------------------------------------------------------
    # Numbers / bool / None / everything else
    # ------------------------------------------------------------------
    return value


def _resolve_args(args: dict, step_results: dict) -> dict:
    """
    Resolve all $step_N.key references in the args dictionary.

    Supports:
      ✔ strings
      ✔ lists
      ✔ dictionaries
      ✔ nested dictionaries
      ✔ nested lists
      ✔ any combination of the above
    """
    return {
        key: _resolve_value(value, step_results)
        for key, value in args.items()
    }

# =============================================================================
# PUBLIC API
# =============================================================================

def run_queue(queue: list[dict], filtered_records: dict, progress_callback: callable = None) -> dict:
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
          "error_count":  int,   ← NEW: number of steps that produced an error
          "status":       "COMPLETE" | "PARTIAL" | "FAILED",
        }

    Status meanings:
        COMPLETE — every step ran and zero errors occurred
        PARTIAL  — every step ran but ≥1 step errored (answer may still be useful)
        FAILED   — the final_answer_tool step itself errored (no usable answer)
    """
    # Execution Context — tools read filtered_records from here
    execution_context: dict = {
        "filtered_records": filtered_records,
    }

    step_results: dict[str, Any] = {}
    tools_called = 0
    error_count  = 0

    for step_def in queue:
        step_idx  = step_def["step"]
        tool_name = step_def["tool"]
        raw_args  = step_def.get("args", {})
        step_key  = f"step_{step_idx}"

        # ── 1. Resolve $step_N.key references in args ──────────────────────
        try:
            resolved_args = _resolve_args(raw_args, step_results)

        except _DependencyError as exc:
            # Fix 1: upstream step failed — mark this step as dep-failed and move on
            logger.warning(
                "[Queue Runner] Step %d (%s) — skipped: dependency failed. %s",
                step_idx, tool_name, exc,
            )
            step_results[step_key] = {"_dep_failed": str(exc)}
            tools_called += 1
            error_count  += 1
            log_step(step_idx, tool_name, step_results[step_key])
            continue

        except (ValueError, KeyError) as exc:
            logger.error(
                "[Queue Runner] Step %d (%s) — arg resolution failed: %s",
                step_idx, tool_name, exc,
            )
            step_results[step_key] = {"error": str(exc)}
            tools_called += 1
            error_count  += 1
            log_step(step_idx, tool_name, step_results[step_key])
            continue

        # ── 2. Look up the tool ─────────────────────────────────────────────
        tool_obj = TOOL_REGISTRY.get(tool_name)
        if tool_obj is None:
            logger.error("[Queue Runner] Step %d — unknown tool: '%s'", step_idx, tool_name)
            step_results[step_key] = {"error": f"Unknown tool: {tool_name}"}
            tools_called += 1
            error_count  += 1
            log_step(step_idx, tool_name, step_results[step_key])
            continue

        # ── 3. Call the tool's underlying Python function directly ──────────
        # We bypass LangGraph's ToolNode / schema validation so we can inject
        # 'state' (the execution_context) ourselves for tools that need it.
        if progress_callback:
            progress_callback(f"Running '{tool_name}' (step {step_idx})...")
            
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
            error_count  += 1
            log_step(step_idx, tool_name, step_results[step_key])
            continue

        step_results[step_key] = result
        tools_called += 1
        log_step(step_idx, tool_name, result)

    # ── Fix 2: Accurate status reporting ────────────────────────────────────
    # Determine how many of the non-final steps errored vs succeeded
    final_step_key = f"step_{len(queue) - 1}"
    final_result   = step_results.get(final_step_key, {})

    if _step_failed(final_result):
        # The answer step itself failed — no usable output
        status = "FAILED"
    elif error_count > 0:
        # Some intermediate steps errored but final_answer_tool produced a value
        status = "PARTIAL"
    else:
        # Every single step succeeded cleanly
        status = "COMPLETE"

    return {
        "queue":        queue,
        "step_results": step_results,
        "queue_total":  len(queue),
        "tools_called": tools_called,
        "error_count":  error_count,
        "status":       status,
    }
