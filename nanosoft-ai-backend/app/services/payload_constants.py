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
_SMART_PUNCTUATION_TRANSLATION = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201A": "'",
    "\u201B": "'",
    "\u201C": '"',
    "\u201D": '"',
    "\u201E": '"',
    "\u201F": '"',
})


def _normalize_smart_punctuation(value: Any) -> Any:
    if isinstance(value, str):
        return value.translate(_SMART_PUNCTUATION_TRANSLATION)
    if isinstance(value, list):
        return [_normalize_smart_punctuation(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_smart_punctuation(item) for key, item in value.items()}
    return value

# Canonical group-by columns allowed per tool (must match DB / stored procedures)
TOOL_GROUP_BY_COLUMNS: dict[str, frozenset[str]] = {
    "ASSETS": frozenset({
        "DivisionName", "DisciplineName", "BuildingName", "FloorName", "LocalityName", "LocalityCode",
        "StatusName", "ConditionName", "PriorityName", "AssetTypeName", "EquipmentName",
        "MakeName", "ModelName", "SpotName", "TradeGroupName", "ServiceAreaName",
        "OnHold", "IsSnagged", "IsScraped", "IsEnablePPM", "IsEnableBDM",
    }),
    "PPM": frozenset({
        "DivisionName", "DisciplineName", "BuildingName", "FloorName", "LocalityName", "LocalityCode",
        "FrequencyName", "PPMStatus", "PPMStageName", "ContractName", "SpotName",
    }),
    "BDM": frozenset({
        "DivisionName", "DisciplineName", "BuildingName", "FloorName", "LocalityName", "LocalityCode",
        "WoStatus", "PriorityName", "StageName", "ComplaintTypeName", "ComplaintModeName",
        "ComplaintHeaderName", "ServiceTypeName", "SpotName", "ContractName",
    }),
    "FA": frozenset({
        "DivisionName", "BuildingName", "FloorName", "LocalityName", "LocalityCode", "PriorityName",
        "RMStageName", "RMCategoryName", "RMCategorySubName", "FrequencyName",
        "ContractName", "SpotName", "IsRMWithdraw", "IsRMRework", "IsActive",
    }),
    "SB": frozenset({
        "DivisionName", "DisciplineName", "BuildingName", "FloorName", "LocalityName", "LocalityCode",
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
    "localitycode": "LocalityCode",
    "locality_code": "LocalityCode",
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
    "complaintheader": "ComplaintHeaderName",
    "complaintheadername": "ComplaintHeaderName",
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
    "onholds": "OnHold",
    "onheld": "OnHold",
    "issnagged": "IsSnagged",
    "snagged": "IsSnagged",
    "snags": "IsSnagged",
    "isscraped": "IsScraped",
    "scraped": "IsScraped",
    "scrapped": "IsScraped",
    "isenableppm": "IsEnablePPM",
    "enableppm": "IsEnablePPM",
    "ppmenabled": "IsEnablePPM",
    "isenablebdm": "IsEnableBDM",
    "enablebdm": "IsEnableBDM",
    "bdmenabled": "IsEnableBDM",
}

# Query phrase fragment → group_by column (when inferring from user text)
_QUERY_GROUP_BY_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bbuilding\s*name\b", re.I), "BuildingName"),
    (re.compile(r"\b(?:per|by|each|based)\s+locality\b|\blocality\s+(?:based|wise)\b", re.I), "LocalityName"),
    (re.compile(r"\b(?:per|by|each|based)\s+building\b|\bbuilding\s+(?:based|wise)\b", re.I), "BuildingName"),
    (re.compile(r"\b(?:per|by|each|based)\s+division\b|\bdivision\s+(?:based|wise)\b", re.I), "DivisionName"),
    (re.compile(r"\b(?:per|by|each|based)\s+floor\b|\bfloor\s+(?:based|wise)\b", re.I), "FloorName"),
    (re.compile(r"\b(?:per|by|each|based)\s+priority\b|\bpriority\s+(?:based|wise)\b", re.I), "PriorityName"),
    (re.compile(r"\b(?:per|by|each|based)\s+stage\b|\bstage\s+(?:based|wise)\b", re.I), "StageName"),
    (re.compile(r"\b(?:per|by|each|based)\s+frequency\b|\bfrequency\s+(?:based|wise)\b", re.I), "FrequencyName"),
    (re.compile(r"\b(?:per|by|each|based)\s+contract\b|\bcontract\s+(?:based|wise)\b", re.I), "ContractName"),
    (re.compile(r"\b(?:per|by|each|based)\s+service\s*section\b|\bservice\s*section\s+(?:based|wise)\b", re.I), "DivisionName"),
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
    "BDM": frozenset({"limit"}),
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
    (re.compile(r"\bhow\s+many\s+service\s+(?:types|categor(?:y|ies))\b", re.I), "service_type"),
    (re.compile(r"\bhow\s+many\s+complaint\s+types\b", re.I), "complaint_type"),
    (re.compile(r"\bhow\s+many\s+complaint\s+modes\b", re.I), "complaint_mode"),
    (re.compile(r"\bhow\s+many\s+(?:audit\s+)?categories\b", re.I), "category"),
    (re.compile(r"\bhow\s+many\s+contracts\b", re.I), "contract"),
    (re.compile(r"\bhow\s+many\s+(?:spots|spot\s*names?)\b", re.I), "spot"),
    (re.compile(r"\bhow\s+many\s+equipments?\b", re.I), "equipment"),
    (re.compile(r"\bhow\s+many\s+makes\b", re.I), "make"),
    (re.compile(r"\bhow\s+many\s+models\b", re.I), "model"),
    (re.compile(r"\bhow\s+many\s+on\s*holds?\b|\bhow\s+many\s+onholds?\b", re.I), "OnHold"),
    (re.compile(r"\bhow\s+many\s+snagged\b|\bhow\s+many\s+snags?\b", re.I), "IsSnagged"),
    (re.compile(r"\bhow\s+many\s+scrap(?:ed|ped)\b", re.I), "IsScraped"),
    (re.compile(r"\bhow\s+many\s+ppm\s+enabled\b|\bhow\s+many\s+enable\s*ppm\b", re.I), "IsEnablePPM"),
    (re.compile(r"\bhow\s+many\s+bdm\s+enabled\b|\bhow\s+many\s+enable\s*bdm\b", re.I), "IsEnableBDM"),
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
        "complaint_header": "ComplaintHeaderName",
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



__all__ = [name for name in dir() if not name.startswith('__') and name != 'logging' and name != 're' and name != 'Any']
