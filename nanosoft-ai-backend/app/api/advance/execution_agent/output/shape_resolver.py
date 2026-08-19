"""
Shape Resolver — pure Python format decision for execution results.

No LLM call. No hardcoded field names. No arbitrary size thresholds.

Analyzes the actual STRUCTURE and VALUE TYPES of final_value dynamically:

  PLAIN_TEXT — scalar, or a dict whose values are all scalars (summary)
  GRAPH      — list of consistent dicts where each item has at least one
               string value (category/label) AND at least one numeric value
               (metric) — detected from actual values, not field names
  TABLE      — list of consistent dicts that do not fit the GRAPH pattern

A list or dict is never automatically treated as TABLE or GRAPH.
If the user explicitly requests a compatible format, that request is respected.

Public API:
  resolve(final_value, suggested_format, user_specified) → dict
"""
import logging

logger = logging.getLogger("advance.execution")


# =============================================================================
# HELPERS — purely value-type based, no field name knowledge
# =============================================================================

def _is_numeric(v) -> bool:
    """True if v is a real number (int or float, excluding bool)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _all_dicts(lst: list) -> bool:
    """True if lst is non-empty and every element is a dict."""
    return bool(lst) and all(isinstance(item, dict) for item in lst)


def _item_has_category(item: dict) -> bool:
    """True if the dict contains at least one string value.

    A string value indicates a label, group name, or category dimension —
    the dimension you would place on a chart axis or legend.
    Detection is value-type based, not field-name based.
    """
    return any(isinstance(v, str) for v in item.values())


def _item_has_metric(item: dict) -> bool:
    """True if the dict contains at least one numeric (int/float) value.

    A numeric value is the metric you would measure — count, sum, average,
    rate, percentage, score, etc. — regardless of what the field is named.
    Detection is value-type based, not field-name based.
    """
    return any(_is_numeric(v) for v in item.values())


def _qualifies_for_graph(items: list) -> bool:
    """True if items represent groupable data suitable for a graph.

    Checks the first item as a representative sample:
      - has a string value  (the category/group axis)
      - has a numeric value (the metric axis)
    No field name knowledge or size thresholds applied.
    """
    if not _all_dicts(items):
        return False
    sample = items[0]
    return _item_has_category(sample) and _item_has_metric(sample)


def _find_embedded_list(d: dict) -> list | None:
    """Return the first non-empty list of dicts found inside a dict,
    falling back to the first non-empty list of any type.
    """
    for v in d.values():
        if isinstance(v, list) and _all_dicts(v):
            return v
    for v in d.values():
        if isinstance(v, list) and v:
            return v
    return None


# =============================================================================
# MAIN ANALYSIS
# =============================================================================

def _analyze(final_value) -> tuple[str, str, str]:
    """Return (shape, reason, best_format) by inspecting actual value types.

    No field names hardcoded. No arbitrary thresholds.
    """

    # ── None or error dict ────────────────────────────────────────────────────
    if final_value is None:
        return "error", "Result is None — execution may have failed.", "PLAIN_TEXT"

    if isinstance(final_value, dict) and ("error" in final_value or "_dep_failed" in final_value):
        return "error", "Execution step failed.", "PLAIN_TEXT"

    # ── Scalar (int, float, str, bool) → PLAIN_TEXT ───────────────────────────
    if not isinstance(final_value, (dict, list)):
        return "single_number", "Single scalar value.", "PLAIN_TEXT"

    # ── List ──────────────────────────────────────────────────────────────────
    if isinstance(final_value, list):

        if not final_value:
            return "empty_list", "Empty list result.", "PLAIN_TEXT"

        # List contains no dicts — just scalars (IDs, names, values)
        if not any(isinstance(item, dict) for item in final_value):
            return (
                "value_list",
                "List of scalar values — no table or graph needed.",
                "PLAIN_TEXT",
            )

        # List of dicts — inspect actual value types
        # NOTE: GRAPH auto-detection is disabled. Even if data looks graph-compatible
        # (has a string category + numeric metric), we resolve to TABLE so the
        # frontend can render it reliably. Users can still request a graph explicitly.
        if _all_dicts(final_value):
            if _qualifies_for_graph(final_value):
                return (
                    "grouped_numeric_data",
                    "Each record has a string category and a numeric metric — table for individual inspection.",
                    "TABLE",  # GRAPH auto-detection disabled — always use TABLE
                )
            return (
                "record_set",
                "Records with no clear numeric metric — table for individual inspection.",
                "TABLE",
            )

        # Mixed list (some dicts, some scalars)
        return "mixed_list", "Mixed list of records and scalars — table for structured view.", "TABLE"

    # ── Dict ──────────────────────────────────────────────────────────────────
    # Look for an embedded list of dicts (e.g. {"groups": [...], "total": 100})
    embedded = _find_embedded_list(final_value)

    if embedded is not None and _all_dicts(embedded):
        if _qualifies_for_graph(embedded):
            return (
                "grouped_numeric_data",
                "Wraps a list where each record has a category and a numeric value — table for individual inspection.",
                "TABLE",  # GRAPH auto-detection disabled — always use TABLE
            )
        return (
            "record_set",
            "Wraps a list of records — table for individual inspection.",
            "TABLE",
        )

    # Dict with only scalar values → simple summary → PLAIN_TEXT
    non_private = {k: v for k, v in final_value.items() if not k.startswith("_")}
    if all(not isinstance(v, (dict, list)) for v in non_private.values()):
        return (
            "summary_metrics",
            "All values are scalars — simple summary, no table or graph needed.",
            "PLAIN_TEXT",
        )

    # Dict with nested structure but no groupable list → PLAIN_TEXT
    return (
        "summary_metrics",
        "Structured result without groupable data — plain text summary.",
        "PLAIN_TEXT",
    )


# =============================================================================
# COMPATIBLE FORMATS PER SHAPE
# =============================================================================
_COMPATIBLE: dict[str, set[str]] = {
    "single_number":        {"PLAIN_TEXT"},
    "summary_metrics":      {"PLAIN_TEXT"},
    "value_list":           {"PLAIN_TEXT", "BULLET_LIST", "NUMBERED_LIST"},
    "grouped_numeric_data": {"GRAPH", "TABLE", "PLAIN_TEXT"},
    "record_set":           {"TABLE", "PLAIN_TEXT"},
    "mixed_list":           {"TABLE", "PLAIN_TEXT"},
    "error":                {"PLAIN_TEXT"},
    "empty_list":           {"PLAIN_TEXT"},
}


# =============================================================================
# PUBLIC API
# =============================================================================

def resolve(
    final_value,
    suggested_format: str  = "PLAIN_TEXT",
    user_specified:   bool = False,
) -> dict:
    """Determine the best presentation format by inspecting final_value's structure.

    No LLM. No hardcoded field names. No size thresholds.
    Decision is based entirely on the actual value types inside the result.

    Args:
        final_value:      Final computed answer from the Execution Agent.
        suggested_format: Format hint from the Understanding Agent.
        user_specified:   True if the user explicitly named a format in their query.

    Returns:
        {
            "resolved_format":  str,   # PLAIN_TEXT | TABLE | GRAPH
            "shape_descriptor": dict,  # {"shape": ..., "reason": ...}
        }
    """
    shape, reason, best_format = _analyze(final_value)
    suggested_upper = suggested_format.upper()
    compatible      = _COMPATIBLE.get(shape, {"PLAIN_TEXT"})

    # Honour user's explicit format request if the data is compatible with it
    if user_specified and suggested_upper in compatible:
        resolved_format = suggested_upper
    else:
        resolved_format = best_format

    logger.info(
        "[Shape Resolver] format=%s | shape=%s | reason=%s",
        resolved_format, shape, reason,
    )

    return {
        "resolved_format":  resolved_format,
        "shape_descriptor": {"shape": shape, "reason": reason},
    }