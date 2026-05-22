"""Empty-result keyword retry and field_filter metadata for all query routes."""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

# Text filter fields per module (first match wins for retry / field_filter metadata).
ASSET_TEXT_FILTER_FIELDS = (
    "asset_type", "equipment_name", "make", "model", "building", "division",
    "discipline", "locality", "floor", "spot_name", "owner", "trade_group",
    "service_area", "status", "condition", "priority", "asset_tag_no", "serial_no",
    "equipment_ref_no", "remarks", "drawing_no", "asset_barcode",
)
PPM_TEXT_FILTER_FIELDS = (
    "work_order", "asset_tag_no", "equipment_ref_no", "status", "stage", "frequency",
    "division", "discipline", "locality", "building", "floor", "spot_name",
    "equipment", "contract", "tech",
)
BDM_TEXT_FILTER_FIELDS = (
    "complaint_no", "asset_tag_no", "asset_barcode", "client_wo_no", "status",
    "priority", "stage", "complaint_type", "complaint_header", "complaint_mode",
    "complaint_nature", "wo_type", "service_type", "division", "discipline",
    "locality", "building", "floor", "spot_name", "contract", "complainer",
    "register_by", "analysis_tech", "execution_tech",
)
FA_TEXT_FILTER_FIELDS = (
    "complaint_no", "complaint_code", "x_complaint_no", "priority", "stage",
    "category", "category_sub", "division", "locality", "building", "floor",
    "spot_name", "contract", "tech", "frequency", "request_desc",
)
SB_TEXT_FILTER_FIELDS = (
    "work_order", "stage", "frequency", "service_type", "division", "discipline",
    "locality", "building", "floor", "spot_name", "contract", "tech",
)


def is_empty_query_result(data: dict[str, Any]) -> bool:
    p_list = data.get("p_list") or []
    if not p_list:
        return True
    first = p_list[0]
    if isinstance(first, dict):
        for key in ("total_count", "total_count_over", "full_count", "overall_count"):
            val = first.get(key)
            if isinstance(val, (int, float)):
                return int(val) == 0
    return int(data.get("p_count") or 0) == 0


def pick_text_filter(req: Any, fields: tuple[str, ...]) -> tuple[str, str] | None:
    """(value, field_name) for first non-empty text filter when keyword is unset."""
    if getattr(req, "keyword", None):
        return None
    for field in fields:
        val = getattr(req, field, None)
        if val is not None and str(val).strip():
            return str(val).strip(), field
    return None


def merge_format_response(data: dict | list) -> dict[str, Any]:
    """Standard p_list / p_count shape plus optional SP metadata."""
    if isinstance(data, dict):
        out: dict[str, Any] = {
            "p_list": data.get("p_list", []),
            "p_count": data.get("p_count", 0),
        }
        for key in ("keyword_search", "keyword_fallback", "field_filter"):
            if data.get(key) is not None:
                out[key] = data[key]
        return out
    safe_list = data if isinstance(data, list) else []
    return {"p_list": safe_list, "p_count": len(safe_list)}


def apply_limit_offset(formatted: dict, req: Any) -> dict:
    p_list = formatted.get("p_list", [])
    sp_count = formatted.get("p_count", len(p_list))
    offset = getattr(req, "offset", 0) or 0
    limit = getattr(req, "limit", None)
    if offset:
        p_list = p_list[offset:]
    if limit is not None:
        p_list = p_list[:limit]
    formatted["p_list"] = p_list
    formatted["p_count"] = sp_count if sp_count > len(p_list) else len(p_list)
    return formatted


def enrich_with_search_fallback(
    req: Any,
    formatted: dict[str, Any],
    *,
    text_filter_fields: tuple[str, ...],
    call_query: Callable[[Any], dict[str, Any]],
    log_prefix: str,
    logger: logging.Logger,
    sp_label: str,
) -> dict[str, Any]:
    """
    - Empty + text filter → retry with keyword (log 2nd payload).
    - Success + text filter (no keyword) → attach field_filter metadata.
    """
    if is_empty_query_result(formatted):
        fallback = pick_text_filter(req, text_filter_fields)
        if fallback:
            keyword_val, from_field = fallback
            logger.info(
                "%s Empty result — retrying as keyword | from_field=%s | keyword=%s",
                log_prefix,
                from_field,
                keyword_val,
            )
            retry_req = req.model_copy(update={from_field: None, "keyword": keyword_val})
            logger.info(
                "%s Keyword fallback — 2nd %s payload:\n%s",
                log_prefix,
                sp_label,
                json.dumps(retry_req.model_dump(exclude_none=True), indent=2, default=str),
            )
            retry_formatted = call_query(retry_req)
            if not is_empty_query_result(retry_formatted):
                retry_formatted["keyword_fallback"] = {
                    "from_field": from_field,
                    "keyword": keyword_val,
                }
                return retry_formatted
            logger.info(
                "%s Keyword fallback still empty | keyword=%s",
                log_prefix,
                keyword_val,
            )
    elif not getattr(req, "keyword", None):
        applied = pick_text_filter(req, text_filter_fields)
        if applied:
            filter_val, filter_field = applied
            formatted["field_filter"] = {"field": filter_field, "value": filter_val}
            logger.info(
                "%s Field filter applied | field=%s | value=%s",
                log_prefix,
                filter_field,
                filter_val,
            )
    return formatted
