from __future__ import annotations
import logging
import re
from typing import Any
from app.services.payload_constants import *
from app.services.payload_helpers import *

logger = logging.getLogger('tool_payload_validator')

def normalize_tool_args(tool_name: str, user_query: str, args: dict[str, Any]) -> dict[str, Any]:
    """
    Return a copy of tool args normalized for DB routes.
    """
    out = _normalize_smart_punctuation(dict(args or {}))
    tool = (tool_name or "").upper()
    query = _normalize_smart_punctuation(user_query or "")

    # Normalize frequency value (e.g., ANNUALLY -> ANNUAL) to match database values
    freq = out.get("frequency")
    if freq and isinstance(freq, str):
        freq_upper = freq.upper().strip()
        if freq_upper in ("ANNUALLY", "ANNUAL"):
            out["frequency"] = "ANNUAL"
        elif freq_upper in ("MONTHLY", "MONTH"):
            out["frequency"] = "MONTHLY"
        elif freq_upper in ("QUARTERLY", "QUARTER"):
            out["frequency"] = "QUARTERLY"
        elif freq_upper in ("WEEKLY", "WEEK"):
            out["frequency"] = "WEEKLY"
        elif freq_upper in ("DAILY", "DAY"):
            out["frequency"] = "DAILY"

    # Coerce aggregate flag
    if "is_aggregate" in out:
        out["is_aggregate"] = _coerce_bool(out["is_aggregate"])

    # Normalize group_by_columns to list of canonical names
    gbc = out.get("group_by_columns")
    if gbc is not None:
        if isinstance(gbc, str):
            gbc = [gbc]
        elif not isinstance(gbc, list):
            gbc = [str(gbc)]
        normalized_cols: list[str] = []
        for item in gbc:
            col = _normalize_group_by_value(str(item), tool)
            if col and col not in normalized_cols:
                normalized_cols.append(col)
        out["group_by_columns"] = normalized_cols or None

    _fix_dimension_count_aggregate(tool, query, out)
    _fix_bogus_dimension_location_filters(tool, query, out)
    _fix_mistaken_group_by_on_simple_count(tool, query, out)
    # Disabled by user request: _fix_division_to_building_for_location_count was too aggressive
    # _fix_division_to_building_for_location_count(tool, query, out)

    wants_aggregate = _query_implies_aggregate(query, tool)
    has_group_by = bool(out.get("group_by_columns"))

    if wants_aggregate or has_group_by:
        out["is_aggregate"] = True

    if out.get("is_aggregate") and not out.get("group_by_columns"):
        inferred = _infer_group_by_from_query(query, tool)
        if inferred:
            out["group_by_columns"] = inferred
            logger.info("🔧 Inferred group_by_columns=%s from query", inferred)
        else:
            # Fall back to standard query mode since no group_by columns are defined or could be inferred
            logger.info("🔧 No group_by columns provided or inferred; resetting is_aggregate to False")
            out["is_aggregate"] = False

    if out.get("group_by_columns") and not out.get("is_aggregate"):
        out["is_aggregate"] = True

    # Aggregate without group_by is invalid (HTTP 400). Use normal sp_*_query + p_count.
    if out.get("is_aggregate") and not out.get("group_by_columns"):
        out["is_aggregate"] = False
        out.pop("aggregate_function", None)
        logger.info(
            "🔧 Disabled invalid aggregate for %s (no group_by_columns) — normal count/list query",
            tool,
        )

    # "low count" ≠ priority filter
    _strip_priority_for_low_count(query, out)

    _fix_service_type_vs_division(tool, query, out)
    _fix_bogus_division(tool, query, out)
    _fix_bdm_complaint_type_header_stage(tool, query, out)
    _fix_fa_building_name_vs_audit_category(tool, query, out)
    _fix_fa_closed_open_stage(tool, query, out)
    _fix_ppm_stages_from_query(tool, query, out)
    _fix_ppm_technician_assigned_tech(tool, query, out)
    _strip_implicit_status_for_conversational_verbs(tool, query, out)
    _normalize_location_fields(out)
    _fix_hyphen_spacing_from_query(query, out)
    _fix_redundant_keyword_with_structured_filters(tool, out)

    if _RE_PRIORITY_INTENT.search(query) and out.get("priority") is None:
        m = re.search(r"\bp([1-4])\b", query, re.I)
        if m:
            level = int(m.group(1))
            mapping = {1: "P1 Critical", 2: "P2 High", 3: "P3 Medium", 4: "P4 Low"}
            out["priority"] = mapping.get(level)
    if out.get("priority") is not None:
        out["priority"] = _normalize_priority_value(out["priority"])
        # ── P-prefix recovery ──────────────────────────────────────────────────
        # The model sometimes strips the P-number prefix when the user said
        # e.g. "P3 medium priority" and the model sends priority="Medium".
        # Rule:
        #   - If query has a P-number AND model sent a short form → upgrade to full form.
        #   - If query has NO P-number → leave the short form as-is (DB accepts both).
        # The P-number in the query is the canonical truth because the user said it.
        _P_TO_FULL = {1: "P1 Critical", 2: "P2 High", 3: "P3 Medium", 4: "P4 Low"}
        _SHORT_NAMES = {"low", "medium", "high", "critical"}
        _p_match = re.search(r"\bp([1-4])\b", query, re.I)
        if _p_match and out.get("priority", "").lower() in _SHORT_NAMES:
            _level = int(_p_match.group(1))
            _full  = _P_TO_FULL[_level]
            logger.info(
                "🔧 Priority P-prefix restored: '%s' → '%s' (query mentioned P%s)",
                out["priority"], _full, _level,
            )
            out["priority"] = _full

    # Group-by building: drop mistaken `building` filter when user asked per-building counts
    if (
        out.get("is_aggregate")
        and out.get("group_by_columns") == ["BuildingName"]
        and _RE_BUILDING_GROUP.search(query)
        and not re.search(r"\bbuilding\s+(?:is|named|=)\s+", query, re.I)
    ):
        if out.pop("building", None) is not None:
            logger.info("🔧 Cleared building filter (aggregate by BuildingName)")

    if out.get("is_aggregate"):
        strip = AGGREGATE_STRIP_FIELDS.get(tool, frozenset())
        for key in list(out.keys()):
            if key in strip and out[key] is not None:
                logger.info("🔧 Aggregate mode: stripped %s (not used by aggregate SP)", key)
                out.pop(key, None)
        if not out.get("aggregate_function"):
            out["aggregate_function"] = "COUNT"

    if out.get("is_aggregate"):
        logger.info(
            "🔧 Normalized %s payload | is_aggregate=%s | group_by=%s | priority=%s",
            tool,
            out.get("is_aggregate"),
            out.get("group_by_columns"),
            out.get("priority"),
        )

    return out


def validate_aggregate_request(is_aggregate: bool, group_by_columns: list | None) -> None:
    """
    Route-level guard before calling sp_*_aggregate.
    Raises ValueError with a clear message if invalid.
    """
    if not is_aggregate:
        return
    if not group_by_columns:
        raise ValueError(
            "group_by_columns is required when is_aggregate is true. "
            "Example: group_by_columns=['BuildingName']"
        )
