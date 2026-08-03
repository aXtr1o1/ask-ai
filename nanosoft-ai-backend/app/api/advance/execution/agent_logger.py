"""
agent_logger.py — Logging for the Queue-Driven Execution Agent.

Log format per question:

  QUESTION : <question text>
  MODULES  : ['ppm', 'bdm']
  -------------------------------------------------------
  QUEUE    : 3 steps planned
    [0] count_records        module=ppm
    [1] do_math              operation=DIV | a=$step_0.count | b=100
    [2] final_answer_tool    result_ref=$step_1.result
  -------------------------------------------------------
    STEP 0  count_records    → count=48
    STEP 1  do_math          → result=0.48
    STEP 2  final_answer     → 0.48
  -------------------------------------------------------
  STATUS   : COMPLETE  (3/3 steps, 0 errors)
  ANSWER   : 0.48

Status values:
  COMPLETE — all steps ran, zero errors
  PARTIAL  — all steps ran, ≥1 intermediate step errored
  FAILED   — final_answer_tool itself errored, no usable answer
"""
import logging

logger = logging.getLogger("advance.execution")

DASH = "-" * 55


# =============================================================================
# Public functions — called from agent.py, planner.py, queue_runner.py
# =============================================================================

def log_question(question: str, modules: list):
    """Log the incoming question and which modules are involved."""
    logger.info("")
    logger.info("QUESTION : %s", question)
    logger.info("MODULES  : %s", modules)
    logger.info(DASH)


def log_queue(queue: list):
    """Log the planned queue of steps produced by the planner."""
    logger.info("QUEUE    : %d steps planned", len(queue))
    for step in queue:
        args = step.get("args", {})
        # Format args as key=value pairs (exclude step index from display)
        args_str = " | ".join(f"{k}={v}" for k, v in args.items()) if args else ""
        logger.info(
            "  [%d] %-24s %s",
            step["step"],
            step["tool"],
            args_str,
        )
    logger.info(DASH)


def log_step(step_idx: int, tool_name: str, result: dict):
    """
    Log one step's execution result in a single readable line.

    Extracts the most meaningful value from each tool's output:
      count_records          → count=N
      sum_values             → total_sum=N  (M records)
      get_average            → average=N    (M records)
      get_minimum            → minimum=N
      get_maximum            → maximum=N
      calculate_time_between → avg=N min
      group_by_and_count     → total=N  groups=M
      get_unique_values      → count=N unique values
      join_records           → matched=N
      do_math                → result=N
      final_answer_tool      → <final_value>
    """
    if tool_name == "final_answer_tool":
        summary = str(result.get("final_value", result))

    elif "count" in result and "groups" not in result and "stats" not in result:
        summary = f"count={result['count']}"

    elif "total_sum" in result:
        summary = f"total_sum={result['total_sum']}  ({result.get('records_used')} records)"

    elif "average" in result and "stats" not in result:
        summary = f"average={result['average']}  ({result.get('records_used')} records)"

    elif "percentile_values" in result:
        pct = result.get("percentile_values", {})
        p50 = pct.get("p50", "N/A")
        summary = (
            f"p50={p50}  mean={result.get('mean')}  "
            f"std={result.get('std_dev')}  "
            f"records={result.get('records_used')}"
        )

    elif "groups" in result:
        summary = (
            f"total={result.get('total_records')}  "
            f"groups={result.get('unique_groups')}"
        )

    elif "unique_values" in result:
        summary = f"{result.get('count')} unique values"

    elif "matched_count" in result:
        summary = (
            f"matched={result['matched_count']}  "
            f"unmatched_a={result.get('unmatched_in_a')}  "
            f"unmatched_b={result.get('unmatched_in_b')}"
        )

    elif "sorted_data" in result:
        summary = (
            f"{result.get('total_out')}/{result.get('total_in')} items  "
            f"sort_by={result.get('sort_by')}  order={result.get('order')}"
        )

    elif "agg_field" in result and "groups" in result:
        summary = (
            f"op={result.get('operation')}  "
            f"total={result.get('total_records')}  "
            f"groups={result.get('unique_groups')}"
        )

    elif "condition_field_1" in result:
        summary = f"count={result['count']}"

    elif "result" in result:
        summary = f"result={result['result']}"

    elif "_dep_failed" in result:
        summary = f"DEPENDENCY_FAILED: {result['_dep_failed']}"

    elif "error" in result:
        summary = f"ERROR: {result['error']}"

    else:
        summary = str(result)

    logger.info("  STEP %-2d  %-22s → %s", step_idx, tool_name, summary)


def log_completion(
    status:       str,
    tools_called: int,
    queue_total:  int,
    error_count:  int,
    final_value,
    latency:      dict = None,
):
    """
    Log the final status and answer after all steps complete.

    status values:
      COMPLETE — all steps ran, zero errors
      PARTIAL  — all steps ran, ≥1 intermediate step errored
      FAILED   — final_answer_tool itself errored
    """
    logger.info(DASH)
    if error_count > 0:
        logger.info(
            "STATUS   : %s  (%d/%d steps, %d error(s))",
            status, tools_called, queue_total, error_count,
        )
    else:
        logger.info(
            "STATUS   : %s  (%d/%d steps)",
            status, tools_called, queue_total,
        )
    logger.info("ANSWER   : %s", final_value)
    
    if latency:
        logger.info(
            "LATENCY  : Total: %.2fs | LLM Plan: %.2fs | Tool Exec: %.2fs", 
            latency.get("total_time", 0),
            latency.get("llm_time", 0),
            latency.get("execution_time", 0)
        )
    
    logger.info("")
