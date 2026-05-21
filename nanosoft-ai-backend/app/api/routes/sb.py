from fastapi import APIRouter, HTTPException
import logging
import json
import difflib
 
from app.api.models.schemas import SBRequest
from app.api.database.postgres_client import get_pool
from .utils import generate_fallback_candidates

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


def get_db_candidates(conn, field: str) -> list:
    column_map = {
        "building": "BuildingName",
        "locality": "LocalityName",
        "spot_name": "SpotName"
    }
    col = column_map.get(field)
    if not col:
        return []
    try:
        cursor = conn.cursor()
        query = f'SELECT DISTINCT "{col}" FROM public."ScheduleBased" WHERE "{col}" IS NOT NULL AND "{col}" <> \'\''
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        return [row[0] for row in rows if row[0]]
    except Exception as e:
        logger_sb.error("Error fetching DB candidates for %s: %s", field, str(e))
        return []


def find_close_matches(original_val: str, db_vals: list) -> list:
    if not original_val or not db_vals:
        return []
    val_map = {v.lower(): v for v in db_vals if v}
    matches = difflib.get_close_matches(original_val.lower(), list(val_map.keys()), n=3, cutoff=0.5)
    return [val_map[m] for m in matches]
 
 
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
            req.frequency,
            req.service_type,         # NEW
            req.division,
            req.discipline,
            None,  # p_locality cleared
            req.building,
            req.floor,
            req.locality,  # p_spot_name mapped
            req.contract,
            req.tech,
            req.is_withdraw,          # NEW
            req.is_reschedule,        # NEW
            req.is_rework,            # NEW
            req.is_active,            # NEW
            req.is_draft,             # NEW
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
 
        formatted = format_response_sb(raw)
 
        logger_sb.info("[GET-SB] Fetched | count=%s", formatted["p_count"])

        return formatted
 
    except Exception as e:
        logger_sb.error("[GET-SB] RPC failed | error=%s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))