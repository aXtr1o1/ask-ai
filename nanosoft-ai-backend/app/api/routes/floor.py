from fastapi import APIRouter, HTTPException
import logging
import json

from app.api.models.schemas import FloorRequest
from app.api.database.postgres_client import get_pool
from .query_search_fallback import merge_format_response, apply_limit_offset

router = APIRouter()
logger = logging.getLogger("floor_route")
logger.setLevel(logging.INFO)

def format_response(data):
    out = merge_format_response(data)
    return out

def _call_sp_floor_query(req: FloorRequest) -> dict:
    conn = get_pool()
    cursor = conn.cursor()
    cursor.callproc("sp_floor_query", [
        req.user_name,
        req.user_id,
        req.floor_code,
        req.floor_name,
        req.building,
        req.building_code,
        req.locality,
        req.locality_code,
        req.is_active,
        req.is_draft,
        req.is_non_contract,
        req.is_default,
        req.keyword,
        req.date_from,
        req.date_to,
        req.limit,
        req.offset,
    ])
    row = cursor.fetchone()
    cursor.close()
    raw = row[0] if row else {}
    if isinstance(raw, str):
        raw = json.loads(raw)
    return format_response(raw)

@router.post("/get-floor")
def get_floor(req: FloorRequest):
    logger.info(
        "📦 [GET-FLOOR] Incoming | user_name=%s | limit=%s | offset=%s",
        req.user_name, req.limit, req.offset
    )
    
    try:
        raw_data = _call_sp_floor_query(req)
        formatted = apply_limit_offset(raw_data, req)
        
        p_list = formatted.get("p_list", [])
        if p_list:
            logger.info("[GET-FLOOR] Success | count=%s", formatted.get("p_count", 0))
        else:
            logger.info("[GET-FLOOR] Success | count=0")
            
        return formatted
    except Exception as e:
        err_msg = str(e)
        logger.error("[GET-FLOOR] RPC failed | error=%s", err_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=err_msg)
