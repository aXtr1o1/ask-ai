from fastapi import APIRouter, HTTPException
from app.api.models.schemas import PPMRequest, StandardResponse
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

@router.post("/get-ppm", response_model=StandardResponse, tags=["PPM"])
def get_ppm(req: PPMRequest):
    print(f"🛠️ GetPPM | user_id={req.user_id} | status={req.status} | limit={req.limit}")

    try:
        client = get_supabase_client()

        response = client.rpc(
            "sp_ppm_query",
            {
                # Scope
                "p_user_id": req.user_id,

                # Text Filters
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

                # Search
                "p_keyword": req.keyword,

                # Date Ranges
                "p_date_from": req.date_from,
                "p_date_to": req.date_to,
                "p_comp_from": req.comp_from,
                "p_comp_to": req.comp_to,

                # SLA
                "p_sla_min": req.sla_min,
                "p_sla_max": req.sla_max,

                # Pagination
                "p_limit": req.limit,
                "p_offset": req.offset,
            },
        ).execute()

        result = format_response(response.data)
        return result

    except Exception as exc:
        print(f"❌ GetPPM Error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))