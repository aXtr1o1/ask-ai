"""
PPM Route (Planned Preventive Maintenance / Work Orders)
"""
from fastapi import APIRouter, HTTPException
import logging

from app.api.models.schemas import PPMRequest
from app.api.database.supabase_client import get_supabase_client

router = APIRouter()

logger = logging.getLogger("ppm_route")
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


@router.post("/get-ppm")
def get_ppm(req: PPMRequest):
    
    logger.info(
        "🛠️ ppm endpoint called | user_id=%s | status=%s | limit=%s",
        req.user_id, req.status, req.limit
    )
    
    logger.debug(
        "📥 Incoming PPM request payload: %s",
        req.model_dump()
    )
    
    try:
        client = get_supabase_client()
        
        logger.info("🚀 Calling sp_ppm_query RPC")
        
        response = client.rpc("sp_ppm_query", {
            "p_user_id": req.user_id,
            "p_status": req.status,
            "p_stage": req.stage,
            "p_frequency": req.frequency,
            "p_division": req.division,
            "p_discipline": req.discipline,
            "p_locality": req.locality,
            "p_building": req.building,
            "p_floor": req.floor,
            "p_contract": req.contract,
            "p_tech": req.tech,
            "p_keyword": req.keyword,
            "p_date_from": req.date_from,
            "p_date_to": req.date_to,
            "p_comp_from": req.comp_from,
            "p_comp_to": req.comp_to,
            "p_sla_min": req.sla_min,
            "p_sla_max": req.sla_max,
            "p_limit": req.limit,
            "p_offset": req.offset,
        }).execute()
        
        formatted = format_response(response.data)
        
        logger.info(
            "✅ PPM response ready | count=%s",
            formatted["p_count"]
        )
        
        logger.debug(
            "📤 PPM final response: %s",
            formatted
        )

        return formatted
    
    
    except Exception as e:
        logger.error(f"❌ PPM route  faild: {e}", exc_info=True)
        
        raise HTTPException(status_code=500, detail=str(e))