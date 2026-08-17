"""
Execution — Data Shapes

StepDef       → one planned tool call in the queue
ExecutionResult → the final output after the queue finishes running
"""
from typing import Any, TypedDict


# =============================================================================
# STEP DEFINITION — one entry in the planned queue
#
# Fields:
#   step  → index (0, 1, 2, ...)
#   tool  → tool name (e.g. "count_records", "do_math", "final_answer_tool")
#   args  → tool arguments; values may be plain scalars or "$step_N.key" references
# =============================================================================
class StepDef(TypedDict):
    step: int
    tool: str
    args: dict[str, Any]


# =============================================================================
# EXECUTION RESULT — returned by run_queue() after all steps complete
#
# Fields:
#   queue        → the original planned queue (list of StepDef)
#   step_results → raw tool output per step  e.g. {"step_0": {...}, "step_1": {...}}
#   queue_total  → total steps that were planned
#   tools_called → total steps that were actually executed
#   error_count  → number of steps that produced an error or dependency failure
#   status       → "COMPLETE" | "PARTIAL" | "FAILED"
#   latency      → dict with "llm_time", "execution_time", "total_time" in seconds
# =============================================================================
class ExecutionResult(TypedDict):
    queue:        list[StepDef]
    step_results: dict[str, Any]
    queue_total:  int
    tools_called: int
    error_count:  int
    status:       str
    latency:      dict[str, float]

