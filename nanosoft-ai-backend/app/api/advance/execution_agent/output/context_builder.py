"""
Context Builder — formats the Execution Agent's raw output into a clean context
for the Formatting Agent.

Format determines what the Formatting Agent receives:

  TABLE / GRAPH   — steps + shape_descriptor + alternatives only.
                    No final_answer. Frontend renders the data.
                    LLM writes the analytical context above the rendered data.

  PLAIN_TEXT /    — steps + shape_descriptor + alternatives + final_answer.
  BULLET_LIST /     LLM reasons over the result to produce the full response.
  NUMBERED_LIST

Dashboard composition:
  Regardless of format, the DashboardComposer is called to produce a typed
  component list (kpi / bar_chart / time_series_chart / table / text) from
  the final_answer.  This list is included in the context as `dashboard` and
  flows through to the frontend without touching the LLM.
"""
import logging

from app.api.advance.execution_agent.output.shape_resolver    import resolve as resolve_shape
from app.api.advance.execution_agent.output.dashboard_composer import compose as compose_dashboard

logger = logging.getLogger("advance.context_builder")

_DATA_HEAVY_FORMATS = {"TABLE", "GRAPH"}


def build_formatting_context(
    execution_result: dict,
    suggested_format: str  = "PLAIN_TEXT",
    user_specified:   bool = False,
) -> dict:
    """
    Build the context passed to the Formatting Agent.

    Args:
        execution_result: Raw output from run_execution().
        suggested_format: Format hint from the Understanding Agent.
                          Default is PLAIN_TEXT — the safest fallback when
                          no format is specified by the caller.
        user_specified:   True if the user explicitly stated this format
                          in their query (e.g. "show me a graph").

    Returns a dict with:
        planned_steps, response_format, shape_descriptor, alternatives,
        final_answer (always included — service layer needs it for all formats),
        and dashboard (typed component list produced by DashboardComposer).
    """
    queue        = execution_result.get("queue", [])
    step_results = execution_result.get("step_results", {})

    # Pull final computed answer from the last step.
    # Use the actual step index from the queue — not len(queue)-1 —
    # because the LLM may number steps from 1 or use non-sequential indices.
    last_step_key = f"step_{queue[-1]['step']}" if queue else None
    final_output  = step_results.get(last_step_key, {}) if last_step_key else {}
    final_answer  = final_output.get("final_value", final_output)

    # Resolve the best presentation format based on the actual result structure.
    # shape_resolver applies Rule 8: if user_specified=True and the result is
    # compatible with suggested_format, the user's choice is honoured.
    shape_result    = resolve_shape(
        final_answer,
        suggested_format = suggested_format,
        user_specified   = user_specified,
    )
    resolved_format = shape_result["resolved_format"]

    # Strip intermediate outputs — only keep the plan itself
    planned_steps = [
        {
            "step": step["step"],
            "tool": step["tool"],
            "args": step.get("args", {}),
        }
        for step in queue
    ]

    # Compose the dynamic dashboard from the final_answer.
    # Pure Python, no LLM, no hardcoded field names.
    # The dashboard is always built — the frontend decides whether to use it.
    try:
        dashboard = compose_dashboard(
            final_answer     = final_answer,
            shape_descriptor = shape_result["shape_descriptor"],
            resolved_format  = resolved_format,
        )
    except Exception as exc:
        logger.warning("[ContextBuilder] DashboardComposer failed: %s", exc)
        dashboard = []

    context = {
        "planned_steps":     planned_steps,
        "response_format":   resolved_format,
        "shape_descriptor":  shape_result["shape_descriptor"],
        # Always include final_answer so service.py can patch it back.
        # The Formatting Agent LLM only receives it for non-data-heavy formats
        # (see Formatting_agent/agent.py) — but we store it here regardless.
        "final_answer":      final_answer,
        # Typed presentation component list — independent of layout/format.
        "dashboard":         dashboard,
    }

    return context