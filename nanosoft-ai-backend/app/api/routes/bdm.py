"""
BDM Route (Breakdown Maintenance / Complaints)
"""
from fastapi import APIRouter, HTTPException
import logging
import json
from collections import Counter

from app.api.models.schemas import BDMRequest
from app.api.database.postgres_client import get_pool
from .query_search_fallback import (
    BDM_TEXT_FILTER_FIELDS,
    apply_limit_offset,
    enrich_with_search_fallback,
    merge_format_response,
)
from app.services.tool_payload_validator import validate_aggregate_request

router = APIRouter()

logger = logging.getLogger("bdm_route")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)

BDM_SP_AGGREGATE_GROUP_COLUMNS = {
    "DivisionName",
    "DisciplineName",
    "BuildingName",
    "FloorName",
    "LocalityName",
    "WoStatus",
    "PriorityName",
    "StageName",
    "ComplaintTypeName",
    "ComplaintModeName",
    "ServiceTypeName",
    "SpotName",
    "ContractName",
}

BDM_SP_AGGREGATE_FILTER_FIELDS = {
    "division",
    "discipline",
    "building",
    "floor",
    "locality",
    "status",
    "priority",
    "stage",
    "date_from",
    "date_to",
}


def format_response(data):
    out = merge_format_response(data)
    logger.info(
        "📊 format_response | p_list_length=%s | p_count=%s",
        len(out.get("p_list", [])),
        out.get("p_count", 0),
    )
    return out


def _call_sp_bdm_query(req: BDMRequest) -> dict:
    conn = get_pool()
    cursor = conn.cursor()
    cursor.callproc("sp_bdm_query", [
        req.user_name,
        req.user_id,
        req.complaint_no,
        req.asset_tag_no,
        req.asset_barcode,
        req.client_wo_no,
        req.status,
        req.priority,
        req.stage,
        req.complaint_type,
        req.complaint_header,
        req.complaint_mode,
        req.complaint_nature,
        req.wo_type,
        req.service_type,
        req.division,
        req.discipline,
        req.locality,
        req.building,
        req.floor,
        req.spot_name,
        req.contract,
        req.complainer,
        req.register_by,
        req.analysis_tech,
        req.execution_tech,
        req.keyword,
        req.date_from,
        req.date_to,
        req.completed_from,
        req.completed_to,
    ])
    row = cursor.fetchone()
    cursor.close()
    raw = row[0] if row else {}
    if isinstance(raw, str):
        raw = json.loads(raw)
    return format_response(raw)


def _bdm_requires_local_aggregate(req: BDMRequest) -> bool:
    group_cols = set(req.group_by_columns or [])
    if group_cols - BDM_SP_AGGREGATE_GROUP_COLUMNS:
        return True
    for field, value in req.model_dump().items():
        if field in BDM_SP_AGGREGATE_FILTER_FIELDS:
            continue
        if field in {"user_id", "user_name", "is_aggregate", "group_by_columns", "aggregate_function", "offset"}:
            continue
        if value is not None:
            return True
    return False


def _format_local_bdm_aggregate(rows: list[dict], group_by_columns: list[str]) -> dict:
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


def _call_local_bdm_aggregate(req: BDMRequest) -> dict:
    query_req = req.model_copy(update={
        "is_aggregate": False,
        "group_by_columns": None,
        "aggregate_function": None,
    })
    formatted = _call_sp_bdm_query(query_req)
    rows = formatted.get("p_list") or []
    return _format_local_bdm_aggregate(rows, req.group_by_columns or [])


@router.post("/get-bdm")
def get_bdm(req: BDMRequest):
    logger.info(
        "[GET-BDM] Incoming | user_name=%s | status=%s | limit=%s | offset=%s",
        req.user_name, req.status, req.limit, req.offset
    )
    logger.debug("[GET-BDM] Full payload: %s", req.model_dump())

    if getattr(req, "is_aggregate", False):
        try:
            validate_aggregate_request(True, req.group_by_columns)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        logger.info("📊 [GET-BDM] AGGREGATE MODE detected → calling sp_bdm_aggregate")
        if _bdm_requires_local_aggregate(req):
            logger.info(
                "[GET-BDM] Local aggregate fallback | group_by=%s",
                req.group_by_columns,
            )
            try:
                formatted = _call_local_bdm_aggregate(req)
                logger.info("[GET-BDM] Local aggregate result | count=%s", formatted["p_count"])
                return formatted
            except Exception as e:
                err_msg = str(e)
                logger.error("[GET-BDM] Local aggregate failed | error=%s", err_msg, exc_info=True)
                raise HTTPException(status_code=500, detail=err_msg)
        try:
            conn = get_pool()
            cursor = conn.cursor()
            group_by_str = ",".join(req.group_by_columns) if req.group_by_columns else None
            agg_function = req.aggregate_function or "COUNT"
            logger.info("📊 [GET-BDM] group_by=%s | function=%s", group_by_str, agg_function)
            cursor.callproc("sp_bdm_aggregate", [
                req.user_name,
                req.user_id,
                req.division,
                req.discipline,
                req.building,
                req.floor,
                req.locality,
                req.status,
                req.priority,
                req.stage,
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
            logger.info("✅ [GET-BDM] Aggregate result | count=%s", formatted["p_count"])
            return formatted
        except Exception as e:
            err_msg = str(e)
            logger.error("[GET-BDM] Aggregate RPC failed | error=%s", err_msg, exc_info=True)
            raise HTTPException(status_code=500, detail=err_msg)

    logger.info("[GET-BDM] Calling sp_bdm_query")
    try:
        formatted = enrich_with_search_fallback(
            req,
            _call_sp_bdm_query(req),
            text_filter_fields=BDM_TEXT_FILTER_FIELDS,
            call_query=_call_sp_bdm_query,
            log_prefix="[GET-BDM]",
            logger=logger,
            sp_label="sp_bdm_query",
        )
        formatted = apply_limit_offset(formatted, req)
        p_list = formatted.get("p_list", [])

        if p_list:
            fields = list(p_list[0].keys()) if isinstance(p_list[0], dict) else []
            sample = [r.get("ComplaintNo") or r.get("id") or str(r)[:50] for r in p_list[:3]]
            logger.info(
                "[GET-BDM] Fetched | count=%s | fields=%s | sample_ids=%s",
                formatted["p_count"], fields[:8], sample,
            )
        else:
            logger.info("[GET-BDM] Success | count=0")

        return formatted

    except Exception as e:
        err_msg = str(e)
        if hasattr(e, "args") and e.args and isinstance(e.args[0], dict):
            err_dict = e.args[0]
            logger.error(
                "[GET-BDM] RPC failed | code=%s | message=%s | hint=%s",
                err_dict.get("code", "?"),
                err_dict.get("message", err_msg),
                err_dict.get("hint", ""),
                exc_info=True,
            )
        else:
            logger.error("[GET-BDM] RPC failed | error=%s", err_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=err_msg)
