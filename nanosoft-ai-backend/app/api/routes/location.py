from fastapi import APIRouter, HTTPException
import logging
import json

from app.api.models.schemas import LocationRequest
from app.api.database.postgres_client import get_pool
from .query_search_fallback import merge_format_response, apply_limit_offset

router = APIRouter()
logger = logging.getLogger("location_route")
logger.setLevel(logging.INFO)

def format_response(data):
    out = merge_format_response(data)
    return out

def _call_sp_location_query(req: LocationRequest) -> dict:
    conn = get_pool()
    cursor = conn.cursor()
    cursor.callproc("sp_location_query", [
        req.user_name,
        req.user_id,
        req.locality_code,
        req.locality_name,
        req.city,
        req.city_code,
        req.locality_group,
        req.admin_locality_type,
        req.is_active,
        req.is_draft,
        req.is_portal_display,
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

@router.post("/get-location")
def get_location(req: LocationRequest):
    logger.info(
        "📦 [GET-LOCATION] Incoming | user_name=%s | limit=%s | offset=%s",
        req.user_name, req.limit, req.offset
    )
    
    try:
        raw_data = _call_sp_location_query(req)
        formatted = apply_limit_offset(raw_data, req)
        
        p_list = formatted.get("p_list", [])
        if p_list:
            logger.info("[GET-LOCATION] Success | count=%s", formatted.get("p_count", 0))
        else:
            logger.info("[GET-LOCATION] Success | count=0")
            
        return formatted
    except Exception as e:
        err_msg = str(e)
        logger.error("[GET-LOCATION] RPC failed | error=%s", err_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=err_msg)
