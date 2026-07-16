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
  STATUS   : COMPLETE  (3/3 steps)
  ANSWER   : 0.48
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

    elif "minimum" in result and "stats" not in result:
        summary = f"minimum={result['minimum']}"

    elif "maximum" in result and "stats" not in result:
        summary = f"maximum={result['maximum']}"

    elif "stats" in result:
        s = result["stats"]
        summary = (
            f"avg={s.get('average')} min  "
            f"min={s.get('minimum')}  "
            f"max={s.get('maximum')}  "
            f"({result.get('calculated')} records)"
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

    elif "result" in result:
        summary = f"result={result['result']}"

    elif "error" in result:
        summary = f"ERROR: {result['error']}"

    else:
        summary = str(result)

    logger.info("  STEP %-2d  %-22s → %s", step_idx, tool_name, summary)


def log_completion(status: str, tools_called: int, queue_total: int, final_value):
    """Log the final status and answer after all steps complete."""
    logger.info(DASH)
    logger.info("STATUS   : %s  (%d/%d steps)", status, tools_called, queue_total)
    logger.info("ANSWER   : %s", final_value)
    logger.info("")