"""
Work Orders Route
Handles work order (PPM) related database queries
"""
from fastapi import APIRouter, HTTPException
from app.api.models.schemas import WorkOrderRequest
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


@router.post("/get-workorders")
def get_workorders(req: WorkOrderRequest):
    """
    Query work orders (PPM) from database
    
    Supports filtering by:
    - Status (Open, Closed, etc.)
    - Frequency (Monthly, Weekly, etc.)
    - Technician name
    - Date range
    """
    print(f"📅 WorkOrders Request: Status={req.status} | Frequency={req.frequency}")
    
    try:
        # Get the Supabase client safely
        client = get_supabase_client()
        
        # Convert dates to strings if present
        d_from = str(req.date_from) if req.date_from else None
        d_to = str(req.date_to) if req.date_to else None
        
        response = client.rpc('sp_workorders_query', {
            'p_status': req.status,
            'p_frequency': req.frequency,
            'p_techname': req.tech_name,
            'p_datefrom': d_from,
            'p_dateto': d_to,
            'p_limit': req.limit
        }).execute()
        
        # Format response
        return format_manual_response(response.data)
        
    except Exception as e:
        print(f"❌ WorkOrders Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
