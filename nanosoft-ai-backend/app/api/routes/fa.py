from fastapi import APIRouter, HTTPException
import logging
import json
 
from app.api.models.schemas import FARequest
from app.api.database.postgres_client import get_pool
 
router = APIRouter()
 
logger = logging.getLogger("fa_route")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)
 
 
def format_response(data):
    if isinstance(data, dict):
        p_list  = data.get("p_list", [])
        p_count = data.get("p_count", 0)
        logger.info("📊 FA format_response | p_list_length=%s | p_count=%s", len(p_list), p_count)
        return {"p_list": p_list, "p_count": p_count}
    safe_list = data if isinstance(data, list) else []
    return {"p_list": safe_list, "p_count": len(safe_list)}
 
 
@router.post("/get-fa")
def get_fa(req: FARequest):
    logger.info(
        "📋 [GET-FA] Incoming | user_name=%s | limit=%s | offset=%s",
        req.user_name, req.limit, req.offset
    )
 
    # ── AGGREGATE PATH ──────────────────────────────────────────────────────
    if getattr(req, "is_aggregate", False) and req.group_by_columns:
        logger.info("📊 [GET-FA] AGGREGATE MODE → calling sp_fa_aggregate")
        try:
            conn   = get_pool()
            cursor = conn.cursor()
 
            group_by_str = ",".join(req.group_by_columns)
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
 
    # ── NORMAL PATH ─────────────────────────────────────────────────────────
    logger.info("[GET-FA] Calling sp_fa_query")
    try:
        conn   = get_pool()
        cursor = conn.cursor()
 
        cursor.callproc("sp_fa_query", [
            req.user_name,
            req.user_id,
            req.complaint_no,
            req.complaint_code,       # NEW
            req.x_complaint_no,       # NEW
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
            req.is_bms,               # NEW
            req.is_active,
            req.is_draft,             # NEW
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
 
        formatted = format_response(raw)
        p_list = formatted.get("p_list", [])

        # Fallback interceptor: if 0 records found and locality was specified but spot_name was not,
        # retry the query mapping locality to spot_name.
        if not p_list and req.locality and not req.spot_name:
            logger.info("🔄 0 records found with locality='%s' in FA. Retrying query by mapping locality to spot_name...", req.locality)
            cursor = conn.cursor()
            cursor.callproc("sp_fa_query", [
                req.user_name,
                req.user_id,
                req.complaint_no,
                req.complaint_code,       # NEW
                req.x_complaint_no,       # NEW
                req.priority,
                req.stage,
                req.category,
                req.category_sub,
                req.division,
                None,  # p_locality cleared
                req.building,
                req.floor,
                req.locality,  # p_spot_name mapped
                req.contract,
                req.tech,
                req.frequency,
                req.request_desc,
                req.is_withdraw,
                req.is_rework,
                req.is_bms,               # NEW
                req.is_active,
                req.is_draft,             # NEW
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
            formatted = format_response(raw)
            p_list = formatted.get("p_list", [])

        logger.info("[GET-FA] Fetched | count=%s", formatted["p_count"])
        return formatted
 
    except Exception as e:
        logger.error("[GET-FA] RPC failed | error=%s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))