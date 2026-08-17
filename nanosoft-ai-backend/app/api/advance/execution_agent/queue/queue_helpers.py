"""
Queue Runner — Helper Functions

These are the internal building blocks used by run_queue() in queue_runner.py.
Nothing here is part of the public API — import run_queue() from queue_runner.py.

  _needs_state          — detects if a tool function requires the execution context injected
  _step_failed          — checks if a prior step's result contains an error
  _DependencyError      — raised when a $ref points to a step that already failed
  _SafeSkipError        — raised when a resolved arg value is semantically unsafe for the tool
  _is_zero_or_none      — guard utility: True for None, 0, "0", "none", "null"
  _ARG_GUARDS           — per-tool rules that trigger _SafeSkipError before tool execution
  _guard_resolved_args  — applies _ARG_GUARDS for a given tool after arg resolution
  _coerce_numeric_args  — converts string/None operands to float for arithmetic tools
  _resolve_ref          — resolves a single "$step_N.key" string to its actual value
  _resolve_value        — recursively resolves $refs inside any nested structure (list, dict, str)
  _resolve_args         — resolves all $refs in a step's args dict
"""
import logging
import re
from typing import Any

logger = logging.getLogger("advance.execution.queue_runner")


# =============================================================================
# _needs_state
# =============================================================================

def _needs_state(tool_obj: Any) -> bool:
    """Return True if the tool's Python function accepts a 'state' parameter.

    Tools that read filtered_records use InjectedState() and need 'state' injected
    manually when called directly — it is hidden from the LLM's tool schema.
    """
    import inspect
    raw_fn = getattr(tool_obj, "func", tool_obj)
    return "state" in inspect.signature(raw_fn).parameters


# =============================================================================
# _step_failed
# =============================================================================

def _step_failed(step_result: Any) -> bool:
    """Return True if a step result represents a failure.

    A step failed if its output dict contains an 'error' or '_dep_failed' key.
    Plain values (ints, strings, lists) are never treated as failures.
    """
    if isinstance(step_result, dict):
        return "error" in step_result or "_dep_failed" in step_result
    return False


# =============================================================================
# _DependencyError
# =============================================================================

class _DependencyError(Exception):
    """Raised when a $ref points to a step that already failed.

    Used by _resolve_ref() to stop error cascades before a tool is called
    with garbage data from a broken upstream step.
    """


# =============================================================================
# _SafeSkipError
# =============================================================================

class _SafeSkipError(Exception):
    """Raised when a resolved argument value is semantically unsafe for its tool.

    Unlike _DependencyError (upstream step crashed), _SafeSkipError means the
    upstream step SUCCEEDED but its output value cannot safely be fed into this
    tool — e.g. a zero denominator for DIV, or an empty list for sort_and_limit.

    Carries a pre-built safe_result dict so the queue can continue rather than
    hard-failing: downstream steps that depend on this step via a $ref still
    receive a usable (though possibly null) value.
    """
    def __init__(self, reason: str, safe_result: dict):
        super().__init__(reason)
        self.safe_result = safe_result


# =============================================================================
# _is_zero_or_none
# =============================================================================

def _is_zero_or_none(v: Any) -> bool:
    """Return True when v is None, the string 'None'/'null'/'', 0, or 0.0."""
    if v is None:
        return True
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v == 0
    if isinstance(v, str):
        return v.strip().lower() in ("0", "0.0", "none", "null", "")
    return False


# =============================================================================
# _ARG_GUARDS
# Per-tool rules: (arg_name, check_fn, safe_result_factory)
#   check_fn          — receives (value, resolved_args), returns True if UNSAFE
#   safe_result_factory — called with (tool_name, args) to produce the safe output
# Applied by _guard_resolved_args() AFTER _resolve_args(), BEFORE tool execution.
# =============================================================================
_ARG_GUARDS: dict[str, list[tuple]] = {
    # DIV / MOD with b == 0 → division undefined
    "do_math": [
        (
            "b",
            lambda v, args: args.get("operation", "").upper() in ("DIV", "MOD")
                            and _is_zero_or_none(v),
            lambda tool, args: {
                "_result_type": "single_number",
                "operation": args.get("operation", "DIV").upper(),
                "a": args.get("a"),
                "b": args.get("b"),
                "result": None,
                "_safe_skip": "denominator_was_zero_or_null — result set to None",
            },
        ),
        # operand a is None for ANY operation → result undefined
        (
            "a",
            lambda v, args: v is None or (isinstance(v, str) and v.strip().lower() in ("none", "null", "")),
            lambda tool, args: {
                "_result_type": "single_number",
                "operation": args.get("operation", "").upper(),
                "a": None,
                "b": args.get("b"),
                "result": None,
                "_safe_skip": "operand_a_was_none — result set to None",
            },
        ),
    ],
    # sort_and_limit with an empty data list → nothing to sort
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
        # data resolved to a non-list (LLM passed whole step result instead of a specific key)
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
    # forecast_linear requires at least 2 data points for regression
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
    # calculate_rate_of_change: zero baseline → percentage change undefined
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
    # flag_by_threshold: threshold is None → cannot evaluate condition
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
    # filter_by_prior_results: empty match_values → no records can match
    "filter_by_prior_results": [
        (
            "match_values",
            lambda v, args: v is None or (isinstance(v, list) and len(v) == 0),
            lambda tool, args: {
                "_result_type": "record_set",
                "module": args.get("module", ""),
                "match_field": args.get("match_field", ""),
                "total": 0,
                "matched": 0,
                "fields_returned": args.get("fields", []) or [],
                "records": [],
                "_safe_skip": "match_values was empty or None — returning empty record set",
            },
        ),
    ],
    # get_average: empty field name → tool cannot compute average
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


# =============================================================================
# _guard_resolved_args
# =============================================================================

def _guard_resolved_args(tool_name: str, resolved_args: dict) -> None:
    """Check resolved arg values against known dangerous patterns for the tool.

    Raises _SafeSkipError with a pre-built safe_result if an unsafe pattern is
    detected, so the queue runner can short-circuit the step cleanly without
    crashing or propagating bad data downstream.

    Called AFTER _resolve_args(), BEFORE the tool is invoked.
    """
    for arg_name, check_fn, result_factory in _ARG_GUARDS.get(tool_name, []):
        value = resolved_args.get(arg_name)
        if check_fn(value, resolved_args):
            raise _SafeSkipError(
                f"Tool '{tool_name}' arg '{arg_name}' = {value!r} is semantically "
                f"unsafe — short-circuiting step with safe result.",
                safe_result=result_factory(tool_name, resolved_args),
            )


# =============================================================================
# _coerce_numeric_args
# =============================================================================

def _coerce_numeric_args(tool_name: str, resolved_args: dict) -> dict:
    """Convert string/None numeric operands to float for arithmetic tools.

    For do_math: coerces 'a' and 'b' so _ARG_GUARDS can detect None operands
    cleanly instead of the tool receiving raw None or the string "None" and crashing.
    Non-parseable values are left as None so the guards can safe-skip the step.
    """
    if tool_name == "do_math":
        patched = dict(resolved_args)
        for arg in ("a", "b"):
            v = patched.get(arg)
            if v is None or (isinstance(v, str) and v.strip().lower() in ("none", "null", "")):
                patched[arg] = None   # let _ARG_GUARDS detect and safe-skip
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                patched[arg] = float(v)
            else:
                try:
                    patched[arg] = float(str(v))
                except (ValueError, TypeError):
                    patched[arg] = None
        return patched
    return resolved_args


# =============================================================================
# _resolve_ref
# =============================================================================

def _resolve_ref(val: Any, step_results: dict) -> Any:
    """Resolve a single "$step_N.key" reference string to its actual value.

    Non-reference values (numbers, plain strings, None) pass through unchanged.

    Supported access patterns:
      "$step_0.count"             → step_results["step_0"]["count"]
      "$step_1.groups[0].value"   → first element of the groups list, then its .value
      "$step_1.groups[*].AssetTagNo" → list of AssetTagNo values across all groups
      "$step_1.groups[?WoStatus=='Closed'].count" → count from the first matching group
      "$step_0.stats.average"     → nested dot-notation
      "$step_2"                   → whole step result dict
      "any plain value"           → returned as-is

    Raises:
      _DependencyError  — if the referenced step itself previously failed
      ValueError        — if the referenced step has not run yet
      KeyError / IndexError — if the key or index does not exist in the result
    """
    if not isinstance(val, str) or not val.startswith("$step_"):
        return val  # plain value — pass through

    ref      = val[1:]               # strip "$"  →  "step_1.count"
    parts    = ref.split(".", 1)
    step_key = parts[0]              # "step_1"

    step_result = step_results.get(step_key)
    if step_result is None:
        raise ValueError(
            f"Reference '{val}' refers to step '{step_key}' which has not run yet "
            f"or does not exist. Available steps: {list(step_results.keys())}"
        )

    # Block immediately if the referenced step failed — don't propagate garbage
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
        return step_result  # whole dict — no field specified

    field = parts[1]   # e.g. "count"  /  "groups[0].value"  /  "stats.average"

    # ── List-index notation: "groups[0].value"  or  "groups[*].AssetTagNo" ──
    list_idx_match = re.match(r'^(\w+)\[(\*|\d+)\]\.?(.*)?$', field)
    if list_idx_match:
        list_key = list_idx_match.group(1)   # "groups"
        raw_idx  = list_idx_match.group(2)   # "*" or "0"
        sub_key  = list_idx_match.group(3)   # "value"  (may be empty)

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

        # Wildcard [*] — return a list of sub_key values from every item
        if raw_idx == "*":
            if sub_key:
                return [item[sub_key] for item in the_list if isinstance(item, dict) and sub_key in item]
            return the_list

        idx = int(raw_idx)
        if idx >= len(the_list):
            if idx == 0 and len(the_list) == 0:
                # Index 0 on an empty list — safe fallback for count/value metrics
                return 0 if sub_key in ("count", "value", "total", "matched_count", "total_records") else None
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

    # ── Conditional filter: "groups[?WoStatus=='Closed'].count" ──────────────
    # Returns a safe fallback (0 or None) rather than crashing on missing data.
    cond_match = re.match(r'^(\w+)\[\?\s*(\w+)\s*==\s*[\'"]?([^\'"]+)[\'"]?\s*\]\.?(.*)?$', field)
    if cond_match:
        list_key     = cond_match.group(1)
        target_field = cond_match.group(2)
        target_val   = cond_match.group(3).strip()
        sub_key      = cond_match.group(4)

        def _safe_fallback(key):
            return 0 if key in ("count", "value", "total", "matched_count", "total_records") else None

        try:
            if not isinstance(step_result, dict) or list_key not in step_result:
                logger.warning("[Queue Runner] Conditional ref '%s': list field '%s' not in step '%s'.", val, list_key, step_key)
                return _safe_fallback(sub_key)

            the_list = step_result[list_key]
            if not isinstance(the_list, list):
                logger.warning("[Queue Runner] Conditional ref '%s': '%s' is not a list.", val, list_key)
                return _safe_fallback(sub_key)

            for item in the_list:
                if isinstance(item, dict) and str(item.get(target_field, "")).strip().lower() == target_val.lower():
                    if sub_key:
                        if sub_key in item:
                            return item[sub_key]
                        logger.warning("[Queue Runner] Conditional ref '%s': sub-key '%s' not in matched item.", val, sub_key)
                        return _safe_fallback(sub_key)
                    return item

            return _safe_fallback(sub_key)  # no matching item found

        except Exception as exc:
            logger.warning("[Queue Runner] Conditional ref '%s' failed: %s.", val, exc)
            return _safe_fallback(sub_key)

    # ── Key alias resolution: "count" ↔ "total_records" ↔ "total" ────────────
    _KEY_ALIASES = {
        "count":         ["total_records", "total", "matched_count"],
        "total":         ["total_records", "count", "matched_count"],
        "total_records": ["count", "total"],
    }
    if isinstance(step_result, dict) and field not in step_result:
        for alias in _KEY_ALIASES.get(field, []):
            if alias in step_result:
                logger.debug("[Queue Runner] Alias resolution: '%s' → '%s' in step '%s'", field, alias, step_key)
                return step_result[alias]

    # ── Dot-notation nested key: "stats.average" → result["stats"]["average"] ─
    if not isinstance(step_result, dict) or field not in step_result:
        if "." in field:
            top_key, sub_key = field.split(".", 1)
            if isinstance(step_result, dict) and top_key in step_result:
                nested = step_result[top_key]
                if isinstance(nested, dict) and sub_key in nested:
                    return nested[sub_key]
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


# =============================================================================
# _resolve_value
# =============================================================================

def _resolve_value(value: Any, step_results: dict) -> Any:
    """Recursively resolve $step_N.key references inside any JSON structure.

    Handles strings, lists, dicts, and any nested combination. Lists of resolved
    lists are automatically flattened (e.g. when multiple $refs each return a list).
    Also handles the LLM dict-style reference pattern: {"step": 1, "key": "count"}.
    """
    if isinstance(value, str):
        return _resolve_ref(value, step_results)

    if isinstance(value, list):
        resolved_list = [_resolve_value(item, step_results) for item in value]
        # Flatten if every resolved item is itself a list
        if resolved_list and all(isinstance(item, list) for item in resolved_list):
            flattened = []
            for sublist in resolved_list:
                flattened.extend(sublist)
            return flattened
        return resolved_list

    if isinstance(value, dict):
        # LLM sometimes emits {"step": 1, "key": "count"} instead of "$step_1.count"
        step_val = value.get("step")
        key_val  = value.get("key")
        if step_val is not None and key_val is not None and isinstance(key_val, str) and len(value) == 2:
            synthetic_ref = f"$step_{step_val}.{key_val}"
            logger.debug("[Queue Runner] dict-ref %r → resolving as '%s'", value, synthetic_ref)
            return _resolve_ref(synthetic_ref, step_results)
        return {k: _resolve_value(v, step_results) for k, v in value.items()}

    return value  # int, float, bool, None — pass through unchanged


# =============================================================================
# _resolve_args
# =============================================================================

def _resolve_args(args: dict, step_results: dict) -> dict:
    """Resolve all $step_N.key references in a step's args dict.

    Calls _resolve_value on every arg value so strings, lists, dicts, and nested
    combinations are all fully resolved before the tool is called.
    """
    return {key: _resolve_value(value, step_results) for key, value in args.items()}
