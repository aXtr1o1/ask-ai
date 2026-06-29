from fastapi import APIRouter, HTTPException
import logging
import json

from app.api.models.schemas import FARequest
from app.api.database.postgres_client import get_pool
from .query_search_fallback import (
    FA_TEXT_FILTER_FIELDS,
    apply_limit_offset,
    enrich_with_search_fallback,
    merge_format_response,
    call_sp_with_multi_values,
)
from app.services.tool_payload_validator import validate_aggregate_request

router = APIRouter()

logger = logging.getLogger("fa_route")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


def format_response(data):
    out = merge_format_response(data)
    logger.info(
        "📊 FA format_response | p_list_length=%s | p_count=%s",
        len(out.get("p_list", [])),
        out.get("p_count", 0),
    )
    return out


def _call_sp_fa_query_single(req: FARequest) -> dict:
    """Single-value SP call — always receives plain string fields."""
    conn = get_pool()
    cursor = conn.cursor()
    cursor.callproc("sp_fa_query", [
        req.user_name,
        req.user_id,
        req.complaint_no,
        req.complaint_code,
        req.x_complaint_no,
        req.priority,
        req.stage,
        req.category,
        req.category_sub,
        req.division,
        req.locality,
        req.locality_code,
        req.building,
        req.floor,
        req.spot_name,
        req.contract,
        req.tech,
        req.frequency,
        req.request_desc,
        req.is_withdraw,
        req.is_rework,
        req.is_bms,
        req.is_active,
        req.is_draft,
        req.keyword,
        req.date_from,
        req.date_to,
        req.comp_from,
        req.comp_to,
        req.limit,
        req.offset,
    ])
    row = cursor.fetchone()
    cursor.close()
    raw = row[0] if row else {}
    if isinstance(raw, str):
        raw = json.loads(raw)
    return format_response(raw)


def _call_sp_fa_query(req: FARequest) -> dict:
    """Multi-value-aware wrapper — fans out list fields across SP calls."""
    return call_sp_with_multi_values(
        req,
        _call_sp_fa_query_single,
        id_fields=("id", "RMComplaintNo"),
    )

from collections import Counter
from app.services.payload_constants import TOOL_GROUP_BY_COLUMNS
FA_SP_AGGREGATE_GROUP_COLUMNS = set(TOOL_GROUP_BY_COLUMNS.get("FA", []))

def _fa_requires_local_aggregate(req: FARequest) -> bool:
    group_cols = set(req.group_by_columns or [])
    if group_cols - FA_SP_AGGREGATE_GROUP_COLUMNS:
        return True
    return False

def _format_local_fa_aggregate(rows: list[dict], group_by_columns: list[str]) -> dict:
    counts: Counter[tuple] = Counter()
    for row in rows:
        key = tuple(row.get(col) for col in group_by_columns)
        counts[key] += 1

    p_list = []
    for key, count in counts.items():
        item = {col: key[idx] for idx, col in enumerate(group_by_columns)}
        item["result"] = count
        p_list.append(item)

    p_list.sort(
        key=lambda item: (
            -int(item.get("result") or 0),
            tuple("" if item.get(col) is None else str(item.get(col)) for col in group_by_columns),
        )
    )
    return {"p_list": p_list, "p_count": len(p_list), "local_aggregate": True}

def _call_local_fa_aggregate(req: FARequest) -> dict:
    query_req = req.model_copy(update={
        "is_aggregate": False,
        "group_by_columns": None,
        "aggregate_function": None,
    })
    formatted = _call_sp_fa_query(query_req)
    rows = formatted.get("p_list") or []
    return _format_local_fa_aggregate(rows, req.group_by_columns or [])


@router.post("/get-fa")
def get_fa(req: FARequest):
    logger.info(
        "📋 [GET-FA] Incoming | user_name=%s | limit=%s | offset=%s",
        req.user_name, req.limit, req.offset
    )

    if getattr(req, "is_aggregate", False):
        try:
            validate_aggregate_request(True, req.group_by_columns)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        if _fa_requires_local_aggregate(req):
            logger.info("📊 [GET-FA] Local Aggregation Fallback triggered")
            return _call_local_fa_aggregate(req)
            
        logger.info("📊 [GET-FA] AGGREGATE MODE → calling sp_fa_aggregate")
        try:
            conn = get_pool()
            cursor = conn.cursor()
            group_by_str = ",".join(req.group_by_columns) if req.group_by_columns else None
            agg_function = req.aggregate_function or "COUNT"
            logger.info("📊 [GET-FA] group_by=%s | function=%s", group_by_str, agg_function)
            cursor.callproc("sp_fa_aggregate", [
                req.user_name,
                req.user_id,
                req.division,
                req.building,
                req.floor,
                req.locality,
                req.locality_code,
                req.priority,
                req.stage,
                req.category,
                req.frequency,
                req.date_from,
                req.date_to,
                group_by_str,
                agg_function,
            ])
            row = cursor.fetchone()
            cursor.close()
            raw = row[0] if row else {}
            if isinstance(raw, str):
                raw = json.loads(raw)
            formatted = format_response(raw)
            logger.info("✅ [GET-FA] Aggregate result | count=%s", formatted["p_count"])
            return formatted
        except Exception as e:
            logger.error("[GET-FA] Aggregate failed | error=%s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    logger.info("[GET-FA] Calling sp_fa_query")
    try:
        formatted = enrich_with_search_fallback(
            req,
            _call_sp_fa_query(req),
            text_filter_fields=FA_TEXT_FILTER_FIELDS,
            call_query=_call_sp_fa_query,
            log_prefix="[GET-FA]",
            logger=logger,
            sp_label="sp_fa_query",
        )
        formatted = apply_limit_offset(formatted, req)
        logger.info("[GET-FA] Fetched | count=%s", formatted["p_count"])
        return formatted

    except Exception as e:
        logger.error("[GET-FA] RPC failed | error=%s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
