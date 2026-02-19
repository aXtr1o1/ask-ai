from fastapi import APIRouter, HTTPException
from app.api.models.schemas import BDMRequest, StandardResponse
from app.api.database.supabase_client import get_supabase_client

router = APIRouter()

def format_response(raw) -> dict:
    if isinstance(raw, dict):
        return {
            "p_list": raw.get("p_list", []),
            "p_count": raw.get("p_count", 0),
        }
    safe = raw if isinstance(raw, list) else []
    return {"p_list": safe, "p_count": len(safe)}

@router.post("/get-bdm", response_model=StandardResponse, tags=["BDM"])
def get_bdm(req: BDMRequest):
    print(f"🔧 GetBDM | user_id={req.user_id} | status={req.status} | limit={req.limit}")

    try:
        client = get_supabase_client()

        response = client.rpc(
            "sp_bdm_query",
            {
                # Scope
                "p_user_id": req.user_id,

                # Text Filters
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

                # Search
                "p_keyword": req.keyword,

                # Date Ranges
                "p_date_from": req.date_from,
                "p_date_to": req.date_to,
                "p_completed_from": req.completed_from,
                "p_completed_to": req.completed_to,

                # Pagination
                "p_limit": req.limit,
                "p_offset": req.offset,
            },
        ).execute()

        result = format_response(response.data)
        return result

    except Exception as exc:
        print(f"❌ GetBDM Error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))