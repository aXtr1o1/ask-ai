"""
Assets Route
"""
from fastapi import APIRouter, HTTPException
import logging

from app.api.models.schemas import AssetRequest
from app.api.database.supabase_client import get_supabase_client

router = APIRouter()

logger = logging.getLogger("assets_route")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


def format_response(data):
    if isinstance(data, dict):
        return {"p_list": data.get("p_list", []), "p_count": data.get("p_count", 0)}
    safe = data if isinstance(data, list) else []
    return {"p_list": safe, "p_count": len(safe)}


@router.post("/get-assets", response_model=StandardResponse, tags=["Assets"])
def get_assets(req: AssetRequest):
    logger.info(f"📦 Assets | user_id={req.user_id} | limit={req.limit} offset={req.offset}")
    try:
        client = get_supabase_client()
        response = client.rpc("sp_asset_query", {
            "p_user_id": req.user_id,
            "p_status": req.status,
            "p_condition": req.condition,
            "p_priority": req.priority,
            "p_asset_type": req.asset_type,
            "p_division": req.division,
            "p_discipline": req.discipline,
            "p_locality": req.locality,
            "p_building": req.building,
            "p_floor": req.floor,
            "p_owner": req.owner,
            "p_make": req.make,
            "p_model": req.model,
            "p_service_area": req.service_area,
            "p_trade_group": req.trade_group,
            "p_on_hold": req.on_hold,
            "p_is_snagged": req.is_snagged,
            "p_is_scraped": req.is_scraped,
            "p_enable_ppm": req.enable_ppm,
            "p_enable_bdm": req.enable_bdm,
            "p_keyword": req.keyword,
            "p_date_from": req.date_from,
            "p_date_to": req.date_to,
            "p_limit": req.limit,
            "p_offset": req.offset,
        }).execute()
        return format_response(response.data)
    except Exception as e:
        logger.error(f"❌ Assets Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))