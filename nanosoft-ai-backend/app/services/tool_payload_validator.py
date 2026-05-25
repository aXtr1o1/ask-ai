"""
Normalize and validate LangChain tool args before they reach facility_tools / DB routes.

The LLM often sends inconsistent payloads (is_aggregate without group_by, wrong priority
on "low count", filter field `building` instead of group_by BuildingName). This module
corrects those cases from the user query + tool name.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("tool_payload_validator")

# Canonical group-by columns allowed per tool (must match DB / stored procedures)
TOOL_GROUP_BY_COLUMNS: dict[str, frozenset[str]] = {
    "ASSETS": frozenset({
        "DivisionName", "DisciplineName", "BuildingName", "FloorName", "LocalityName",
        "StatusName", "ConditionName", "PriorityName", "AssetTypeName", "EquipmentName",
        "MakeName", "ModelName", "SpotName", "TradeGroupName", "ServiceAreaName",
        "OnHold", "IsSnagged", "IsScraped", "IsEnablePPM", "IsEnableBDM",
    }),
    "PPM": frozenset({
        "DivisionName", "DisciplineName", "BuildingName", "FloorName", "LocalityName",
        "FrequencyName", "PPMStatus", "PPMStageName", "ContractName", "SpotName",
    }),
    "BDM": frozenset({
        "DivisionName", "DisciplineName", "BuildingName", "FloorName", "LocalityName",
        "WoStatus", "PriorityName", "StageName", "ComplaintTypeName", "ComplaintModeName",
        "SpotName", "ContractName",
    }),
    "FA": frozenset({
        "DivisionName", "BuildingName", "FloorName", "LocalityName", "PriorityName",
        "RMStageName", "RMCategoryName", "RMCategorySubName", "FrequencyName",
        "ContractName", "SpotName", "IsRMWithdraw", "IsRMRework", "IsActive",
    }),
    "SB": frozenset({
        "DivisionName", "DisciplineName", "BuildingName", "FloorName", "LocalityName",
        "PPMStageName", "FrequencyName", "ServiceTypeName", "ContractName", "SpotName",
    }),
}

# English / alias → canonical DB column for group_by_columns
GROUP_BY_ALIASES: dict[str, str] = {
    "division": "DivisionName",
    "divisionname": "DivisionName",
    "discipline": "DisciplineName",
    "disciplinename": "DisciplineName",
    "building": "BuildingName",
    "buildingname": "BuildingName",
    "floor": "FloorName",
    "floorname": "FloorName",
    "locality": "LocalityName",
    "localityname": "LocalityName",
    "status": "StatusName",
    "statusname": "StatusName",
    "wostatus": "WoStatus",
    "condition": "ConditionName",
    "conditionname": "ConditionName",
    "priority": "PriorityName",
    "priorityname": "PriorityName",
    "stage": "StageName",
    "stagename": "StageName",
    "rmstage": "RMStageName",
    "rmstagename": "RMStageName",
    "complainttype": "ComplaintTypeName",
    "complainttypename": "ComplaintTypeName",
    "complaintmode": "ComplaintModeName",
    "complaintmodename": "ComplaintModeName",
    "frequency": "FrequencyName",
    "frequencyname": "FrequencyName",
    "ppmstatus": "PPMStatus",
    "ppmstagename": "PPMStageName",
    "contract": "ContractName",
    "contractname": "ContractName",
    "spot": "SpotName",
    "spotname": "SpotName",
    "assettype": "AssetTypeName",
    "equipment": "EquipmentName",
    "make": "MakeName",
    "model": "ModelName",
    "servicetype": "ServiceTypeName",
    "category": "RMCategoryName",
    "rmcategory": "RMCategoryName",
    "rmcategoryname": "RMCategoryName",
    "onhold": "OnHold",
    "issnagged": "IsSnagged",
    "isscraped": "IsScraped",
    "isenableppm": "IsEnablePPM",
    "isenablebdm": "IsEnableBDM",
}

# Query phrase fragment → group_by column (when inferring from user text)
_QUERY_GROUP_BY_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bbuilding\s*name\b", re.I), "BuildingName"),
    (re.compile(r"\b(?:per|by|each)\s+building\b", re.I), "BuildingName"),
    (re.compile(r"\b(?:per|by|each)\s+division\b", re.I), "DivisionName"),
    (re.compile(r"\b(?:per|by|each)\s+floor\b", re.I), "FloorName"),
    (re.compile(r"\b(?:per|by|each)\s+priority\b", re.I), "PriorityName"),
    (re.compile(r"\b(?:per|by|each)\s+stage\b", re.I), "StageName"),
    (re.compile(r"\b(?:per|by|each)\s+frequency\b", re.I), "FrequencyName"),
]

# Fields ignored by aggregate stored procedures — strip so payload matches DB contract
AGGREGATE_STRIP_FIELDS: dict[str, frozenset[str]] = {
    "ASSETS": frozenset({
        "asset_tag_no", "asset_barcode", "equipment_name", "equipment_ref_no", "serial_no",
        "asset_type", "owner", "make", "model", "service_area", "trade_group", "drawing_no",
        "remarks", "on_hold", "is_snagged", "is_scraped", "enable_ppm", "enable_bdm",
        "enable_bms", "enable_dsm", "keyword", "limit",
    }),
    "PPM": frozenset({
        "work_order", "asset_tag_no", "equipment_ref_no", "equipment", "contract", "tech",
        "keyword", "comp_from", "comp_to", "sla_min", "sla_max", "limit",
    }),
    "BDM": frozenset({
        "complaint_no", "asset_tag_no", "asset_barcode", "client_wo_no", "complaint_type",
        "complaint_header", "complaint_mode", "complaint_nature", "wo_type", "service_type",
        "spot_name", "contract", "complainer", "register_by", "analysis_tech",
        "execution_tech", "keyword", "completed_from", "completed_to", "limit",
    }),
    "FA": frozenset({
        "complaint_no", "complaint_code", "x_complaint_no", "category_sub", "spot_name",
        "contract", "tech", "request_desc", "is_withdraw", "is_rework", "is_bms",
        "is_active", "is_draft", "keyword", "comp_from", "comp_to", "limit",
    }),
    "SB": frozenset({
        "work_order", "spot_name", "contract", "tech", "is_withdraw", "is_reschedule",
        "is_rework", "is_active", "is_draft", "keyword", "comp_from", "comp_to",
        "sla_min", "sla_max", "limit",
    }),
}

_RE_AGGREGATE_INTENT = re.compile(
    r"\b(?:how\s+many\s+.+\s+(?:per|by|each|wise)|breakdown|grouped\s+by|distribution|"
    r"count\s+by|counts?\s+per|per\s+\w+|by\s+\w+\s+wise|building\s*name)\b",
    re.I,
)
_RE_LOW_COUNT = re.compile(
    r"\b(?:low\s+count|lowest\s+count|fewest|minimum\s+count|smallest\s+count|"
    r"least\s+count|low\s+counts?)\b",
    re.I,
)
_RE_PRIORITY_INTENT = re.compile(
    r"\b(?:p[1-4]\s*(?:critical|high|medium|low)?|"
    r"(?:critical|high|medium)\s+priority|low\s+priority|urgency)\b",
    re.I,
)
_RE_BUILDING_GROUP = re.compile(
    r"\b(?:building\s*name|(?:per|by|each)\s+building)\b",
    re.I,
)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _normalize_group_by_value(raw: str, tool_name: str) -> str | None:
    if not raw or not isinstance(raw, str):
        return None
    key = re.sub(r"[\s_\-]+", "", raw.strip()).lower()
    if not key:
        return None
    canonical = GROUP_BY_ALIASES.get(key)
    if canonical and canonical in TOOL_GROUP_BY_COLUMNS.get(tool_name, ()):
        return canonical
    # Already PascalCase column?
    if raw in TOOL_GROUP_BY_COLUMNS.get(tool_name, ()):
        return raw
    # Try title-case match
    for col in TOOL_GROUP_BY_COLUMNS.get(tool_name, ()):
        if col.lower() == key:
            return col
    return None


def _infer_group_by_from_query(query: str, tool_name: str) -> list[str]:
    q = query or ""
    found: list[str] = []
    allow = TOOL_GROUP_BY_COLUMNS.get(tool_name, frozenset())

    if _RE_BUILDING_GROUP.search(q) and "BuildingName" in allow:
        found.append("BuildingName")

    for pattern, col in _QUERY_GROUP_BY_HINTS:
        if col and pattern.search(q) and col in allow and col not in found:
            found.append(col)

    if re.search(r"\b(?:per|by|each)\s+status\b", q, re.I):
        status_col = {
            "BDM": "WoStatus",
            "ASSETS": "StatusName",
            "PPM": "PPMStatus",
        }.get(tool)
        if status_col and status_col in allow and status_col not in found:
            found.append(status_col)

    # Literal column names in query (e.g. "BuildingName")
    for col in allow:
        if re.search(rf"\b{re.escape(col)}\b", q, re.I) and col not in found:
            found.append(col)

    return found


def _query_implies_aggregate(query: str) -> bool:
    q = query or ""
    if _RE_AGGREGATE_INTENT.search(q):
        return True
    if _RE_BUILDING_GROUP.search(q):
        return True
    if _RE_LOW_COUNT.search(q) and re.search(r"\bbuilding\b", q, re.I):
        return True
    return False


def _strip_priority_for_low_count(query: str, args: dict[str, Any]) -> None:
    if not _RE_LOW_COUNT.search(query or ""):
        return
    if _RE_PRIORITY_INTENT.search(query or ""):
        return
    if args.pop("priority", None) is not None:
        logger.info("🔧 Stripped priority (user meant low count, not P4 Low)")


def _normalize_priority_value(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = re.sub(r"[\-–—]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    low = s.lower()
    if low in ("p4", "p4 low", "low"):
        return "P4 Low"
    if low in ("p1", "p1 critical", "critical"):
        return "P1 Critical"
    if low in ("p2", "p2 high", "high"):
        return "P2 High"
    if low in ("p3", "p3 medium", "medium"):
        return "P3 Medium"
    return s


def normalize_tool_args(tool_name: str, user_query: str, args: dict[str, Any]) -> dict[str, Any]:
    """
    Return a copy of tool args normalized for DB routes.
    """
    out = dict(args or {})
    tool = (tool_name or "").upper()
    query = user_query or ""

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

    wants_aggregate = _query_implies_aggregate(query)
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

    # "low count" ≠ priority filter
    _strip_priority_for_low_count(query, out)

    if _RE_PRIORITY_INTENT.search(query) and out.get("priority") is None:
        m = re.search(r"\bp([1-4])\b", query, re.I)
        if m:
            level = int(m.group(1))
            mapping = {1: "P1 Critical", 2: "P2 High", 3: "P3 Medium", 4: "P4 Low"}
            out["priority"] = mapping.get(level)
    if out.get("priority") is not None:
        out["priority"] = _normalize_priority_value(out["priority"])

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
