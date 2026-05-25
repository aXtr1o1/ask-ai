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

# Unicode dash/minus variants → ASCII hyphen (DB locality/building names use " - ")
_UNICODE_DASHES = re.compile(r"[\u002d\u2010-\u2015\u2212\uFE58\uFE63\uFF0d]")
_LOCATION_TEXT_FIELDS = frozenset({"locality", "building", "floor", "spot_name"})

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
        "ServiceTypeName", "SpotName", "ContractName",
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
_RE_BREAKDOWN_INTENT = re.compile(
    r"\b(?:per|by|each|wise|breakdown|grouped\s+by|distribution|"
    r"count\s+by|counts?\s+per|by\s+\w+\s+wise)\b",
    re.I,
)
_RE_SIMPLE_HOW_MANY = re.compile(r"\bhow\s+many\b", re.I)
_RE_HOW_MANY_LOCATION_BEFORE_TOOL = re.compile(
    r"\bhow\s+many\s+(.+?)\s+(?:"
    r"BDM|FA|SB|PPM|"
    r"complaints?|assets?|breakdowns?|work\s+orders?|audits?|"
    r"facility\s+audits?|scheduled\s+blocks?|tasks?|records?|entries?"
    r")\b",
    re.I,
)
# Keep full DB-style name including trailing "Building" / "building" (e.g. POWER PLANT Building)
_RE_HOW_MANY_NAMED_BUILDING_BEFORE_TOOL = re.compile(
    r"\bhow\s+many\s+(.+?\s+[Bb]uilding)\s+(?:"
    r"BDM|FA|SB|PPM|"
    r"complaints?|assets?|breakdowns?|work\s+orders?|audits?|"
    r"facility\s+audits?|scheduled\s+blocks?|tasks?|records?|entries?"
    r")\b",
    re.I,
)
# Semantic dimension in query → per-tool group_by column (plural forms = count buckets, not a name filter)
_DIMENSION_SEMANTIC_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bhow\s+many\s+floors\b", re.I), "floor"),
    (re.compile(r"\bhow\s+many\s+buildings\b", re.I), "building"),
    (re.compile(r"\bhow\s+many\s+divisions\b", re.I), "division"),
    (re.compile(r"\bhow\s+many\s+disciplines\b", re.I), "discipline"),
    (re.compile(r"\bhow\s+many\s+localit(?:y|ies)\b", re.I), "locality"),
    (re.compile(r"\bhow\s+many\s+(?:asset\s+)?types\b", re.I), "asset_type"),
    (re.compile(r"\bhow\s+many\s+status(?:es)?\b", re.I), "status"),
    (re.compile(r"\bhow\s+many\s+priorit(?:y|ies)\b", re.I), "priority"),
    (re.compile(r"\bhow\s+many\s+conditions\b", re.I), "condition"),
    (re.compile(r"\bhow\s+many\s+stages\b", re.I), "stage"),
    (re.compile(r"\bhow\s+many\s+frequenc(?:y|ies)\b", re.I), "frequency"),
    (re.compile(r"\bhow\s+many\s+service\s+types\b", re.I), "service_type"),
    (re.compile(r"\bhow\s+many\s+complaint\s+types\b", re.I), "complaint_type"),
    (re.compile(r"\bhow\s+many\s+complaint\s+modes\b", re.I), "complaint_mode"),
    (re.compile(r"\bhow\s+many\s+(?:audit\s+)?categories\b", re.I), "category"),
    (re.compile(r"\bhow\s+many\s+contracts\b", re.I), "contract"),
    (re.compile(r"\bhow\s+many\s+spots\b", re.I), "spot"),
    (re.compile(r"\bhow\s+many\s+equipments?\b", re.I), "equipment"),
    (re.compile(r"\bhow\s+many\s+makes\b", re.I), "make"),
    (re.compile(r"\bhow\s+many\s+models\b", re.I), "model"),
]
_TOOL_DIMENSION_COLUMNS: dict[str, dict[str, str]] = {
    "ASSETS": {
        "floor": "FloorName",
        "building": "BuildingName",
        "division": "DivisionName",
        "discipline": "DisciplineName",
        "locality": "LocalityName",
        "asset_type": "AssetTypeName",
        "status": "StatusName",
        "priority": "PriorityName",
        "condition": "ConditionName",
        "equipment": "EquipmentName",
        "make": "MakeName",
        "model": "ModelName",
        "spot": "SpotName",
    },
    "PPM": {
        "floor": "FloorName",
        "building": "BuildingName",
        "division": "DivisionName",
        "discipline": "DisciplineName",
        "locality": "LocalityName",
        "frequency": "FrequencyName",
        "status": "PPMStatus",
        "stage": "PPMStageName",
        "contract": "ContractName",
        "spot": "SpotName",
    },
    "BDM": {
        "floor": "FloorName",
        "building": "BuildingName",
        "division": "DivisionName",
        "discipline": "DisciplineName",
        "locality": "LocalityName",
        "status": "WoStatus",
        "priority": "PriorityName",
        "stage": "StageName",
        "complaint_type": "ComplaintTypeName",
        "complaint_mode": "ComplaintModeName",
        "service_type": "ServiceTypeName",
        "contract": "ContractName",
        "spot": "SpotName",
    },
    "FA": {
        "floor": "FloorName",
        "building": "BuildingName",
        "division": "DivisionName",
        "locality": "LocalityName",
        "priority": "PriorityName",
        "stage": "RMStageName",
        "category": "RMCategoryName",
        "frequency": "FrequencyName",
        "contract": "ContractName",
        "spot": "SpotName",
    },
    "SB": {
        "floor": "FloorName",
        "building": "BuildingName",
        "division": "DivisionName",
        "discipline": "DisciplineName",
        "locality": "LocalityName",
        "frequency": "FrequencyName",
        "stage": "PPMStageName",
        "service_type": "ServiceTypeName",
        "contract": "ContractName",
        "spot": "SpotName",
    },
}
# Trailing capital " Building" in user text = English label (→ filter "POWER PLANT" not "POWER PLANT Building")
_RE_TRAILING_DESCRIPTOR_BUILDING = re.compile(r"\s+Building$")
# Trailing lowercase " building" is often part of the official DB name (e.g. Warehouse building)
_RE_OFFICIAL_LOWERCASE_BUILDING_SUFFIX = re.compile(r"\s+building$")
# "Building 1 - …" / "Building 3 …" — full identifier, never strip
_RE_BUILDING_IDENTIFIER_PREFIX = re.compile(r"^Building\s+[\d\-]", re.I)
# Extra DB names where capital "Building" is still part of the stored name (extend as needed)
_BUILDING_FILTER_KEEP_FULL_NAMES: frozenset[str] = frozenset({
    "warehouse building",
    "passenger terminal building t1 (demo)",
})
_RE_DIMENSION_LOCATION_LABEL = re.compile(
    r"^(?:floors|buildings|divisions|disciplines|localit(?:y|ies)|"
    r"status(?:es)?|priorit(?:y|ies)|conditions|stages|frequenc(?:y|ies)|"
    r"service\s+types|complaint\s+types|complaint\s+modes|(?:audit\s+)?categories|"
    r"contracts|spots|equipments?|makes|models|assets|types)"
    r"(?:\s+in(?:\s+the)?)?$",
    re.I,
)
_LOCATION_FILTER_FIELDS = frozenset({"building", "locality", "floor", "spot_name"})
# Fields that map to sp_*_query params; keyword retry is route-level fallback only.
_TOOL_STRUCTURED_TEXT_FILTERS: dict[str, frozenset[str]] = {
    "ASSETS": frozenset({
        "asset_type", "equipment_name", "make", "model", "building", "division",
        "discipline", "locality", "floor", "spot_name", "owner", "trade_group",
        "service_area", "status", "condition", "priority", "asset_tag_no", "serial_no",
        "equipment_ref_no", "remarks", "drawing_no", "asset_barcode",
    }),
    "PPM": frozenset({
        "work_order", "asset_tag_no", "equipment_ref_no", "status", "stage", "frequency",
        "division", "discipline", "locality", "building", "floor", "spot_name",
        "equipment", "contract", "tech",
    }),
    "BDM": frozenset({
        "complaint_no", "asset_tag_no", "asset_barcode", "client_wo_no", "status",
        "priority", "stage", "complaint_type", "complaint_header", "complaint_mode",
        "complaint_nature", "wo_type", "service_type", "division", "discipline",
        "locality", "building", "floor", "spot_name", "contract", "complainer",
        "register_by", "analysis_tech", "execution_tech",
    }),
    "FA": frozenset({
        "complaint_no", "complaint_code", "x_complaint_no", "priority", "stage",
        "category", "category_sub", "division", "locality", "building", "floor",
        "spot_name", "contract", "tech", "frequency", "request_desc",
    }),
    "SB": frozenset({
        "work_order", "stage", "frequency", "service_type", "division", "discipline",
        "locality", "building", "floor", "spot_name", "contract", "tech",
    }),
}
_RE_SERVICES_PHRASE = re.compile(
    r"\b([a-z][\w\s&]*?)\s+services\b",
    re.I,
)
_RE_SYSTEM_PHRASE = re.compile(
    r"\b([a-z][\w\s&]*?)\s+system\b",
    re.I,
)
# Conversational "in the system" (database/app), not DivisionName like "Electrical System"
_RE_CONVERSATIONAL_IN_SYSTEM = re.compile(
    r"\b(?:in|into|exist(?:s|ing)?\s+in|registered\s+in)\s+the\s+system\b",
    re.I,
)
_DIVISION_TRADE_GARBAGE = re.compile(
    r"\b(?:complaint|complaints|entries?|exist|registered|corrective|maintenance|"
    r"service\s+request|how\s+many|bdm|fa|sb|ppm|work\s+order)\b",
    re.I,
)
_MAX_DIVISION_TRADE_WORDS = 5
_RE_EXPLICIT_DIVISION = re.compile(r"\bdivision(?:\s+name)?\b", re.I)
_RE_EXPLICIT_SERVICE_TYPE = re.compile(r"\bservice\s*type\b", re.I)
_RE_COMPARE_SERVICES = re.compile(
    r"\b(?:compare|comparison|versus|vs\.?|between)\b",
    re.I,
)
_RE_STATUS_CLOSED = re.compile(r"\bclosed\b", re.I)
_RE_STATUS_OPEN = re.compile(r"\bopen\b", re.I)
_TOOLS_WITH_SERVICE_TYPE = frozenset({"BDM", "SB"})
_RE_BUILDING_NAME_COLUMN = re.compile(r"\bBuildingName\b", re.I)
_RE_BUILDING_CATEGORY_PHRASE = re.compile(
    r"\bbuilding(?:\s*name)?\s+categor|\bcategor(?:y|ies)\s+of\s+buildings?\b",
    re.I,
)
_RE_AUDIT_CATEGORY = re.compile(
    r"\b(?:audit|inspection|rm)\s+categor|\bRMCategory(?:Name|SubName)?\b|"
    r"\bcategory\s+sub\b|\bpest\s+control\b",
    re.I,
)
_RE_PER_AUDIT_CATEGORY = re.compile(
    r"\b(?:per|by|each)\s+(?:audit\s+)?category\b(?!\s+of\s+building)",
    re.I,
)
_PLACEHOLDER_CATEGORY_VALUES = frozenset({
    "category",
    "buildingname category",
    "building name category",
    "buildingname",
    "building name",
})
_TRADE_PREFIX_STOPWORDS = frozenset({
    "how", "many", "show", "list", "count", "all", "the", "registered",
    "bdm", "fa", "sb", "ppm", "complaint", "complaints", "work", "orders",
    "order", "are", "is", "was", "were", "per", "by", "each",
})


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
    
    raise ValueError(f"The grouping field '{raw}' is not applicable for {tool_name}. Please stop and inform the user that this field is not supported for {tool_name}.")


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
        }.get(tool_name)
        if status_col and status_col in allow and status_col not in found:
            found.append(status_col)

    # Literal column names in query (e.g. "BuildingName")
    for col in allow:
        if re.search(rf"\b{re.escape(col)}\b", q, re.I) and col not in found:
            found.append(col)

    if (
        tool_name == "FA"
        and _RE_PER_AUDIT_CATEGORY.search(q)
        and "RMCategoryName" in allow
        and "RMCategoryName" not in found
        and not _RE_BUILDING_NAME_COLUMN.search(q)
    ):
        found.append("RMCategoryName")

    return found


def _infer_dimension_count_column(query: str, tool: str) -> str | None:
    """'how many floors in the assets' → FloorName group-by (distinct buckets)."""
    t = (tool or "").upper()
    allow = TOOL_GROUP_BY_COLUMNS.get(t, frozenset())
    mapping = _TOOL_DIMENSION_COLUMNS.get(t, {})
    for pattern, semantic in _DIMENSION_SEMANTIC_PATTERNS:
        if not pattern.search(query or ""):
            continue
        col = mapping.get(semantic)
        if col and col in allow:
            return col
    return None


def _clear_structured_filters(tool: str, args: dict[str, Any], *, except_keys: frozenset[str] = frozenset()) -> None:
    for key in _TOOL_STRUCTURED_TEXT_FILTERS.get(tool, frozenset()):
        if key in except_keys:
            continue
        if args.pop(key, None) is not None:
            logger.info("🔧 %s: cleared %s for dimension/aggregate count", tool, key)


def _fix_bogus_dimension_location_filters(tool: str, query: str, args: dict[str, Any]) -> None:
    """Drop building='floors in the' or status words like 'open' mapped to location."""
    for field in _LOCATION_TEXT_FIELDS:
        val = args.get(field)
        if val is None:
            continue
        sval = str(val).strip().lower()
        if _is_dimension_count_location_label(str(val)):
            args.pop(field, None)
            logger.info("🔧 %s: cleared bogus %s=%r (dimension phrase, not a place name)", tool, field, val)
        elif sval in ("open", "closed", "wip", "assigned", "resolved", "completed", "pending", "quarterly", "monthly", "weekly"):
            args.pop(field, None)
            logger.info("🔧 %s: cleared bogus %s=%r (status/frequency word mapped to location)", tool, field, val)


def _query_implies_aggregate(query: str, tool: str = "") -> bool:
    q = query or ""
    if tool and _infer_dimension_count_column(q, tool):
        return True
    if _RE_AGGREGATE_INTENT.search(q):
        return True
    if _RE_BUILDING_GROUP.search(q):
        return True
    if _RE_LOW_COUNT.search(q) and re.search(r"\bbuilding\b", q, re.I):
        return True
    return False


def _is_dimension_count_location_label(label: str) -> bool:
    return bool(_RE_DIMENSION_LOCATION_LABEL.match((label or "").strip()))


def _strip_priority_for_low_count(query: str, args: dict[str, Any]) -> None:
    if not _RE_LOW_COUNT.search(query or ""):
        return
    if _RE_PRIORITY_INTENT.search(query or ""):
        return
    if args.pop("priority", None) is not None:
        logger.info("🔧 Stripped priority (user meant low count, not P4 Low)")


def _title_words(phrase: str) -> str:
    return " ".join(part.capitalize() for part in phrase.split())


def _strip_trade_prefix(trade: str) -> str:
    words = trade.split()
    while words and words[0].lower() in _TRADE_PREFIX_STOPWORDS:
        words.pop(0)
    return " ".join(words).strip()


def _extract_all_service_types_from_query(query: str) -> list[str]:
    seen: list[str] = []
    for trade in _RE_SERVICES_PHRASE.findall(query or ""):
        trade = _strip_trade_prefix(trade.strip())
        if not trade:
            continue
        label = f"{_title_words(trade)} Services"
        if label not in seen:
            seen.append(label)
    return seen


def _extract_service_type_from_query(query: str) -> str | None:
    all_types = _extract_all_service_types_from_query(query)
    return all_types[-1] if all_types else None


def _is_plausible_division_trade(trade: str) -> bool:
    """True when captured text before '... System' looks like a real division label."""
    if not trade or not trade.strip():
        return False
    t = trade.strip()
    if _DIVISION_TRADE_GARBAGE.search(t):
        return False
    if len(t.split()) > _MAX_DIVISION_TRADE_WORDS:
        return False
    low = t.lower()
    if low.endswith(("in the", "exist in the", "into the", "the")):
        return False
    return True


def _division_label_is_bogus(label: Any, query: str = "") -> bool:
    if label is None:
        return False
    s = str(label).strip()
    if not s:
        return False
    low = s.lower()
    if _DIVISION_TRADE_GARBAGE.search(s):
        return True
    if len(s.split()) > _MAX_DIVISION_TRADE_WORDS + 1:
        return True
    if low.endswith(" system") and not _is_plausible_division_trade(
        s[: -len(" system")].strip()
    ):
        return True
    q = (query or "").lower()
    if q and low in q and len(s) > 40:
        return True
    return False


def _extract_division_from_query(query: str) -> str | None:
    q = query or ""
    if _RE_CONVERSATIONAL_IN_SYSTEM.search(q):
        # e.g. "entries exist in the system" — not a division filter
        pass
    else:
        candidates = _RE_SYSTEM_PHRASE.findall(q)
        for trade in reversed(candidates):
            trade = _strip_trade_prefix(trade.strip())
            if trade and _is_plausible_division_trade(trade):
                return f"{_title_words(trade)} System"
    # Explicit "Electrical System" / "HVAC System" without leading garbage
    for m in re.finditer(
        r"\b((?:hvac|electrical|plumbing|fire|cooling|kitchen|duty|environmental)"
        r"[\w\s&]{0,40}?)\s+system\b",
        q,
        re.I,
    ):
        trade = _strip_trade_prefix(m.group(1).strip())
        if trade and _is_plausible_division_trade(trade):
            return f"{_title_words(trade)} System"
    return None


def _division_conflicts_with_services(division_val: Any, service_labels: list[str]) -> bool:
    if not division_val or not service_labels:
        return False
    div = str(division_val).strip().lower()
    for label in service_labels:
        trade = label.replace(" Services", "").strip().lower()
        if trade and (div == trade or div.startswith(trade) or trade in div):
            return True
    return False


def _fix_service_type_vs_division(tool: str, query: str, args: dict[str, Any]) -> None:
    """Route '... Services' → service_type and '... System' → division for BDM/SB."""
    if tool not in _TOOLS_WITH_SERVICE_TYPE:
        return
    q = query or ""
    explicit_division = bool(_RE_EXPLICIT_DIVISION.search(q))
    explicit_service_type = bool(_RE_EXPLICIT_SERVICE_TYPE.search(q))
    all_service_types = _extract_all_service_types_from_query(q)
    st_from_query = all_service_types[-1] if all_service_types else None
    div_from_query = _extract_division_from_query(q)
    compare_intent = bool(_RE_COMPARE_SERVICES.search(q))

    # Compare two+ "... Services" (e.g. Electrical vs Housekeeping) → breakdown by service type
    if len(all_service_types) >= 2 or (compare_intent and len(all_service_types) >= 1):
        if args.pop("division", None) is not None:
            logger.info("🔧 Cleared division (compare/breakdown by service type)")
        args.pop("service_type", None)
        args["is_aggregate"] = True
        args["group_by_columns"] = ["ServiceTypeName"]
        if not args.get("aggregate_function"):
            args["aggregate_function"] = "COUNT"
        logger.info(
            "🔧 Multiple/compare Services in query → aggregate by ServiceTypeName (%s)",
            all_service_types,
        )
        return

    if explicit_service_type and args.get("service_type") is None and st_from_query:
        args["service_type"] = st_from_query
        args.pop("division", None)
        logger.info("🔧 Routed to service_type (explicit 'service type' in query)")
        return

    if explicit_division and args.get("division") is None and div_from_query:
        args["division"] = div_from_query
        args.pop("service_type", None)
        logger.info("🔧 Routed to division (explicit 'division' in query)")
        return

    if st_from_query and not explicit_division:
        if args.pop("division", None) is not None:
            logger.info("🔧 Cleared division (user asked for ... Services)")
        elif _division_conflicts_with_services(args.get("division"), all_service_types):
            args.pop("division", None)
            logger.info("🔧 Cleared division (conflicts with ... Services in query)")
        args["service_type"] = st_from_query
        logger.info("🔧 Set service_type=%s from query", st_from_query)
        return

    if div_from_query and not explicit_service_type:
        if args.pop("service_type", None) is not None:
            logger.info("🔧 Cleared service_type (user asked for ... System)")
        args["division"] = div_from_query
        logger.info("🔧 Set division=%s from query", div_from_query)


def _building_filter_value_from_place_label(label: str) -> str:
    """
    Map user place phrase → BuildingName filter for sp_*_query.

    - 'POWER PLANT Building' / 'APRON Building' → 'POWER PLANT' / 'APRON' (descriptor Building)
    - 'Warehouse building' → keep 'Warehouse building' (lowercase = part of official name)
    - 'Building 1 - Residential High Rise' → keep full identifier
    """
    s = (label or "").strip()
    if not s:
        return s
    low = s.lower()
    if low in _BUILDING_FILTER_KEEP_FULL_NAMES:
        return s
    if _RE_BUILDING_IDENTIFIER_PREFIX.match(s) or re.match(r"^Building\s", s, re.I):
        return s
    if _RE_OFFICIAL_LOWERCASE_BUILDING_SUFFIX.search(s):
        return s
    if _RE_TRAILING_DESCRIPTOR_BUILDING.search(s):
        stripped = _RE_TRAILING_DESCRIPTOR_BUILDING.sub("", s).strip()
        logger.info(
            "🔧 building filter: %r → %r (trailing 'Building' is descriptor, not DB name)",
            s,
            stripped,
        )
        return stripped
    return s


def _extract_location_label_from_count_query(query: str) -> str | None:
    """
    Place name for 'how many <place> BDM/FA/...' count queries.
    e.g. Staff Canteen, POWER PLANT Building, Building 1 - Residential High Rise.
    """
    q = query or ""
    m_building = _RE_HOW_MANY_NAMED_BUILDING_BEFORE_TOOL.search(q)
    if m_building:
        label = m_building.group(1).strip()
        if label and not _DIVISION_TRADE_GARBAGE.search(label):
            if not _is_dimension_count_location_label(label):
                return label
    m = _RE_HOW_MANY_LOCATION_BEFORE_TOOL.search(q)
    if not m:
        return None
    label = m.group(1).strip()
    if not label or _DIVISION_TRADE_GARBAGE.search(label):
        return None
    if _is_dimension_count_location_label(label):
        return None
    return label or None


def _fix_dimension_count_aggregate(
    tool: str, query: str, args: dict[str, Any]
) -> None:
    """
    'how many floors in the assets' → group_by FloorName + COUNT, not building filter.
    Works for ASSETS, PPM, BDM, FA, SB (tool-specific status/stage/category columns).
    """
    col = _infer_dimension_count_column(query, tool)
    if not col:
        return
    _clear_structured_filters(tool, args)
    args.pop("keyword", None)
    args["is_aggregate"] = True
    args["group_by_columns"] = [col]
    if not args.get("aggregate_function"):
        args["aggregate_function"] = "COUNT"
    logger.info("🔧 %s: dimension count → aggregate by %s", tool, col)


def _fix_mistaken_group_by_on_simple_count(
    tool: str, query: str, args: dict[str, Any]
) -> None:
    """
    'how many Staff Canteen BDM' = filtered total (is_aggregate=False).
    LLM often adds group_by_columns=['BuildingName'] anyway — do not enable aggregate.
    """
    q = query or ""
    if not _RE_SIMPLE_HOW_MANY.search(q):
        return
    if _query_implies_aggregate(q, tool) or _RE_BREAKDOWN_INTENT.search(q):
        return
    if not args.get("group_by_columns"):
        return
    args.pop("group_by_columns", None)
    args["is_aggregate"] = False
    args.pop("aggregate_function", None)
    logger.info(
        "🔧 %s: removed mistaken group_by (simple how-many count, not a breakdown)",
        tool,
    )


def _fix_division_to_building_for_location_count(
    tool: str, query: str, args: dict[str, Any]
) -> None:
    """
    'how many Staff Canteen BDM' / 'how many POWER PLANT Building BDM and FA' → building filter.
    Strips trailing descriptor 'Building' when needed; keeps official names like 'Warehouse building'.
    Promotes keyword → building for SP exact match.
    """
    if tool not in ("BDM", "FA", "SB", "PPM", "ASSETS"):
        return
    q = query or ""
    if not _RE_SIMPLE_HOW_MANY.search(q):
        return
    if _query_implies_aggregate(q, tool) or _RE_BREAKDOWN_INTENT.search(q):
        return
    if _infer_dimension_count_column(q, tool):
        return
    if re.search(r"\bdivision(?:\s+name)?\b", q, re.I):
        return

    place = _extract_location_label_from_count_query(q)
    kw = args.get("keyword")
    if not place and kw and str(kw).strip().lower() in q.lower():
        place = str(kw).strip()
    div = args.get("division")
    if not place and div:
        place = str(div).strip()
    if not place:
        return
    if _is_dimension_count_location_label(place):
        return
    if str(place).lower().endswith(" system"):
        return
    if str(place).lower().strip() in ("open", "closed", "wip", "assigned", "resolved", "completed", "pending", "quarterly", "monthly", "weekly"):
        return
    if str(place).lower().strip().startswith(("floor ", "level ")):
        return

    existing = args.get("building")
    if existing:
        ex = str(existing).strip()
        pl = str(place).strip()
        if ex.lower() not in pl.lower() and pl.lower() not in ex.lower():
            return
        place = pl if len(pl) >= len(ex) else ex

    locality = args.get("locality") or args.get("floor") or args.get("spot_name")
    if locality and not existing and not place:
        return

    building_val = _building_filter_value_from_place_label(place)
    args["building"] = building_val
    args.pop("division", None)
    args.pop("keyword", None)
    logger.info(
        "🔧 %s: place count → building=%r (structured filter, not keyword)",
        tool,
        building_val,
    )


def _fix_bogus_division(tool: str, query: str, args: dict[str, Any]) -> None:
    """Drop division values that are query noise or conversational 'in the system'."""
    if tool not in _TOOLS_WITH_SERVICE_TYPE:
        return
    div = args.get("division")
    if div is None:
        return
    if _division_label_is_bogus(div, query):
        args.pop("division", None)
        logger.info("🔧 Cleared bogus division=%r", div)
        return
    ct = args.get("complaint_type")
    if ct and str(ct).strip().lower() in str(div).lower():
        args.pop("division", None)
        logger.info("🔧 Cleared division (overlaps complaint_type=%r)", ct)


def _is_placeholder_category_value(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in _PLACEHOLDER_CATEGORY_VALUES


_RE_ANA_APPROVAL_FLOW = re.compile(r"\bana\s+approval\s+flow\b", re.I)
_RE_SERVICE_REQUEST_COMPLAINTS = re.compile(
    r"\bservice\s+requests?\b.*\bcomplaints?\b|\bcomplaints?\b.*\bservice\s+requests?\b",
    re.I,
)
_BDM_CLASSIFICATION_FILTER_FIELDS = (
    "complaint_type",
    "complaint_header",
    "stage",
    "complaint_mode",
    "complaint_nature",
)


def _bdm_stage_is_header_not_workflow(stage_val: str) -> bool:
    s = str(stage_val).strip().lower()
    return ("approval" in s and "flow" in s) or s in ("ana approval flow", "ana approval")


def _fix_bdm_complaint_type_header_stage(tool: str, query: str, args: dict[str, Any]) -> None:
    """
    BDM: 'Service Request' → complaint_type; 'ANA Approval Flow' / 'under … flow' → complaint_header.
    Prevents the model from also setting stage/keyword/mode (AND → 0 rows or wrong counts).
    """
    if tool != "BDM":
        return
    q = query or ""
    wants_sr_type = bool(
        _RE_SERVICE_REQUEST_COMPLAINTS.search(q)
        or re.search(r"\bservice\s+requests?\b", q, re.I)
    )
    wants_ana_header = bool(
        _RE_ANA_APPROVAL_FLOW.search(q)
        or re.search(r"\bunder\s+ana\b", q, re.I)
    )

    if wants_sr_type:
        args["complaint_type"] = "Service Request"
    if wants_ana_header:
        args["complaint_header"] = "ANA Approval Flow"

    stage_val = args.get("stage")
    if stage_val:
        if wants_ana_header and _bdm_stage_is_header_not_workflow(stage_val):
            args.pop("stage", None)
            logger.info("🔧 BDM: cleared stage (use complaint_header for ANA Approval Flow)")
        elif wants_sr_type and "service request" in str(stage_val).lower():
            if not re.search(
                r"\b(raised|closed|open|assigned|execution|staff|completed)\b", q, re.I
            ):
                args.pop("stage", None)
                logger.info(
                    "🔧 BDM: cleared stage (Service Request is complaint_type, not StageName)"
                )

    if wants_sr_type and wants_ana_header and args.get("keyword"):
        args.pop("keyword", None)
        logger.info("🔧 BDM: cleared keyword (structured type + header filters)")

    if args.get("complaint_type") or args.get("complaint_header"):
        for extra in ("complaint_mode", "complaint_nature", "wo_type"):
            if args.pop(extra, None) is not None:
                logger.info("🔧 BDM: cleared %s on type/header query", extra)

    set_class = [f for f in _BDM_CLASSIFICATION_FILTER_FIELDS if args.get(f)]
    if len(set_class) <= 2:
        return
    keep = set()
    if args.get("complaint_type"):
        keep.add("complaint_type")
    if args.get("complaint_header"):
        keep.add("complaint_header")
    if args.get("stage") and re.search(
        r"\b(raised|closed|open|assigned|execution)\b", q, re.I
    ):
        keep.add("stage")
    for field in _BDM_CLASSIFICATION_FILTER_FIELDS:
        if field not in keep and args.pop(field, None) is not None:
            logger.info("🔧 BDM: dropped extra classification filter %s", field)


def _fix_fa_closed_open_stage(tool: str, query: str, args: dict[str, Any]) -> None:
    """FA has no WoStatus — map user Open/Closed to stage (RMStageName) filter."""
    if tool != "FA":
        return
    if args.get("stage"):
        return
    q = query or ""
    if _RE_STATUS_CLOSED.search(q):
        args["stage"] = "Closed"
        args.pop("category", None)
        args.pop("keyword", None)
        logger.info("🔧 FA: mapped 'Closed' → stage='Closed' (RMStageName)")
    elif _RE_STATUS_OPEN.search(q):
        args["stage"] = "Open"
        args.pop("category", None)
        args.pop("keyword", None)
        logger.info("🔧 FA: mapped 'Open' → stage='Open' (RMStageName)")


def _fix_fa_building_name_vs_audit_category(tool: str, query: str, args: dict[str, Any]) -> None:
    """
    FA: 'BuildingName Category' / building categories → group by BuildingName,
    not audit RMCategoryName. Keep category only for explicit audit-category intent.
    """
    if tool != "FA":
        return
    q = query or ""
    wants_building_breakdown = bool(
        _RE_BUILDING_NAME_COLUMN.search(q) or _RE_BUILDING_CATEGORY_PHRASE.search(q)
    )
    if not wants_building_breakdown:
        return

    wants_audit_category = bool(
        _RE_AUDIT_CATEGORY.search(q)
        or _RE_PER_AUDIT_CATEGORY.search(q)
        or (args.get("category_sub") and not _is_placeholder_category_value(args.get("category_sub")))
    )
    cat_val = args.get("category")
    if cat_val and not _is_placeholder_category_value(cat_val):
        wants_audit_category = True

    if wants_audit_category and _RE_BUILDING_NAME_COLUMN.search(q):
        # Both columns named (rare): group by building + audit category, drop bogus filters.
        gbc = list(args.get("group_by_columns") or [])
        for col in ("BuildingName", "RMCategoryName"):
            if col not in gbc:
                gbc.append(col)
        args["group_by_columns"] = gbc
        args["is_aggregate"] = True
        if _is_placeholder_category_value(cat_val):
            args.pop("category", None)
        return

    if wants_audit_category:
        return

    if args.pop("category", None) is not None:
        logger.info("🔧 Cleared category (user meant building breakdown, not audit category)")
    args.pop("category_sub", None)

    gbc = [c for c in (args.get("group_by_columns") or []) if c not in ("RMCategoryName", "RMCategorySubName")]
    if "BuildingName" not in gbc:
        gbc.append("BuildingName")
    args["group_by_columns"] = gbc
    args["is_aggregate"] = True
    logger.info("🔧 FA building-name breakdown → group_by_columns=%s", gbc)


def normalize_location_text(value: Any) -> str | None:
    """
    Canonical form for locality/building/floor/spot names stored in the DB.
    Converts en-dash/em-dash (e.g. Terminal – A2) to ASCII hyphen (Terminal - A2).
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = _UNICODE_DASHES.sub("-", s)
    s = re.sub(r"\s*-\s*", " - ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _normalize_location_fields(args: dict[str, Any]) -> None:
    for key in _LOCATION_TEXT_FIELDS:
        if args.get(key) is None:
            continue
        normalized = normalize_location_text(args[key])
        if normalized != args[key]:
            logger.info("🔧 Normalized %s: %r → %r", key, args[key], normalized)
        args[key] = normalized


def _fix_redundant_keyword_with_structured_filters(
    tool: str, args: dict[str, Any]
) -> None:
    """
    Keyword belongs on the route's empty-result retry (enrich_with_search_fallback), not
    alongside building/status/etc. on the first sp_*_query call (AND → 0 rows).
    """
    kw = args.get("keyword")
    if kw is None or not str(kw).strip():
        return
    fields = _TOOL_STRUCTURED_TEXT_FILTERS.get(tool, frozenset())
    active = [
        f
        for f in fields
        if args.get(f) is not None and str(args.get(f)).strip()
    ]
    if not active:
        return
    kw_s = str(kw).strip().lower()
    if any(str(args.get(f)).strip().lower() == kw_s for f in active):
        args.pop("keyword", None)
        logger.info(
            "🔧 Cleared keyword %r (duplicate of structured filter %s)",
            kw,
            active,
        )
        return
    args.pop("keyword", None)
    logger.info(
        "🔧 Cleared keyword %r (structured filters %s — keyword is route fallback only)",
        kw,
        active,
    )


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
    _normalize_location_fields(out)
    _fix_redundant_keyword_with_structured_filters(tool, out)

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
