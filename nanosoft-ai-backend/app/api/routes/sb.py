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


@router_sb.post("/get-sb")
def get_sb(req: SBRequest):
    logger_sb.info(
        "🗓️ [GET-SB] Incoming | user_name=%s | limit=%s | offset=%s",
        req.user_name, req.limit, req.offset
    )

    if getattr(req, "is_aggregate", False) and req.group_by_columns:
        logger_sb.info("📊 [GET-SB] AGGREGATE MODE → calling sp_sb_aggregate")
        try:
            conn = get_pool()
            cursor = conn.cursor()
            group_by_str = ",".join(req.group_by_columns)
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
