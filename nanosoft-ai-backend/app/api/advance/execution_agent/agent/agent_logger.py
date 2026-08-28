"""
Execution Agent Logger

Structured terminal logs for the three key moments of the execution agent:

  log_question  — question received + modules selected
  log_queue     — the plan the LLM produced (each step on one line)
  log_step      — result of a single tool execution (concise summary)
  log_completion — final status, tool counts, latency, and final answer
"""
import json
import logging

logger = logging.getLogger("advance.execution")

_SEP = "─" * 55


# =============================================================================
# log_question — called before the LLM planning call
# =============================================================================

def log_question(question: str, modules: list) -> None:
    """Log the incoming question and the modules it will operate on."""
    logger.info("┌─ [Execution Agent] QUESTION")
    logger.info("│  modules : %s", modules)
    logger.info("│  question: %s", question[:200])
    logger.info("└─ %s", _SEP)


# =============================================================================
# log_queue — called after the LLM plan is parsed and validated
# =============================================================================

def log_queue(queue: list) -> None:
    """Log the planned execution queue — one line per step."""
    logger.info("┌─ [Execution Agent] PLAN — %d step(s)", len(queue))
    for step in queue:
        step_idx  = step.get("step", "?")
        tool_name = step.get("tool", "?")
        args      = step.get("args", {})

        # Show the most useful args compactly — skip large lists/dicts
        arg_parts = []
        for k, v in args.items():
            if isinstance(v, (dict, list)):
                arg_parts.append(f"{k}=[...]")
            elif v not in (None, "", [], {}):
                short_v = str(v)[:40]
                arg_parts.append(f"{k}={short_v}")
        arg_str = " | ".join(arg_parts) if arg_parts else "(no args)"

        logger.info("│  step %-2s → %-30s %s", step_idx, tool_name, arg_str)
    logger.info("└─ %s", _SEP)


# =============================================================================
# log_step — called after each tool executes inside run_queue()
# =============================================================================

def log_step(step_idx: int, tool_name: str, result: dict) -> None:
    """Log the result of a single tool execution with a concise summary."""
    if not isinstance(result, dict):
        logger.info("│  [STEP %s] %-28s result=%s", step_idx, tool_name, result)
        return

    # Error / dependency failure — result_type tells apart a real defect (bad
    # arg, unknown field, exception) from the tool running correctly but the
    # data itself having nothing usable to compute from (see tool_helpers.
    # _insufficient / _err). Label the log line accordingly so this is visible
    # per-step, not only in the final Shape Resolver line.
    if "error" in result:
        label = "INSUFFICIENT-DATA" if result.get("_result_type") == "insufficient_data" else "ERROR"
        logger.warning("│  [STEP %s] %-28s %s: %s", step_idx, tool_name, label, str(result["error"])[:120])
        return
    if "_dep_failed" in result:
        label = "DEP-FAILED (insufficient-data)" if result.get("_result_type") == "insufficient_data" else "DEP-FAILED"
        logger.warning("│  [STEP %s] %-28s %s: %s", step_idx, tool_name, label, str(result["_dep_failed"])[:120])
        return
    if "_safe_skip" in result:
        logger.info("│  [STEP %s] %-28s SAFE-SKIP: %s", step_idx, tool_name, result["_safe_skip"])
        return

    # Build a concise summary of the most important output keys
    SUMMARY_KEYS = {
        "count_records":             ["count", "total_records"],
        "sum_values":                ["total_sum", "records_used"],
        "get_average":               ["average", "records_used"],
        "group_by_and_count":        ["total_records", "unique_groups"],
        "group_by_and_aggregate":    ["total_records", "unique_groups"],
        "join_and_aggregate":        ["matched_count", "unique_groups"],
        "get_record_fields":         ["total"],
        "filter_by_prior_results":   ["matched", "total"],
        "intersect_record_sets":     ["count"],
        "do_math":                   ["result", "operation"],
        "combine_grouped_values":    ["unique_groups", "operation"],
        "sort_and_limit":            ["total_in", "total_out"],
        "final_answer_tool":         ["final_value", "status"],
        "calculate_age_from_now":    ["avg_age_days", "total_records"],
        "group_by_time_period":      ["total_records", "period_count"],
        "calculate_mtbf":            ["overall_avg_mtbf_days", "assets_analyzed"],
        "flag_by_threshold":         ["flagged_count", "total_records", "flag_ratio"],
        "calculate_rate_of_change":  ["pct_change", "direction"],
        "calculate_percentile":      ["mean", "records_used"],
        "forecast_linear":           ["data_points", "r_squared"],
        "compare_date_fields":       ["flagged_count", "total_records", "flag_ratio"],
        "merge_and_score":           ["total_groups"],
        "add_duration_to_date":      ["total", "expired_count"],
        "join_and_filter_by_date_diff": ["matched_count", "total_joined"],
    }

    keys_to_show = SUMMARY_KEYS.get(tool_name, [])
    parts = []
    for k in keys_to_show:
        if k in result:
            v = result[k]
            # Truncate long values
            if isinstance(v, (list, dict)):
                parts.append(f"{k}=<{type(v).__name__}({len(v)})>")
            else:
                parts.append(f"{k}={v}")

    # Fallback: show first 3 keys if no summary match
    if not parts:
        for k, v in list(result.items())[:3]:
            if not k.startswith("_"):
                short_v = str(v)[:40] if not isinstance(v, (list, dict)) else f"<{type(v).__name__}({len(v)})>"
                parts.append(f"{k}={short_v}")

    summary = " | ".join(parts) if parts else "(no summary)"
    logger.info("│  [STEP %s] %-28s %s", step_idx, tool_name, summary)


# =============================================================================
# log_completion — called after run_queue() returns
# =============================================================================

def log_completion(
    status:       str,
    tools_called: int,
    queue_total:  int,
    error_count:  int,
    final_value,
    latency:      dict,
) -> None:
    """Log the final execution result — status, counts, latency, and the answer."""
    llm_t   = latency.get("llm_time", 0)
    exec_t  = latency.get("execution_time", 0)
    total_t = latency.get("total_time", 0)

    status_icon = "✓" if status == "COMPLETE" else ("⚠" if status == "PARTIAL" else "✗")

    logger.info("┌─ [Execution Agent] %s %s — %d/%d tools | %d error(s)",
                status_icon, status, tools_called, queue_total, error_count)
    logger.info("│  latency : llm=%.2fs | exec=%.2fs | total=%.2fs", llm_t, exec_t, total_t)

    # Show final answer — truncate large structures
    if isinstance(final_value, dict):
        logger.info("│  answer  : %s", json.dumps(final_value, default=str)[:300])
    elif isinstance(final_value, list):
        logger.info("│  answer  : list[%d items]", len(final_value))
    elif final_value is not None:
        logger.info("│  answer  : %s", str(final_value)[:300])
    else:
        logger.info("│  answer  : (none)")

    logger.info("└─ %s", _SEP)
