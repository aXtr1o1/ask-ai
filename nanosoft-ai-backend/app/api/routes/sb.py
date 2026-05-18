from fastapi import APIRouter, HTTPException
import logging
import json
 
from app.api.models.schemas import SBRequest
from app.api.database.postgres_client import get_pool
 
router_sb = APIRouter()
 
logger_sb = logging.getLogger("sb_route")
logger_sb.setLevel(logging.INFO)
ch2 = logging.StreamHandler()
ch2.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger_sb.handlers:
    logger_sb.addHandler(ch2)
 
 
def format_response_sb(data):
    if isinstance(data, dict):
        p_list  = data.get("p_list", [])
        p_count = data.get("p_count", 0)
        logger_sb.info("📊 SB format_response | p_list_length=%s | p_count=%s", len(p_list), p_count)
        return {"p_list": p_list, "p_count": p_count}
    safe_list = data if isinstance(data, list) else []
    return {"p_list": safe_list, "p_count": len(safe_list)}
 
 
@router_sb.post("/get-sb")
def get_sb(req: SBRequest):
    logger_sb.info(
        "🗓️ [GET-SB] Incoming | user_name=%s | limit=%s | offset=%s",
        req.user_name, req.limit, req.offset
    )
 
    # ── AGGREGATE PATH ──────────────────────────────────────────────────────
    if getattr(req, "is_aggregate", False) and req.group_by_columns:
        logger_sb.info("📊 [GET-SB] AGGREGATE MODE → calling sp_sb_aggregate")
        try:
            conn   = get_pool()
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
 
    # ── NORMAL PATH ─────────────────────────────────────────────────────────
    logger_sb.info("[GET-SB] Calling sp_sb_query")
    try:
        conn   = get_pool()
        cursor = conn.cursor()
 
        cursor.callproc("sp_sb_query", [
            req.user_name,
            req.user_id,
            req.work_order,
            req.stage,
            req.division,
            req.discipline,
            req.locality,
            req.building,
            req.floor,
            req.spot_name,
            req.contract,
            req.frequency,
            req.service_type,
            req.tech,
            req.is_withdraw,
            req.is_reschedule,
            req.is_rework,
            req.is_active,
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
 
        formatted = format_response_sb(raw)
        p_list = formatted.get("p_list", [])

        # Fallback interceptor: if 0 records found and locality was specified but spot_name was not,
        # retry the query mapping locality to spot_name.
        if not p_list and req.locality and not req.spot_name:
            logger_sb.info("🔄 0 records found with locality='%s' in SB. Retrying query by mapping locality to spot_name...", req.locality)
            cursor = conn.cursor()
            cursor.callproc("sp_sb_query", [
                req.user_name,
                req.user_id,
                req.work_order,
                req.stage,
                req.division,
                req.discipline,
                None,  # p_locality cleared
                req.building,
                req.floor,
                req.locality,  # p_spot_name mapped
                req.contract,
                req.frequency,
                req.service_type,
                req.tech,
                req.is_withdraw,
                req.is_reschedule,
                req.is_rework,
                req.is_active,
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
            formatted = format_response_sb(raw)
            p_list = formatted.get("p_list", [])

        logger_sb.info("[GET-SB] Fetched | count=%s", formatted["p_count"])
        return formatted
 
    except Exception as e:
        logger_sb.error("[GET-SB] RPC failed | error=%s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))