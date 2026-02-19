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
    if isinstance(data, dict):
        return {"p_list": data.get("p_list", []), "p_count": data.get("p_count", 0)}
    safe = data if isinstance(data, list) else []
    return {"p_list": safe, "p_count": len(safe)}


@router.post("/get-ppm")
def get_ppm(req: PPMRequest):
    logger.info(f"🛠️ PPM | user_id={req.user_id} | status={req.status} | limit={req.limit}")
    try:
        client = get_supabase_client()
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
        return format_response(response.data)
    except Exception as e:
        logger.error(f"❌ PPM Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))