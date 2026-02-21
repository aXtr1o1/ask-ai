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
    query_type = getattr(req, "query_type", "main").lower()
    logger.info(f"📅 PPM Single Endpoint | user_id={req.user_id} | type={query_type}")
    
    try:
        client = get_supabase_client()

        if query_type == "detail":
            response = client.rpc("sp_ppm_detail", {
                "p_work_order": getattr(req, "work_order", None),
                "p_user_id": req.user_id,
                "p_table_name": getattr(req, "table_name", "ppm")
            }).execute()
            return response.data

        elif query_type == "schedule":
            response = client.rpc("sp_ppm_schedule_query", {
                "p_user_id": req.user_id,
                "p_checktype": getattr(req, "checktype", "OVERDUE"),
                "p_table_name": getattr(req, "table_name", "ppm"),
                "p_limit": getattr(req, "limit", None)
            }).execute()
            return format_response(response.data)

        elif query_type == "summary":
            response = client.rpc("sp_ppm_summary_query", {
                "p_user_id": req.user_id,
                "p_groupby": getattr(req, "groupby", "FrequencyName"),
                "p_table_name": getattr(req, "table_name", "ppm")
            }).execute()
            return response.data

        elif query_type == "dataquality":
            response = client.rpc("sp_ppm_dataquality_query", {
                "p_user_id": req.user_id,
                "p_checktype": getattr(req, "checktype", "MISSING_TECH"),
                "p_table_name": getattr(req, "table_name", "ppm"),
                "p_limit": getattr(req, "limit", None),
                "p_offset": getattr(req, "offset", 0)
            }).execute()
            return format_response(response.data)

        else:
            # Default to "main" query
            response = client.rpc("sp_ppm_query", {
                "p_user_id": req.user_id,
                "p_table_name": getattr(req, "table_name", "ppm"),
                "p_work_order": getattr(req, "work_order", None),
                "p_status": getattr(req, "status", None),
                "p_stage": getattr(req, "stage", None),
                "p_frequency": getattr(req, "frequency", None),
                "p_division": getattr(req, "division", None),
                "p_discipline": getattr(req, "discipline", None),
                "p_locality": getattr(req, "locality", None),
                "p_building": getattr(req, "building", None),
                "p_floor": getattr(req, "floor", None),
                "p_contract": getattr(req, "contract", None),
                "p_tech": getattr(req, "tech", None),
                "p_keyword": getattr(req, "keyword", None),
                "p_date_from": getattr(req, "date_from", None),
                "p_date_to": getattr(req, "date_to", None),
                "p_comp_from": getattr(req, "comp_from", None),
                "p_comp_to": getattr(req, "comp_to", None),
                "p_sla_min": getattr(req, "sla_min", None),
                "p_sla_max": getattr(req, "sla_max", None),
                "p_limit": getattr(req, "limit", None),
                "p_offset": getattr(req, "offset", 0),
            }).execute()
            return format_response(response.data)

    except Exception as e:
        logger.error(f"❌ PPM Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))