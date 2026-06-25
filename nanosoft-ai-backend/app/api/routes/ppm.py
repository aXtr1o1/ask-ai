"""
PPM Route (Planned Preventive Maintenance)
"""
from fastapi import APIRouter, HTTPException
import logging
import json

from app.api.models.schemas import PPMRequest
from app.api.database.postgres_client import get_pool
from .query_search_fallback import (
    PPM_TEXT_FILTER_FIELDS,
    apply_limit_offset,
    enrich_with_search_fallback,
    merge_format_response,
)
from app.services.tool_payload_validator import validate_aggregate_request

router = APIRouter()

logger = logging.getLogger("ppm_route")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


def format_response(data):
    out = merge_format_response(data)
    logger.info(
        "📊 format_response | p_list_length=%s | p_count=%s",
        len(out.get("p_list", [])),
        out.get("p_count", 0),
    )
    return out


def _call_sp_ppm_query(req: PPMRequest) -> dict:
    conn = get_pool()
    cursor = conn.cursor()
    cursor.callproc("sp_ppm_query", [
        req.user_name,
        req.user_id,
        req.work_order,
        req.asset_tag_no,
        req.equipment_ref_no,
        req.status,
        req.stage,
        req.frequency,
        req.division,
        req.discipline,
        req.locality,
        req.locality_code,
        req.building,
        req.floor,
        req.spot_name,
        req.contract,
        req.tech,
        req.equipment,
        req.keyword,
        req.date_from,
        req.date_to,
        req.comp_from,
        req.comp_to,
        req.sla_min,
        req.sla_max,
    ])
    row = cursor.fetchone()
    cursor.close()
    raw = row[0] if row else {}
    if isinstance(raw, str):
        raw = json.loads(raw)
    return format_response(raw)

from collections import Counter
from app.services.payload_constants import TOOL_GROUP_BY_COLUMNS
PPM_SP_AGGREGATE_GROUP_COLUMNS = set(TOOL_GROUP_BY_COLUMNS.get("PPM", []))

def _ppm_requires_local_aggregate(req: PPMRequest) -> bool:
    group_cols = set(req.group_by_columns or [])
    if group_cols - PPM_SP_AGGREGATE_GROUP_COLUMNS:
        return True
    return False

def _format_local_ppm_aggregate(rows: list[dict], group_by_columns: list[str]) -> dict:
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

def _call_local_ppm_aggregate(req: PPMRequest) -> dict:
    query_req = req.model_copy(update={
        "is_aggregate": False,
        "group_by_columns": None,
        "aggregate_function": None,
    })
    formatted = _call_sp_ppm_query(query_req)
    rows = formatted.get("p_list") or []
    return _format_local_ppm_aggregate(rows, req.group_by_columns or [])

@router.post("/get-ppm")
def get_ppm(req: PPMRequest):
    logger.info(
        "[GET-PPM] Incoming | user_name=%s | status=%s | limit=%s | offset=%s",
        req.user_name, req.status, req.limit, req.offset
    )
    logger.debug("[GET-PPM] Full payload: %s", req.model_dump())

    if getattr(req, "is_aggregate", False):
        try:
            validate_aggregate_request(True, req.group_by_columns)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        if _ppm_requires_local_aggregate(req):
            logger.info("📊 [GET-PPM] Local Aggregation Fallback triggered for grouping columns")
            return _call_local_ppm_aggregate(req)
            
        logger.info("📊 [GET-PPM] AGGREGATE MODE detected → calling sp_ppm_aggregate")
        try:
            conn = get_pool()
            cursor = conn.cursor()
            group_by_str = ",".join(req.group_by_columns) if req.group_by_columns else None
            agg_function = req.aggregate_function or "COUNT"
            logger.info("📊 [GET-PPM] group_by=%s | function=%s", group_by_str, agg_function)
            cursor.callproc("sp_ppm_aggregate", [
                req.user_name,
                req.user_id,
                req.division,
                req.discipline,
                req.building,
                req.floor,
                req.locality,
                req.locality_code,
                req.status,
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
            logger.info("✅ [GET-PPM] Aggregate result | count=%s", formatted["p_count"])
            return formatted
        except Exception as e:
            err_msg = str(e)
            logger.error("[GET-PPM] Aggregate RPC failed | error=%s", err_msg, exc_info=True)
            raise HTTPException(status_code=500, detail=err_msg)

    logger.info("[GET-PPM] Calling sp_ppm_query")
    try:
        formatted = enrich_with_search_fallback(
            req,
            _call_sp_ppm_query(req),
            text_filter_fields=PPM_TEXT_FILTER_FIELDS,
            call_query=_call_sp_ppm_query,
            log_prefix="[GET-PPM]",
            logger=logger,
            sp_label="sp_ppm_query",
        )
        formatted = apply_limit_offset(formatted, req)
        p_list = formatted.get("p_list", [])

        if p_list:
            fields = list(p_list[0].keys()) if isinstance(p_list[0], dict) else []
            sample = [r.get("WorkOrder") or r.get("id") or str(r)[:50] for r in p_list[:3]]
            logger.info(
                "[GET-PPM] Fetched | count=%s | fields=%s | sample_ids=%s",
                formatted["p_count"], fields[:8], sample,
            )
        else:
            logger.info("[GET-PPM] Success | count=0")

        return formatted

    except Exception as e:
        err_msg = str(e)
        if hasattr(e, "args") and e.args and isinstance(e.args[0], dict):
            err_dict = e.args[0]
            logger.error(
                "[GET-PPM] RPC failed | code=%s | message=%s | hint=%s",
                err_dict.get("code", "?"),
                err_dict.get("message", err_msg),
                err_dict.get("hint", ""),
                exc_info=True,
            )
        else:
            logger.error("[GET-PPM] RPC failed | error=%s", err_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=err_msg)
