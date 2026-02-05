from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from typing import Optional
from datetime import date
import uvicorn
import os
from dotenv import load_dotenv
load_dotenv()

# ==========================================
# 1. CONFIGURATION
# ==========================================
URL = os.getenv("URL")
KEY = os.getenv("KEY")
supabase: Client = create_client(URL, KEY)
app = FastAPI()

# ==========================================
# 2. DATA MODELS
# ==========================================
class AssetRequest(BaseModel):
    division: Optional[str] = None
    discipline: Optional[str] = None
    location: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    status: Optional[str] = None
    condition: Optional[str] = None
    priority: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    output_type: str = 'LIST'
    limit: int = 20

class ComplaintRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    nature: Optional[str] = None
    building: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    check_sla_for_id: Optional[str] = None
    output_type: str = 'LIST'
    limit: int = 20

class WorkOrderRequest(BaseModel):
    status: Optional[str] = None
    frequency: Optional[str] = None
    tech_name: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    output_type: str = 'LIST'
    limit: int = 20

# ==========================================
# 3. HELPER FUNCTION
# ==========================================
def format_manual_response(data):
    """
    Use this ONLY if the SQL returns a raw list of rows (e.g., [{}, {}]).
    Do NOT use this if SQL returns a pre-formatted JSON like {"p_list": ...}.
    """
    safe_list = data if data else []
    return {
        "p_list": safe_list,
        "p_count": len(safe_list)
    }

# ==========================================
# 4. ENDPOINTS
# ==========================================

# --- 1. ASSETS ENDPOINT (FIXED: Direct Return) ---
@app.post("/get-assets")
def get_assets(req: AssetRequest):
    print(f"📦 Assets Request: {req.output_type} | Div={req.division}")
    try:
        # The RPC 'sp_assets_query' returns the perfect JSON format {"p_list": [], "p_count": 0}
        response = supabase.rpc('sp_assets_query', {
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
        
        # ✅ FIX: Return response.data directly.
        # This prevents the "Double Wrapping" bug.
        return response.data

    except Exception as e:
        print(f"❌ Assets Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 2. COMPLAINTS ENDPOINT (Uses Helper) ---
@app.post("/get-complaints")
def get_complaints(req: ComplaintRequest):
    try:
        # A. SLA Check
        if req.check_sla_for_id:
            print(f"⏱️ Checking SLA for: {req.check_sla_for_id}")
            response = supabase.rpc('sp_workorder_sla_query', {
                'p_workorderno': req.check_sla_for_id,
                'p_slatype': 'REMAINING'
            }).execute()
            return {"data": response.data}

        # B. Standard Search
        print(f"🚨 Complaints Search: {req.status}")
        d_from = str(req.date_from) if req.date_from else None
        d_to = str(req.date_to) if req.date_to else None

        response = supabase.rpc('sp_complaints_query', {
            'p_status': req.status,
            'p_priority': req.priority,
            'p_nature': req.nature,
            'p_building': req.building,
            'p_datefrom': d_from,
            'p_dateto': d_to,
            'p_outputtype': req.output_type,
            'p_limit': req.limit
        }).execute()

        # Assuming this procedure returns a raw list -> Use helper
        return format_manual_response(response.data)

    except Exception as e:
        print(f"❌ Complaints Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 3. WORK ORDERS ENDPOINT (Uses Helper) ---
@app.post("/get-workorders")
def get_workorders(req: WorkOrderRequest):
    print(f"📅 WorkOrders Request: {req.status} | Freq={req.frequency}")
    try:
        d_from = str(req.date_from) if req.date_from else None
        d_to = str(req.date_to) if req.date_to else None

        response = supabase.rpc('sp_workorders_query', {
            'p_status': req.status,
            'p_frequency': req.frequency,
            'p_techname': req.tech_name,
            'p_datefrom': d_from,
            'p_dateto': d_to,
            'p_limit': req.limit
        }).execute()

        # Assuming this procedure returns a raw list -> Use helper
        return format_manual_response(response.data)

    except Exception as e:
        print(f"❌ WorkOrders Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("🚀 Server starting on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
