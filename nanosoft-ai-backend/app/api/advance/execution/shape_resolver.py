"""
Shape Resolver

Inspects the structure of the execution result ONLY — no actual values.
Determines:
  1. resolved_format  — the best display format for the data shape
  2. alternatives     — other valid formats for the same shape
  3. shape_descriptor — structural metadata (no actual values) sent to Formatting Agent

No LLM involved. No raw data values ever read.
"""


# ---------------------------------------------------------------------------
# Format alternatives per shape type
# ---------------------------------------------------------------------------
_SHAPE_ALTERNATIVES: dict[str, list[str]] = {
    "single_number":    [],
    "statistics":       [],
    "value_list_small": ["NUMBERED_LIST"],
    "value_list_large": ["GRAPH"],
    "grouped_few":      ["TABLE"],
    "grouped_many":     ["GRAPH"],
    "record_set":       [],
    "multi_result":     ["GRAPH"],
}


# ---------------------------------------------------------------------------
# Internal — detect shape from final_value structure
# ---------------------------------------------------------------------------
def _detect(final_value) -> tuple[str, dict]:
    """
    Returns (shape_type, descriptor).
    Inspects structure only — never reads the actual values inside lists/dicts.
    """

    # ── Multiple results (list of results from different steps) ──────────────
    if isinstance(final_value, list):
        item_count = len(final_value)
        # Peek at first item type only
        first_shape = "unknown"
        if item_count > 0 and isinstance(final_value[0], dict):
            first_shape, _ = _detect(final_value[0])
        return "multi_result", {
            "type":        "multi_result",
            "result_count": item_count,
            "item_type":   first_shape,
        }

    if not isinstance(final_value, dict):
        return "single_number", {"type": "single_number"}

    # ── Grouped data (group_by_and_count / group_by_and_aggregate) ───────────
    if "groups" in final_value:
        groups     = final_value["groups"]
        group_count = len(groups) if isinstance(groups, list) else 0
        fields      = list(groups[0].keys()) if group_count > 0 and isinstance(groups[0], dict) else []
        shape_type  = "grouped_few" if group_count <= 6 else "grouped_many"
        return shape_type, {
            "type":          "grouped_data",
            "group_count":   group_count,
            "fields":        fields,
            "total_records": final_value.get("total_records", 0),
        }

    # ── Record set (get_record_fields) ───────────────────────────────────────
    if "records" in final_value:
        record_count    = final_value.get("total", 0)
        fields_returned = final_value.get("fields_returned", [])
        return "record_set", {
            "type":         "record_set",
            "record_count": record_count,
            "field_count":  len(fields_returned),
            "fields":       fields_returned,
        }

    # ── Unique values list (get_unique_values) ───────────────────────────────
    if "unique_values" in final_value:
        item_count = final_value.get("count", 0)
        shape_type = "value_list_small" if item_count <= 10 else "value_list_large"
        return shape_type, {
            "type":       "value_list",
            "item_count": item_count,
        }

    # ── Statistics (calculate_time_between) ──────────────────────────────────
    if "stats" in final_value:
        stat_keys = list(final_value["stats"].keys()) if isinstance(final_value.get("stats"), dict) else []
        return "statistics", {
            "type":      "statistics",
            "stat_keys": stat_keys,
        }

    # ── Sorted list (sort_and_limit) ─────────────────────────────────────────
    if "sorted_data" in final_value:
        total_out = final_value.get("total_out", 0)
        shape_type = "grouped_few" if total_out <= 6 else "grouped_many"
        return shape_type, {
            "type":        "ranked_list",
            "item_count":  total_out,
            "total_in":    final_value.get("total_in", 0),
        }

    # ── Single computed number (count, result, total_sum, average, etc.) ─────
    scalar_keys = {"count", "result", "total_sum", "average", "minimum",
                   "maximum", "matched_count"}
    if scalar_keys & set(final_value.keys()):
        return "single_number", {"type": "single_number"}

    # ── Fallback ─────────────────────────────────────────────────────────────
    return "single_number", {"type": "unknown"}


# ---------------------------------------------------------------------------
# Format resolution per shape type
# ---------------------------------------------------------------------------
def _shape_to_format(shape_type: str, suggested_format: str) -> str:
    """Map shape → best format. Override Understanding Agent hint if mismatched."""
    mapping = {
        "single_number":    "PLAIN_TEXT",
        "statistics":       "PLAIN_TEXT",
        "value_list_small": "BULLET_LIST",
        "value_list_large": "TABLE",
        "grouped_few":      "GRAPH",
        "grouped_many":     "TABLE",
        "record_set":       "TABLE",
        "multi_result":     "TABLE",
    }
    resolved = mapping.get(shape_type, suggested_format)

    # If Understanding Agent suggested GRAPH and shape supports it, honour it
    if suggested_format == "GRAPH" and shape_type in ("grouped_few", "grouped_many", "multi_result"):
        return "GRAPH"
    # If Understanding Agent suggested TABLE and shape supports it, honour it
    if suggested_format == "TABLE" and shape_type in (
        "grouped_few", "grouped_many", "record_set", "multi_result", "value_list_large"
    ):
        return "TABLE"

    return resolved


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Formats compatible with each shape type
# ---------------------------------------------------------------------------
_SHAPE_COMPATIBLE_FORMATS: dict[str, set[str]] = {
    "single_number":    {"PLAIN_TEXT"},
    "statistics":       {"PLAIN_TEXT"},
    "value_list_small": {"BULLET_LIST", "NUMBERED_LIST", "TABLE", "PLAIN_TEXT"},
    "value_list_large": {"TABLE", "GRAPH", "PLAIN_TEXT"},
    "grouped_few":      {"GRAPH", "TABLE", "PLAIN_TEXT"},
    "grouped_many":     {"TABLE", "GRAPH", "PLAIN_TEXT"},
    "record_set":       {"TABLE", "PLAIN_TEXT"},
    "multi_result":     {"TABLE", "GRAPH", "PLAIN_TEXT"},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def resolve(
    final_value,
    suggested_format:   str  = "PLAIN_TEXT",
    user_specified:     bool = False,
) -> dict:
    """
    Inspect the final_value structure and return:
        {
            "resolved_format":  str,    # actual best format
            "alternatives":     [str],  # other valid formats
            "shape_descriptor": dict,   # structural metadata only
            "overridden":       bool,   # True if suggested_format was changed
        }

    user_specified=True  → honour suggested_format IF data can support it.
                           Only override if data fundamentally cannot support it.
    user_specified=False → freely override based on data shape.

    No actual data values are ever read or returned.
    """
    shape_type, descriptor = _detect(final_value)
    compatible             = _SHAPE_COMPATIBLE_FORMATS.get(shape_type, {"PLAIN_TEXT"})
    suggested_upper        = suggested_format.upper()

    if user_specified and suggested_upper in compatible:
        # User explicitly asked for this format and data supports it — honour it
        resolved_format = suggested_upper
    else:
        # Agent guessed, or user's choice is incompatible with data — use best fit
        resolved_format = _shape_to_format(shape_type, suggested_upper)

    # Alternatives = other compatible formats minus the resolved one
    alternatives = [f for f in _SHAPE_ALTERNATIVES.get(shape_type, []) if f != resolved_format]

    return {
        "resolved_format":  resolved_format,
        "alternatives":     alternatives,
        "shape_descriptor": descriptor,
        "overridden":       resolved_format != suggested_upper,
    }
