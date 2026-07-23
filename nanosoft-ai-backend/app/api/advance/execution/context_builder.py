"""
Context Builder — formats the Execution Agent's raw output into a clean context for the Formatting Agent.
"""
from app.api.advance.execution.schemas import ExecutionResult

# Formats where the frontend renders the data directly —
# the LLM only needs to produce a contextual explanation, not reason over the rows.
_DATA_HEAVY_FORMATS = {"TABLE", "GRAPH"}


def build_formatting_context(
    execution_result: dict,
    response_format: str = "PLAIN_TEXT",
) -> dict:
    """
    Builds the context passed to the Formatting Agent.

    For data-heavy formats (TABLE, GRAPH):
        Returns only planned_steps. The final answer (raw data rows / grouped
        data) is excluded — the frontend renders it directly. The LLM only
        needs to write a contextual explanation of how the answer was derived.

    For lightweight formats (PLAIN_TEXT, BULLET_LIST, NUMBERED_LIST):
        Returns planned_steps + final_answer so the LLM can reason over the
        actual result and produce a high-quality, contextual natural language
        response.
    """
    queue        = execution_result.get("queue", [])
    step_results = execution_result.get("step_results", {})

    # Pull the final computed answer from the last step
    last_step_key = f"step_{len(queue) - 1}" if queue else None
    final_output  = step_results.get(last_step_key, {}) if last_step_key else {}
    final_answer  = final_output.get("final_value", final_output)

    # Strip intermediate outputs — only keep the plan itself
    planned_steps = [
        {
            "step": step["step"],
            "tool": step["tool"],
            "args": step.get("args", {}),
        }
        for step in queue
    ]

    context = {
        "planned_steps":   planned_steps,
        "response_format": response_format,
        "final_answer":    final_answer,   # always included — LLM reasons over actual data for ALL formats
    }

    return context
