"""
Assets Route
Handles asset-related database queries
"""
from fastapi import APIRouter, HTTPException

from app.api.models.schemas import AssetRequest
from app.api.database.supabase_client import get_supabase_client

router = APIRouter()

def format_manual_response(data):
    """
    Format raw list response from stored procedure
    Used when SP returns raw rows instead of pre-formatted JSON
    """
    safe_list = data if data else []
    return {
        "p_list": safe_list,
        "p_count": len(safe_list)
    }

@router.post("/get-assets")
def get_assets(req: AssetRequest):
    """
    Query assets from database
    
    Supports filtering by:
    - Division, Discipline, Location
    - Make, Model, Status, Condition, Priority
    - Manufacturing year range
    """
    print(f"📦 Assets Request: {req.output_type} | Division={req.division}")
    
    try:
        client = get_supabase_client()
        response = client.rpc('sp_assets_query', {
            'p_divisionname': req.division,
            'p_disciplinename': req.discipline,
            'p_locationname': req.location,
            'p_makename': req.make,
            'p_modelname': req.model,
            'p_statusname': req.status,
            'p_conditionname': req.condition,
            'p_priorityname': req.priority,
            'p_yearfrom': req.year_from,
            'p_yearto': req.year_to,
            'p_outputtype': req.output_type,
            'p_limit': req.limit
        }).execute()
        
        # Return response data directly (already formatted by stored procedure)
        return format_manual_response(response.data)
        
    except Exception as e:
        print(f"❌ Assets Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))