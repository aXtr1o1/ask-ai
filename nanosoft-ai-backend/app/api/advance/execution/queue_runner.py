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
import re
from typing import Any

from app.api.advance.execution.tools import (
    # Basic Tools
    count_records,
    sum_values,
    get_average,
    group_by_and_count,
    group_by_and_aggregate,
    join_and_aggregate,
    get_record_fields,
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
    merge_and_score,
    add_duration_to_date,
)
from app.api.advance.execution.agent_logger import log_step

logger = logging.getLogger("advance.execution.queue_runner")


# =============================================================================
# TOOL REGISTRY — name → LangChain tool object
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
    "do_math":                 do_math,
    "sort_and_limit":          sort_and_limit,
    "final_answer_tool":       final_answer_tool,
    # ── Intelligence Tools ───────────────────────────────────────────────────
    "calculate_age_from_now":  calculate_age_from_now,
    "group_by_time_period":    group_by_time_period,
    "calculate_mtbf":          calculate_mtbf,
    "flag_by_threshold":       flag_by_threshold,
    "calculate_rate_of_change": calculate_rate_of_change,
    "calculate_percentile":    calculate_percentile,
    "forecast_linear":         forecast_linear,
    "compare_date_fields":     compare_date_fields,
    "merge_and_score":         merge_and_score,
    "add_duration_to_date":    add_duration_to_date,
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

    field = parts[1]        # e.g. "count"  or  "groups[0].value"  or  "stats.average"

    # ── List-index notation: "groups[0].value" ─────────────────────────────
    # The LLM references the top item from a list field: $step_1.groups[0].value
    import re
    list_idx_match = re.match(r'^(\w+)\[(\d+)\]\.?(.*)?$', field)
    if list_idx_match:
        list_key   = list_idx_match.group(1)   # "groups"
        idx        = int(list_idx_match.group(2))  # 0
        sub_key    = list_idx_match.group(3)   # "value"  (may be empty)

        if not isinstance(step_result, dict) or list_key not in step_result:
            available = list(step_result.keys()) if isinstance(step_result, dict) else "N/A"
            raise KeyError(
                f"Reference '{val}': list field '{list_key}' not found in step '{step_key}'. "
                f"Available keys: {available}"
            )
        the_list = step_result[list_key]
        if not isinstance(the_list, list):
            raise KeyError(
                f"Reference '{val}': field '{list_key}' in step '{step_key}' "
                f"is not a list (got {type(the_list).__name__})."
            )
        if idx >= len(the_list):
            raise IndexError(
                f"Reference '{val}': index [{idx}] out of range — "
                f"list '{list_key}' has only {len(the_list)} item(s)."
            )
        item = the_list[idx]
        if sub_key:
            if not isinstance(item, dict) or sub_key not in item:
                available = list(item.keys()) if isinstance(item, dict) else "N/A"
                raise KeyError(
                    f"Reference '{val}': sub-key '{sub_key}' not found in "
                    f"{list_key}[{idx}]. Available keys: {available}"
                )
            return item[sub_key]
        return item
    # ── End list-index notation ─────────────────────────────────────────────

    if not isinstance(step_result, dict) or field not in step_result:
        # Try dot-notation nested key: "stats.average" → step_result["stats"]["average"]
        if "." in field:
            top_key, sub_key = field.split(".", 1)
            if isinstance(step_result, dict) and top_key in step_result:
                nested = step_result[top_key]
                if isinstance(nested, dict) and sub_key in nested:
                    return nested[sub_key]
                # nested is not a dict or sub_key missing
                available_sub = list(nested.keys()) if isinstance(nested, dict) else "not a dict"
                raise KeyError(
                    f"Reference '{val}': sub-key '{sub_key}' not found in "
                    f"step '{step_key}' → '{top_key}'. Available: {available_sub}"
                )
        available = list(step_result.keys()) if isinstance(step_result, dict) else "N/A"
        raise KeyError(
            f"Reference '{val}': field '{field}' not found in step '{step_key}'. "
            f"Available keys: {available}"
        )
    return step_result[field]


class _DependencyError(Exception):
    """Raised when a $ref points to a step that already failed."""


class _SafeSkipError(Exception):
    """
    Raised when a resolved argument value is semantically dangerous for the
    tool that will consume it (e.g. zero denominator for DIV, None for a
    numeric field, empty list for sort_and_limit).

    Unlike _DependencyError (upstream step crashed), _SafeSkipError means the
    upstream step SUCCEEDED but its output value cannot safely be fed into this
    tool.  We short-circuit the step with a pre-built safe_result so the chain
    stays alive — subsequent steps that depend on THIS step via a $ref still
    receive a usable (though possibly null) value.
    """
    def __init__(self, reason: str, safe_result: dict):
        super().__init__(reason)
        self.safe_result = safe_result


# Mapping: tool_name → argument-specific guards
# Each guard is  (arg_name, check_fn, safe_result_factory)
#   arg_name          — the resolved arg key to inspect
#   check_fn          — receives the resolved value, returns True if UNSAFE
#   safe_result_factory — called with (tool_name, args) to produce the safe output
_ARG_GUARDS: dict[str, list[tuple]] = {
    # DIV / MOD with b == 0 → result undefined, avoid ZeroDivisionError
    "do_math": [
        (
            "b",
            lambda v, args: args.get("operation", "").upper() in ("DIV", "MOD")
                            and _is_zero_or_none(v),
            lambda tool, args: {
                "operation": args.get("operation", "DIV").upper(),
                "a": args.get("a"),
                "b": args.get("b"),
                "result": None,
                "_safe_skip": "denominator_was_zero_or_null — result set to None",
            },
        ),
    ],
    # sort_and_limit with an empty data list → return empty result immediately
    "sort_and_limit": [
        (
            "data",
            lambda v, args: isinstance(v, list) and len(v) == 0,
            lambda tool, args: {
                "sorted_data": [],
                "total_in": 0,
                "total_out": 0,
                "sort_by": args.get("sort_by", ""),
                "order": args.get("order", "DESC"),
                "limit": args.get("limit", 0),
                "_safe_skip": "input_data_list_was_empty — no records to sort",
            },
        ),
        # data resolves to a non-list (LLM passed whole step result instead of a key)
        (
            "data",
            lambda v, args: not isinstance(v, list),
            lambda tool, args: {
                "sorted_data": [],
                "total_in": 0,
                "total_out": 0,
                "sort_by": args.get("sort_by", ""),
                "order": args.get("order", "DESC"),
                "limit": args.get("limit", 0),
                "_safe_skip": f"data arg resolved to {type(args.get('data')).__name__} not list — check $ref key",
            },
        ),
    ],
    # forecast_linear with insufficient data points
    "forecast_linear": [
        (
            "data",
            lambda v, args: not isinstance(v, list) or len(v) < 2,
            lambda tool, args: {
                "forecast": [],
                "model_slope": None,
                "model_intercept": None,
                "r_squared": None,
                "periods_ahead": args.get("periods_ahead", 3),
                "data_points": 0,
                "value_key": args.get("value_key", "count"),
                "_safe_skip": "forecast_linear requires at least 2 data points — insufficient periods data",
            },
        ),
    ],
    # calculate_rate_of_change: if either value is None/zero-baseline
    "calculate_rate_of_change": [
        (
            "b",
            lambda v, args: _is_zero_or_none(v),
            lambda tool, args: {
                "a": args.get("a"),
                "b": args.get("b"),
                "pct_change": None,
                "direction": "unknown",
                "_safe_skip": "baseline value (b) is zero or null — rate of change undefined",
            },
        ),
    ],
    # flag_by_threshold: if threshold is None
    "flag_by_threshold": [
        (
            "threshold",
            lambda v, args: v is None or (isinstance(v, str) and v.strip().lower() in ("none", "null", "")),
            lambda tool, args: {
                "flagged_count": 0,
                "total_records": 0,
                "flag_ratio": 0.0,
                "flagged_records": [],
                "groups": [],
                "_safe_skip": "threshold resolved to None — cannot flag records without a threshold",
            },
        ),
    ],
    # get_average: if the field resolves to empty
    "get_average": [
        (
            "field",
            lambda v, args: not v,
            lambda tool, args: {
                "module": args.get("module"),
                "field": args.get("field"),
                "average": None,
                "records_used": 0,
                "_safe_skip": "field_name_resolved_to_empty",
            },
        ),
    ],
}


def _is_zero_or_none(v: Any) -> bool:
    """Return True when v is None, the string 'None', 0, 0.0, or '0'."""
    if v is None:
        return True
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v == 0
    if isinstance(v, str):
        s = v.strip().lower()
        return s in ("0", "0.0", "none", "null", "")
    return False


def _guard_resolved_args(tool_name: str, resolved_args: dict) -> None:
    """
    Check resolved argument values against known dangerous patterns for the
    given tool.  Raises _SafeSkipError with a pre-built safe_result if an
    unsafe pattern is detected so the queue runner can short-circuit cleanly.

    Called AFTER _resolve_args, BEFORE the tool is invoked.
    """
    guards = _ARG_GUARDS.get(tool_name, [])
    for arg_name, check_fn, result_factory in guards:
        value = resolved_args.get(arg_name)
        if check_fn(value, resolved_args):
            safe_result = result_factory(tool_name, resolved_args)
            raise _SafeSkipError(
                f"Tool '{tool_name}' arg '{arg_name}' = {value!r} is semantically "
                f"unsafe — short-circuiting step with safe result.",
                safe_result=safe_result,
            )


# First _resolve_value and _resolve_args definitions removed — dead code.
# The active (more complete) definitions are below.


def _coerce_numeric_args(tool_name: str, resolved_args: dict) -> dict:
    """
    Coerce None/string numeric arguments to float for arithmetic tools.

    For do_math: only coerce when operation is DIV or MOD.
      DIV/MOD with None denominator is caught by _ARG_GUARDS → safe null result.
      ADD/SUB/MUL with None is semantically invalid — leave as-is so the tool
      can return a meaningful error instead of silently computing a wrong result.

    For calculate_rate_of_change: the tool handles None internally and returns
      a structured error — no coercion needed here.
    """
    if tool_name == "do_math":
        op = str(resolved_args.get("operation", "")).upper()
        if op not in ("DIV", "MOD"):
            # Not a division-type op — don't coerce, let tool handle or error
            return resolved_args
        # DIV/MOD: coerce b so _ARG_GUARDS can catch zero-denominator cleanly
        patched = dict(resolved_args)
        for arg in ("a", "b"):
            v = patched.get(arg)
            if v is None or (isinstance(v, str) and v.strip().lower() in ("none", "null", "")):
                logger.warning(
                    "[Queue Runner] do_math %s arg '%s' is None — coercing to 0.",
                    op, arg,
                )
                patched[arg] = 0
            else:
                try:
                    patched[arg] = float(str(v))
                except (ValueError, TypeError):
                    patched[arg] = 0
        return patched

    return resolved_args
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
    # Dictionary — check for LLM dict-style result reference FIRST
    # ------------------------------------------------------------------
    if isinstance(value, dict):
        # LLM sometimes emits {"step": 1, "key": "count"} instead of
        # the canonical "$step_1.count" string reference.  Detect and
        # resolve this pattern before falling through to generic recursion.
        step_val = value.get("step")
        key_val  = value.get("key")
        if (
            step_val is not None
            and key_val is not None
            and isinstance(key_val, str)
            and len(value) == 2           # only these two keys — nothing extra
        ):
            synthetic_ref = f"$step_{step_val}.{key_val}"
            logger.debug(
                "[Queue Runner] dict-ref %r → resolving as '%s'",
                value, synthetic_ref,
            )
            return _resolve_ref(synthetic_ref, step_results)

        # Generic dict → resolve every value recursively
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

        # ── 1b. Coerce numeric args (None → 0) for arithmetic tools ─────────
        resolved_args = _coerce_numeric_args(tool_name, resolved_args)

        # ── 1c. Semantic value guard — catch dangerous values before tool call
        try:
            _guard_resolved_args(tool_name, resolved_args)
        except _SafeSkipError as exc:
            # The resolved value is semantically unsafe (e.g. zero denominator).
            # Use the pre-built safe_result so downstream $refs still get a value
            # and the chain can continue rather than hard-failing.
            logger.warning(
                "[Queue Runner] Step %d (%s) — safe-skipped: %s",
                step_idx, tool_name, exc,
            )
            step_results[step_key] = exc.safe_result
            tools_called += 1
            # Not counted as error_count — it's a graceful skip, not a failure.
            log_step(step_idx, tool_name, exc.safe_result)
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
    # Use the actual step index from the last queue item — NOT len(queue)-1.
    # The LLM may number steps starting from 1 or use non-sequential indices.
    last_step_idx  = queue[-1]["step"] if queue else 0
    final_step_key = f"step_{last_step_idx}"
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
