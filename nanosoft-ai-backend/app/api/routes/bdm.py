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
    query_type = getattr(req, "query_type", "main").lower()
    logger.info(f"🔧 BDM Single Endpoint | user_id={req.user_id} | type={query_type}")
    
    try:
        client = get_supabase_client()

        if query_type == "detail":
            response = client.rpc("sp_bdm_detail", {
                "p_complaint_no": getattr(req, "complaint_no", None),
                "p_user_id": req.user_id,
                "p_table_name": getattr(req, "table_name", "bdm")
            }).execute()
            return response.data

        elif query_type == "sla":
            response = client.rpc("sp_bdm_sla_query", {
                "p_complaint_no": getattr(req, "complaint_no", None),
                "p_slatype": getattr(req, "slatype", "FULL"),
                "p_user_id": req.user_id,
                "p_table_name": getattr(req, "table_name", "bdm")
            }).execute()
            return response.data

        elif query_type == "summary":
            response = client.rpc("sp_bdm_summary_query", {
                "p_user_id": req.user_id,
                "p_groupby": getattr(req, "groupby", "WoStatus"),
                "p_table_name": getattr(req, "table_name", "bdm")
            }).execute()
            return response.data

        elif query_type == "dataquality":
            response = client.rpc("sp_bdm_dataquality_query", {
                "p_user_id": req.user_id,
                "p_checktype": getattr(req, "checktype", "SLA_BREACHED"),
                "p_table_name": getattr(req, "table_name", "bdm"),
                "p_limit": getattr(req, "limit", None),
                "p_offset": getattr(req, "offset", 0)
            }).execute()
            return format_response(response.data)

        else:
            # Default to "main" query
            response = client.rpc("sp_bdm_query", {
                "p_user_id": req.user_id,
                "p_table_name": getattr(req, "table_name", "bdm"),
                "p_complaint_no": getattr(req, "complaint_no", None),
                "p_status": getattr(req, "status", None),
                "p_priority": getattr(req, "priority", None),
                "p_stage": getattr(req, "stage", None),
                "p_complaint_type": getattr(req, "complaint_type", None),
                "p_complaint_mode": getattr(req, "complaint_mode", None),
                "p_complaint_nature": getattr(req, "complaint_nature", None),
                "p_wo_type": getattr(req, "wo_type", None),
                "p_service_type": getattr(req, "service_type", None),
                "p_division": getattr(req, "division", None),
                "p_discipline": getattr(req, "discipline", None),
                "p_locality": getattr(req, "locality", None),
                "p_building": getattr(req, "building", None),
                "p_floor": getattr(req, "floor", None),
                "p_contract": getattr(req, "contract", None),
                "p_analysis_tech": getattr(req, "analysis_tech", None),
                "p_execution_tech": getattr(req, "execution_tech", None),
                "p_complainer": getattr(req, "complainer", None),
                "p_keyword": getattr(req, "keyword", None),
                "p_date_from": getattr(req, "date_from", None),
                "p_date_to": getattr(req, "date_to", None),
                "p_completed_from": getattr(req, "completed_from", None),
                "p_completed_to": getattr(req, "completed_to", None),
                "p_limit": getattr(req, "limit", None),
                "p_offset": getattr(req, "offset", 0),
            }).execute()
            return format_response(response.data)

    except Exception as e:
        logger.error(f"❌ BDM Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))