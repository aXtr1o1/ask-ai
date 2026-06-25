from __future__ import annotations
import logging
import re
from typing import Any
from app.services.payload_constants import *

logger = logging.getLogger('payload_helpers')

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
    if tool_name in ("PPM", "ASSETS", "FA") and key in ("servicetype", "servicetypename", "servicesection", "servicesectionname"):
        return "DivisionName"
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
    
    # If not found in the predefined strict list, just return the raw column name
    # so that local aggregation fallback (or the database itself) can handle it.
    return raw


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
        elif sval in ("open", "closed", "wip", "assigned", "resolved", "completed", "pending", "quarterly", "monthly", "weekly", "operational", "active"):
            args.pop(field, None)
            if not args.get("status"):
                if sval in ("open", "operational", "active"):
                    args["status"] = "Open"
                elif sval in ("closed", "completed", "resolved"):
                    args["status"] = "Closed"
                else:
                    args["status"] = val
            logger.info("🔧 %s: cleared bogus %s=%r and inferred status=%r", tool, field, val, args.get("status"))


def _query_implies_aggregate(query: str, tool: str = "") -> bool:
    q = query or ""
    if tool and _infer_group_by_from_query(q, tool):
        return True
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


_KNOWN_ACRONYMS: frozenset[str] = frozenset({
    "HVAC", "BMS", "AC", "MEP", "CCTV", "IT", "AV", "ELV", "ICT", "LV", "HV",
})

def _title_words(phrase: str) -> str:
    result = []
    for part in phrase.split():
        upper = part.upper()
        if upper in _KNOWN_ACRONYMS:
            result.append(upper)          # HVAC / BMS stays all-caps
        else:
            result.append(part.capitalize())
    return " ".join(result)



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
            # Strip leading prepositions (e.g. "in hvac" → "hvac" from "are in hvac system")
            trade = _RE_LEADING_PREPOSITION.sub("", trade).strip()
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
        trade = _RE_LEADING_PREPOSITION.sub("", trade).strip()
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


_RE_LEADING_PREPOSITION = re.compile(
    r"^(?:in|at|of|for|from|within|the|a|an)\s+",
    re.IGNORECASE,
)
_FIELDS_WITH_LEADING_PREPOSITION = ("division", "discipline", "locality", "building", "floor", "spot_name")


def _strip_leading_prepositions(args: dict[str, Any]) -> None:
    """
    Strip query prepositions the model accidentally includes in field values.
    Examples:
      division="In Hvac System"  → "Hvac System"  (model included 'in' from 'are in hvac system')
      locality="at Terminal A"   → "Terminal A"
      building="the main tower"  → "main tower"
    """
    for field in _FIELDS_WITH_LEADING_PREPOSITION:
        val = args.get(field)
        if val is None or not isinstance(val, str):
            continue
        cleaned = _RE_LEADING_PREPOSITION.sub("", val.strip()).strip()
        if cleaned != val.strip():
            logger.info("🔧 Stripped leading preposition from %s: %r → %r", field, val, cleaned)
            args[field] = cleaned if cleaned else None
            if args[field] is None:
                args.pop(field, None)


def _fix_bogus_division(tool: str, query: str, args: dict[str, Any]) -> None:
    """Drop division values that are query noise or conversational 'in the system'."""
    # First strip any leading prepositions the model accidentally included
    _strip_leading_prepositions(args)

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
_RE_WITHOUT_APPROVAL_FLOW = re.compile(
    r"\b(?:non\s*[- ]?\s*approval|without\s+approval|no\s+approval)\s+"
    r"(?:work\s*)?flows?\b",
    re.I,
)
_RE_APPROVAL_FLOW = re.compile(
    r"\b(?:ana\s+)?approval\s+(?:work\s*)?flows?\b",
    re.I,
)
_RE_SERVICE_REQUEST_COMPLAINTS = re.compile(
    r"\bservice\s+requests?\b.*\bcomplaints?\b|\bcomplaints?\b.*\bservice\s+requests?\b",
    re.I,
)
_BDM_COMPLAINT_TYPE_VALUES = (
    "Service Request",
    "Corrective Maintenance",
    "Reactive Maintenance",
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


def _bdm_complaint_type_from_query(query: str) -> str | None:
    q = query or ""
    for value in _BDM_COMPLAINT_TYPE_VALUES:
        pattern = r"\b" + r"\s+".join(map(re.escape, value.split())) + r"\b"
        if re.search(pattern, q, re.I):
            return value
    return None


def _bdm_complaint_header_from_query(query: str) -> str | None:
    q = query or ""
    if _RE_WITHOUT_APPROVAL_FLOW.search(q):
        return "Without Approval Flow"
    if _RE_ANA_APPROVAL_FLOW.search(q) or _RE_APPROVAL_FLOW.search(q) or re.search(r"\bunder\s+ana\b", q, re.I):
        return "ANA Approval Flow"
    return None


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
    explicit_complaint_type = _bdm_complaint_type_from_query(q)
    explicit_complaint_header = _bdm_complaint_header_from_query(q)
    wants_ana_header = explicit_complaint_header == "ANA Approval Flow"

    if explicit_complaint_type:
        if args.get("complaint_type") != explicit_complaint_type:
            logger.info(
                "🔧 BDM: corrected complaint_type=%r from query",
                explicit_complaint_type,
            )
        args["complaint_type"] = explicit_complaint_type
    elif args.get("complaint_type") in _BDM_COMPLAINT_TYPE_VALUES:
        if not re.search(rf"\b{re.escape(str(args['complaint_type']))}\b", q, re.I):
            args.pop("complaint_type", None)
            logger.info("🔧 BDM: cleared guessed complaint_type not present in query")

    if wants_sr_type:
        args["complaint_type"] = "Service Request"
    if explicit_complaint_header:
        if args.get("complaint_header") != explicit_complaint_header:
            logger.info(
                "🔧 BDM: corrected complaint_header=%r from query",
                explicit_complaint_header,
            )
        args["complaint_header"] = explicit_complaint_header

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


# Words that describe the act of creating/submitting a record — NOT a status value.
# The model often maps "are registered" → status="Open" which is wrong.
_CONVERSATIONAL_VERBS_NOT_STATUS = re.compile(
    r"\b(registered|raised|found|created|submitted|logged|entered|added|done|reported|placed)\b",
    re.IGNORECASE,
)
# Explicit status words that confirm the user really wants a status filter.
_EXPLICIT_STATUS_WORDS = re.compile(
    r"\b(open|closed|pending|resolved|assigned|cancelled|canceled|completed|in\s+progress|"
    r"preliminary\s+confirmed|snagged|scraped|on\s+hold|online|offline|active|inactive|"
    r"standby|allocated|allocation|allocating)\b",
    re.IGNORECASE,
)


def _strip_implicit_status_for_conversational_verbs(
    tool: str, query: str, args: dict[str, Any]
) -> None:
    """
    Strip status/stage injected by the model when the query ends with a conversational
    verb ('are registered', 'are raised', 'are found') but contains NO explicit status word.

    Example: 'How many Electrical BDM complaints are registered'
      => model sends status='Open'  (WRONG - user didn't ask for Open)
      => this function clears it

    Example: 'How many Open BDM complaints are registered'
      => explicit 'Open' present => status kept as-is
    """
    if tool not in ("BDM", "PPM", "SB", "ASSETS", "FA"):
        return
    q = query or ""
    if not _CONVERSATIONAL_VERBS_NOT_STATUS.search(q):
        return
    if _EXPLICIT_STATUS_WORDS.search(q):
        return

    # Check if the extracted status or stage is actually explicitly mentioned in the query
    status_val = args.get("status")
    if status_val and isinstance(status_val, str):
        if status_val.lower().strip() in q.lower():
            return
    stage_val = args.get("stage")
    if stage_val and isinstance(stage_val, str):
        if stage_val.lower().strip() in q.lower():
            return

    # No explicit status/stage found in query — strip them
    if args.get("status") is not None:
        logger.info(
            "🔧 %s: stripped implicit status=%r — query uses conversational verb, no explicit status word",
            tool, args["status"],
        )
        args.pop("status", None)
    # For FA/PPM: also strip implicitly-injected 'stage'
    if args.get("stage") is not None and tool in ("FA", "PPM"):
        logger.info(
            "🔧 %s: stripped implicit stage=%r — query uses conversational verb, no explicit status word",
            tool, args["stage"],
        )
        args.pop("stage", None)


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


def _fix_ppm_stages_from_query(tool: str, query: str, args: dict[str, Any]) -> None:
    if tool != "PPM":
        return
    q = (query or "").lower()
    
    stage_mapped = None
    if "technician assigned" in q:
        stage_mapped = "Technician Assigned"
    elif "standby" in q:
        stage_mapped = "Standby"
    elif "yet to be allocated" in q or "yet to allocated" in q:
        stage_mapped = "Staff Yet to be Allocated"
    elif "execution completed" in q:
        stage_mapped = "Execution Completed"
    elif "preliminary confirmed" in q:
        stage_mapped = "Preliminary Confirmed & Open"
        
    if stage_mapped:
        if args.get("stage") != stage_mapped:
            args["stage"] = stage_mapped
            logger.info("🔧 PPM: mapped stage -> %r based on query", stage_mapped)
        # Clear conflicting/redundant filters
        args.pop("keyword", None)
        if stage_mapped == "Execution Completed":
            args.pop("status", None)


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


def _fix_hyphen_spacing_from_query(query: str, args: dict[str, Any]) -> None:
    if not query:
        return
    q_lower = query.lower()
    for key, val in list(args.items()):
        if isinstance(val, str) and "-" in val:
            # Try collapsed (no spaces around hyphen)
            collapsed = re.sub(r'\s*-\s*', '-', val)
            # Try expanded (spaces around hyphen)
            expanded = re.sub(r'\s*-\s*', ' - ', val)
            
            # Match case-insensitively in the query
            if collapsed.lower() in q_lower and val.lower() != collapsed.lower():
                m = re.search(re.escape(collapsed), query, re.I)
                args[key] = m.group(0) if m else collapsed
                logger.info("🔧 Normalized %s spacing to match query: %r -> %r", key, val, args[key])
            elif expanded.lower() in q_lower and val.lower() != expanded.lower():
                m = re.search(re.escape(expanded), query, re.I)
                args[key] = m.group(0) if m else expanded
                logger.info("🔧 Normalized %s spacing to match query: %r -> %r", key, val, args[key])


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
    """Normalize priority to one of the two valid DB formats:
       With prefix:    'P1 Critical', 'P2 High', 'P3 Medium', 'P4 Low'
       Without prefix: 'Critical',    'High',    'Medium',    'Low'
    Returns the value as-is (title-cased) if unrecognised.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = re.sub(r"[\-\u2013\u2014]+", " ", s)  # dashes to spaces
    s = re.sub(r"\s+", " ", s).strip()
    low = s.lower()

    # ── Full P-prefix format ──────────────────────────────────────────
    if low == "p1 critical":  return "P1 Critical"
    if low == "p2 high":      return "P2 High"
    if low == "p3 medium":    return "P3 Medium"
    if low == "p4 low":       return "P4 Low"

    # ── Bare P-number only (model sends just "P3", "P2", etc.) ───────
    if low == "p1":  return "P1 Critical"
    if low == "p2":  return "P2 High"
    if low == "p3":  return "P3 Medium"
    if low == "p4":  return "P4 Low"

    # ── Short format (no P-prefix) ───────────────────────────────────
    if low == "critical":  return "Critical"
    if low == "high":      return "High"
    if low == "medium":    return "Medium"
    if low == "low":       return "Low"

    return s

def _fix_ppm_technician_assigned_tech(tool: str, query: str, args: dict[str, Any]) -> None:
    if tool not in ("PPM", "SB", "FA"):
        return
    tech_val = args.get("tech")
    stage_val = args.get("stage")
    if tech_val and isinstance(tech_val, str) and tech_val.strip().lower() == "technician":
        if (stage_val and "technician" in str(stage_val).lower()) or "technician assigned" in (query or "").lower():
            args.pop("tech", None)
            logger.info("🔧 %s: cleared tech='Technician' to prevent conflict with 'Technician Assigned' stage", tool)

__all__ = [name for name in dir() if not name.startswith('__') and name != 'logging' and name != 're' and name != 'Any' and name != 'logger']
