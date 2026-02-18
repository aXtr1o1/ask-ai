"""
BDM Route (Breakdown Maintenance / Complaints)
"""
from fastapi import APIRouter, HTTPException
import logging

from app.api.models.schemas import BDMRequest
from app.api.database.supabase_client import get_supabase_client

router = APIRouter()

logger = logging.getLogger("bdm_route")
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


@router.post("/get-bdm")
def get_bdm(req: BDMRequest):
    logger.info(f"🔧 BDM | user_id={req.user_id} | status={req.status} | limit={req.limit}")
    try:
        client = get_supabase_client()
        response = client.rpc("sp_bdm_query", {
            "p_user_id": req.user_id,
            "p_status": req.status,
            "p_priority": req.priority,
            "p_stage": req.stage,
            "p_complaint_type": req.complaint_type,
            "p_complaint_mode": req.complaint_mode,
            "p_complaint_nature": req.complaint_nature,
            "p_wo_type": req.wo_type,
            "p_service_type": req.service_type,
            "p_division": req.division,
            "p_discipline": req.discipline,
            "p_locality": req.locality,
            "p_building": req.building,
            "p_floor": req.floor,
            "p_contract": req.contract,
            "p_analysis_tech": req.analysis_tech,
            "p_execution_tech": req.execution_tech,
            "p_complainer": req.complainer,
            "p_keyword": req.keyword,
            "p_date_from": req.date_from,
            "p_date_to": req.date_to,
            "p_completed_from": req.completed_from,
            "p_completed_to": req.completed_to,
            "p_limit": req.limit,
            "p_offset": req.offset,
        }).execute()
        return format_response(response.data)
    except Exception as e:
        logger.error(f"❌ BDM Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))