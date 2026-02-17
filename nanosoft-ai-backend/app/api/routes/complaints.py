"""
Complaints Route
Handles complaint-related database queries
"""
from fastapi import APIRouter, HTTPException
from app.api.models.schemas import ComplaintRequest
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


@router.post("/get-complaints")
def get_complaints(req: ComplaintRequest):
    """
    Query complaints from database
    
    Two modes:
    1. SLA Check: Pass check_sla_for_id to get SLA status for specific complaint
    2. Search: Filter complaints by status, priority, nature, building, dates
    """
    try:
        # Get the Supabase client safely
        client = get_supabase_client()

        # Mode A: SLA Check
        if req.check_sla_for_id:
            print(f"⏱️ Checking SLA for: {req.check_sla_for_id}")
            response = client.rpc('sp_workorder_sla_query', {
                'p_workorderno': req.check_sla_for_id,
                'p_slatype': 'REMAINING'
            }).execute()
            return {"data": response.data}
        
        # Mode B: Standard Complaint Search
        print(f"🚨 Complaints Search: Status={req.status}")
        
        # Convert dates to strings if present
        d_from = str(req.date_from) if req.date_from else None
        d_to = str(req.date_to) if req.date_to else None
        
        response = client.rpc('sp_complaints_query', {
            'p_status': req.status,
            'p_priority': req.priority,
            'p_nature': req.nature,
            'p_building': req.building,
            'p_datefrom': d_from,
            'p_dateto': d_to,
            'p_outputtype': req.output_type,
            'p_limit': req.limit
        }).execute()
        
        # Format response if needed
        return format_manual_response(response.data)
        
    except Exception as e:
        print(f"❌ Complaints Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
