"""
Search context for keyword and field-filter queries (counts, summaries, UI banner).
"""
from __future__ import annotations

import json
import re
from typing import Any


def friendly_field_name(col: str) -> str:
    if not col:
        return col
    return re.sub(r"(?<!^)(?=[A-Z])", " ", col).strip()


FILTER_FIELD_LABELS: dict[str, str] = {
    # Assets
    "asset_type": "Asset Type",
    "equipment_name": "Equipment Name",
    "make": "Make",
    "model": "Model",
    "building": "Building Name",
    "division": "Division Name",
    "discipline": "Discipline Name",
    "locality": "Locality Name",
    "floor": "Floor Name",
    "spot_name": "Spot Name",
    "owner": "Owner",
    "trade_group": "Trade Group Name",
    "service_area": "Service Area",
    "status": "Status",
    "condition": "Condition",
    "priority": "Priority",
    "asset_tag_no": "Asset Tag No",
    "serial_no": "Serial No",
    "equipment_ref_no": "Equipment Ref No",
    "remarks": "Remarks",
    "drawing_no": "Drawing No",
    "asset_barcode": "Asset Barcode",
    # PPM
    "work_order": "Work Order",
    "equipment": "Equipment",
    "stage": "Stage",
    "frequency": "Frequency",
    "contract": "Contract",
    "tech": "Technician",
    # BDM
    "complaint_no": "Complaint No",
    "client_wo_no": "Client Work Order",
    "complaint_type": "Complaint Type",
    "complaint_header": "Complaint Header",
    "complaint_mode": "Complaint Mode",
    "complaint_nature": "Complaint Nature",
    "wo_type": "Work Order Type",
    "service_type": "Service Type",
    "complainer": "Complainer",
    "register_by": "Registered By",
    "analysis_tech": "Analysis Technician",
    "execution_tech": "Execution Technician",
    # FA
    "complaint_code": "Complaint Code",
    "x_complaint_no": "External Complaint No",
    "category": "Category",
    "category_sub": "Category Sub",
    "request_desc": "Request Description",
}


def filter_field_label(field_name: str) -> str:
    if not field_name:
        return field_name
    return FILTER_FIELD_LABELS.get(field_name) or friendly_field_name(field_name)


def _join_field_breakdown(field_match_counts: dict[str, int]) -> str:
    parts = [f"{friendly_field_name(k)} ({v})" for k, v in field_match_counts.items()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


def build_field_filter_explanation_sentence(
    *,
    total_records: int,
    filter_field: str,
    filter_value: str,
    entity: str = "assets",
) -> str:
    label = entity.strip() or "records"
    field_label = filter_field_label(filter_field)
    val = filter_value.strip()
    return (
        f"There are {total_records} {label} matching \"{val}\" in our records, "
        f"filtered by {field_label}."
    )


def build_match_explanation_sentence(
    *,
    total_records: int,
    keyword: str,
    field_match_counts: dict[str, int],
    entity: str = "assets",
) -> str:
    kw = keyword.strip()
    breakdown = _join_field_breakdown(field_match_counts)
    label = entity.strip() or "records"
    if breakdown:
        return (
            f"There are {total_records} {label} matching \"{kw}\" in our records, "
            f"primarily in {breakdown}."
        )
    return f"There are {total_records} {label} matching \"{kw}\" in our records."


def aggregate_field_match_counts(p_list: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in p_list or []:
        if not isinstance(row, dict):
            continue
        matched = row.get("_matched_fields") or []
        if isinstance(matched, str):
            try:
                matched = json.loads(matched)
            except (json.JSONDecodeError, TypeError):
                matched = []
        if not isinstance(matched, list):
            continue
        for field in matched:
            if field:
                counts[str(field)] = counts.get(str(field), 0) + 1
    return dict(sorted(counts.items(), key=lambda x: (-x[1], x[0])))


def build_search_context(
    *,
    p_list: list[Any],
    keyword_used: str | None = None,
    entity: str = "assets",
) -> dict[str, Any] | None:
    kw = (keyword_used or "").strip()
    if not kw:
        return None
    field_match_counts = aggregate_field_match_counts(p_list)
    total = len(p_list) if p_list else 0
    summary = build_match_explanation_sentence(
        total_records=total,
        keyword=kw,
        field_match_counts=field_match_counts,
        entity=entity,
    )
    return {
        "search_mode": "keyword",
        "keyword": kw,
        "total_records": total,
        "field_match_counts": field_match_counts,
        "field_match_counts_friendly": {
            friendly_field_name(k): v for k, v in field_match_counts.items()
        },
        "summary_line": summary,
    }


def build_field_filter_context(
    *,
    filter_field: str,
    filter_value: str,
    total_records: int = 0,
    entity: str = "assets",
) -> dict[str, Any]:
    summary = build_field_filter_explanation_sentence(
        total_records=total_records,
        filter_field=filter_field,
        filter_value=filter_value,
        entity=entity,
    )
    return {
        "search_mode": "field_filter",
        "filter_field": filter_field,
        "filter_value": filter_value,
        "field_label": filter_field_label(filter_field),
        "total_records": total_records,
        "summary_line": summary,
    }


def extract_from_tool_response(
    parsed: dict[str, Any],
    *,
    keyword_used: str | None = None,
    entity: str = "assets",
) -> dict[str, Any] | None:
    if not isinstance(parsed, dict):
        return None

    kw = (keyword_used or "").strip()
    if not kw:
        fb = parsed.get("keyword_fallback")
        if isinstance(fb, dict):
            kw = (fb.get("keyword") or "").strip()

    if kw:
        return build_search_context(
            p_list=parsed.get("p_list") or [],
            keyword_used=kw,
            entity=entity,
        )

    ff = parsed.get("field_filter")
    if isinstance(ff, dict) and ff.get("field") and ff.get("value"):
        return build_field_filter_context(
            filter_field=str(ff["field"]),
            filter_value=str(ff["value"]),
            total_records=0,
            entity=entity,
        )
    return None


def search_context_prompt_block(search_context: dict[str, Any] | None) -> str:
    if not search_context or not search_context.get("summary_line"):
        return ""
    return (
        "\n\nMATCH CONTEXT — weave this into your reply as one flowing sentence "
        "(do not add a second repetitive sentence):\n"
        f"{search_context['summary_line']}\n"
    )


def format_keyword_count_reply(
    search_context: dict[str, Any],
    entity: str = "assets",
) -> str:
    """Polished count sentence for keyword or field-filter search."""
    if search_context.get("search_mode") == "field_filter":
        return build_field_filter_explanation_sentence(
            total_records=int(search_context.get("total_records") or 0),
            filter_field=str(search_context.get("filter_field") or ""),
            filter_value=str(search_context.get("filter_value") or ""),
            entity=entity,
        )
    return build_match_explanation_sentence(
        total_records=int(search_context.get("total_records") or 0),
        keyword=str(search_context.get("keyword") or ""),
        field_match_counts=search_context.get("field_match_counts") or {},
        entity=entity,
    )


def append_match_explanation(
    text: str,
    search_context: dict[str, Any] | None,
    *,
    use_polished_sentence: bool = False,
    entity: str = "assets",
) -> str:
    if not search_context:
        return text
    if use_polished_sentence:
        return format_keyword_count_reply(search_context, entity=entity)
    line = (search_context.get("summary_line") or "").strip()
    if not line:
        return text
    base = (text or "").strip()
    if line.lower() in base.lower():
        return base
    return f"{base}\n\n{line}" if base else line
