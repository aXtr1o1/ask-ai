from fastapi import APIRouter, HTTPException
import logging
import json

from app.api.models.schemas import SBRequest
from app.api.database.postgres_client import get_pool
from .query_search_fallback import (
    SB_TEXT_FILTER_FIELDS,
    apply_limit_offset,
    enrich_with_search_fallback,
    merge_format_response,
)
from app.services.tool_payload_validator import validate_aggregate_request

router_sb = APIRouter()

logger_sb = logging.getLogger("sb_route")
logger_sb.setLevel(logging.INFO)
ch2 = logging.StreamHandler()
ch2.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger_sb.handlers:
    logger_sb.addHandler(ch2)


def format_response_sb(data):
    out = merge_format_response(data)
    logger_sb.info(
        "📊 SB format_response | p_list_length=%s | p_count=%s",
        len(out.get("p_list", [])),
        out.get("p_count", 0),
    )
    return out


def _call_sp_sb_query(req: SBRequest) -> dict:
    conn = get_pool()
    cursor = conn.cursor()
    cursor.callproc("sp_sb_query", [
        req.user_name,
        req.user_id,
        req.work_order,
        req.stage,
        req.frequency,
        req.service_type,
        req.division,
        req.discipline,
        req.locality,
        req.locality_code,
        req.building,
        req.floor,
        req.spot_name,
        req.contract,
        req.tech,
        req.is_withdraw,
        req.is_reschedule,
        req.is_rework,
        req.is_active,
        req.is_draft,
        req.keyword,
        req.date_from,
        req.date_to,
        req.comp_from,
        req.comp_to,
        req.sla_min,
        req.sla_max,
        req.limit,
        req.offset,
    ])
    row = cursor.fetchone()
    cursor.close()
    raw = row[0] if row else {}
    if isinstance(raw, str):
        raw = json.loads(raw)
    return format_response_sb(raw)

from collections import Counter
from app.services.payload_constants import TOOL_GROUP_BY_COLUMNS
SB_SP_AGGREGATE_GROUP_COLUMNS = set(TOOL_GROUP_BY_COLUMNS.get("SB", []))

def _sb_requires_local_aggregate(req: SBRequest) -> bool:
    group_cols = set(req.group_by_columns or [])
    if group_cols - SB_SP_AGGREGATE_GROUP_COLUMNS:
        return True
    return False

def _format_local_sb_aggregate(rows: list[dict], group_by_columns: list[str]) -> dict:
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

def _call_local_sb_aggregate(req: SBRequest) -> dict:
    query_req = req.model_copy(update={
        "is_aggregate": False,
        "group_by_columns": None,
        "aggregate_function": None,
    })
    formatted = _call_sp_sb_query(query_req)
    rows = formatted.get("p_list") or []
    return _format_local_sb_aggregate(rows, req.group_by_columns or [])


@router_sb.post("/get-sb")
def get_sb(req: SBRequest):
    logger_sb.info(
        "🗓️ [GET-SB] Incoming | user_name=%s | limit=%s | offset=%s",
        req.user_name, req.limit, req.offset
    )

    if getattr(req, "is_aggregate", False):
        try:
            validate_aggregate_request(True, req.group_by_columns)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        if _sb_requires_local_aggregate(req):
            logger_sb.info("📊 [GET-SB] Local Aggregation Fallback triggered")
            return _call_local_sb_aggregate(req)
            
        logger_sb.info("📊 [GET-SB] AGGREGATE MODE → calling sp_sb_aggregate")
        try:
            conn = get_pool()
            cursor = conn.cursor()
            group_by_str = ",".join(req.group_by_columns) if req.group_by_columns else None
            agg_function = req.aggregate_function or "COUNT"
            logger_sb.info("📊 [GET-SB] group_by=%s | function=%s", group_by_str, agg_function)
            cursor.callproc("sp_sb_aggregate", [
                req.user_name,
                req.user_id,
                req.division,
                req.discipline,
                req.building,
                req.floor,
                req.locality,
                req.locality_code,
                req.stage,
                req.frequency,
                req.service_type,
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
            formatted = format_response_sb(raw)
            logger_sb.info("✅ [GET-SB] Aggregate result | count=%s", formatted["p_count"])
            return formatted
        except Exception as e:
            logger_sb.error("[GET-SB] Aggregate failed | error=%s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    logger_sb.info("[GET-SB] Calling sp_sb_query")
    try:
        formatted = enrich_with_search_fallback(
            req,
            _call_sp_sb_query(req),
            text_filter_fields=SB_TEXT_FILTER_FIELDS,
            call_query=_call_sp_sb_query,
            log_prefix="[GET-SB]",
            logger=logger_sb,
            sp_label="sp_sb_query",
        )
        formatted = apply_limit_offset(formatted, req)
        logger_sb.info("[GET-SB] Fetched | count=%s", formatted["p_count"])
        return formatted

    except Exception as e:
        logger_sb.error("[GET-SB] RPC failed | error=%s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
