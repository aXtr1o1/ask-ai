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
)

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


def _call_sp_fa_query(req: FARequest) -> dict:
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


@router.post("/get-fa")
def get_fa(req: FARequest):
    logger.info(
        "📋 [GET-FA] Incoming | user_name=%s | limit=%s | offset=%s",
        req.user_name, req.limit, req.offset
    )

    if getattr(req, "is_aggregate", False):
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
