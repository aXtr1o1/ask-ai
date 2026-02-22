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
    
    logger.info("you can view the length of the p_list  and p_count value so that you can cross verify it")
    if isinstance(data, dict):
        p_list = data.get("p_list", [])
        p_count = data.get("p_count", 0)
        
        logger.info(
            "📊 format_response | p_list_length=%s | p_count=%s",
            len(p_list),
            p_count
        )
        return {"p_list": data.get("p_list", []), "p_count": data.get("p_count", 0)}
    
    safe_list = data if isinstance(data, list) else []

    logger.info(
        "📊 format_response | p_list_length=%s | p_count=%s",
        len(safe_list),
        len(safe_list)
    )

    return {
        "p_list": safe_list,
        "p_count": len(safe_list)
    }
    

@router.post("/get-assets")
def get_assets(req: AssetRequest):
    
    logger.info(
        "📦 assets endpoints called | user_id=%s | limit=%s | offset=%s",
        req.user_id, req.limit, req.offset
    )
    logger.debug(
        "📥 Incoming Assets request payload: %s",
        req.model_dump()
    )
    try:
        client = get_supabase_client()
        
        logger.info("🚀 Calling sp_asset_query RPC")
        
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
        
        formatted = format_response(response.data)
        
        logger.info(
            "✅ Assets response ready | count=%s",
            formatted["p_count"]
        )
        
        logger.debug(
            "📤 Assets final response: %s",
            formatted
        )
        
        return formatted
    
    except Exception as e:
        logger.error(f"❌Assets route failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))