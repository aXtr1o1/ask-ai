"""
Context Builder — formats the Execution Agent's raw output into a clean context
for the Formatting Agent.

The context always carries planned_steps, shape_descriptor, final_answer, and
dashboard, regardless of format. Format determines what the Formatting Agent's
LLM prompt actually includes (see Formatting_agent/agent.py's is_data_heavy
check) — TABLE/GRAPH prompts omit final_answer's raw values from the LLM
message; PLAIN_TEXT/BULLET_LIST/NUMBERED_LIST include them. final_answer and
dashboard themselves are always present in this context so the frontend can
render either way.

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

    # A step's data-quality caveat (tool_helpers._sparsity_note) lives on that
    # step's OWN result dict — but final_answer_tool's result_ref commonly
    # references a specific key inside it (e.g. "$step_0.groups"), so the note
    # sitting alongside that key doesn't travel with the extracted value.
    # shape_resolver only sees final_answer and can't recover it. Scan every
    # step's raw result here (context_builder has step_results in scope) and
    # fold any caveats into the reason the Formatting Agent reads — this is the
    # one channel guaranteed to reach it for every presentation format.
    quality_notes = [
        result["_data_quality_note"]
        for result in step_results.values()
        if isinstance(result, dict) and result.get("_data_quality_note")
    ]
    if quality_notes:
        combined_notes = " ".join(dict.fromkeys(quality_notes))  # de-dupe, keep order
        shape_result["shape_descriptor"]["reason"] = (
            f"{shape_result['shape_descriptor']['reason']} Data quality caveat: {combined_notes}"
        )

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