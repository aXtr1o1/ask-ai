"""
LangChain Tools for Facility Management
Defines tools for querying assets, complaints, and work orders
"""
from langchain.tools import tool
import requests
import json

from app.models.schemas import AssetsInput, ComplaintsInput, WorkOrdersInput
from app.config import settings


# =====================================================
# ✅ TOOL 1: ASSETS
# =====================================================

@tool(
    description="""
Use this tool when the user asks about ASSETS (Master Equipment List).

Assets represent physical equipment installed in the facility.
This includes asset details such as:

- Asset Tag Number
- Equipment Name, Make, Model, Serial Number
- Location info (Locality, Building, Floor, Spot)
- Division and Discipline
- Asset Status, Condition, Priority
- Maintenance enable flags (PPM / BDM)

Call this tool for queries like:
- List assets
- Asset information lookup
- Equipment location or status
""",
    args_schema=AssetsInput
)
def ASSETS(
    division=None,
    discipline=None,
    location=None,
    make=None,
    model=None,
    status=None,
    condition=None,
    priority=None,
    floor=None,
    spot=None,
    year_from=None,
    year_to=None,
    output_type="LIST",
    limit=20
) -> str:
    """Query assets from the database"""
    print("\n" + "="*30)
    print("🔧 ASSETS TOOL TRIGGERED")
    print("="*30)
    
    payload = {
        "division": division,
        "discipline": discipline,
        "location": location,
        "make": make,
        "model": model,
        "status": status,
        "condition": condition,
        "priority": priority,
        "floor": floor,
        "spot": spot,
        "year_from": year_from,
        "year_to": year_to,
        "output_type": output_type,
        "limit": limit
    }
    
    # Remove None values
    clean_payload = {k: v for k, v in payload.items() if v is not None}
    print("\n📤 Payload:", clean_payload)
    
    url = f"{settings.DATABASE_API_URL}/get-assets"
    
    try:
        response = requests.post(url, json=clean_payload)
        print(f"✅ Status: {response.status_code}")
        
        if response.status_code != 200:
            return f"❌ API Error: {response.text}"
        
        data = response.json()
        print(f"📥 Response: {json.dumps(data, indent=2)}")
        
        return json.dumps(data)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return f"Error calling endpoint: {str(e)}"


# =====================================================
# ✅ TOOL 2: COMPLAINTS
# =====================================================

@tool(
    description="""
Use this tool when the user asks about COMPLAINTS (Reactive / Breakdown Maintenance).

Complaints represent breakdown issues reported against an asset.
This table tracks:

- Complaint Number
- Related Asset Tag
- Complaint Nature and Priority
- Work Order Status (WoStatus)
- Complaint Dates and SLA timeline
- Complainer Name and Technician Analysis
- Complaint Mode (Phone/App/etc.)

Call this tool for queries like:
- Register complaint
- Complaint status tracking
- Breakdown job history
- SLA complaint monitoring
""",
    args_schema=ComplaintsInput
)
def COMPLAINTS(
    status=None,
    priority=None,
    nature=None,
    building=None,
    date_from=None,
    date_to=None,
    check_sla_for_id=None,
    output_type="LIST",
    limit=20
) -> str:
    """Query complaints from the database"""
    print("\n" + "="*30)
    print("🚨 COMPLAINTS TOOL TRIGGERED")
    print("="*30)
    
    payload = {
        "status": status,
        "priority": priority,
        "nature": nature,
        "building": building,
        "date_from": date_from,
        "date_to": date_to,
        "check_sla_for_id": check_sla_for_id,
        "output_type": output_type,
        "limit": limit
    }
    
    clean_payload = {k: v for k, v in payload.items() if v is not None}
    print("\n📤 Payload:", clean_payload)
    
    url = f"{settings.DATABASE_API_URL}/get-complaints"
    
    try:
        response = requests.post(url, json=clean_payload)
        print(f"✅ Status: {response.status_code}")
        
        if response.status_code != 200:
            return f"❌ API Error: {response.text}"
        
        data = response.json()
        print(f"📥 Response: {json.dumps(data, indent=2)}")
        
        return json.dumps(data)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return f"Error calling complaints endpoint: {str(e)}"


# =====================================================
# ✅ TOOL 3: WORK ORDERS
# =====================================================

@tool(
    description="""
Use this tool when the user asks about WORK ORDERS (Scheduled Preventive Maintenance - PPM).

Work Orders represent planned maintenance tasks assigned to assets.
This includes:

- Work Order Number
- Linked Asset Tag
- Frequency (Monthly/Weekly/etc.)
- PPM Status and Stage
- Technician assigned (PMTechName)
- Scheduled Date and Completion Date
- Division and Contract info

Call this tool for queries like:
- Open work orders
- Preventive maintenance schedules
- PPM job completion tracking
- Technician assigned work orders
""",
    args_schema=WorkOrdersInput
)
def WORK_ORDERS(
    status=None,
    frequency=None,
    tech_name=None,
    date_from=None,
    date_to=None,
    output_type="LIST",
    limit=20
) -> str:
    """Query work orders from the database"""
    print("\n" + "="*30)
    print("📅 WORK ORDERS TOOL TRIGGERED")
    print("="*30)
    
    payload = {
        "status": status,
        "frequency": frequency,
        "tech_name": tech_name,
        "date_from": date_from,
        "date_to": date_to,
        "output_type": output_type,
        "limit": limit
    }
    
    clean_payload = {k: v for k, v in payload.items() if v is not None}
    print("\n📤 Payload:", clean_payload)
    
    url = f"{settings.DATABASE_API_URL}/get-workorders"
    
    try:
        response = requests.post(url, json=clean_payload)
        print(f"✅ Status: {response.status_code}")
        
        if response.status_code != 200:
            return f"❌ API Error: {response.text}"
        
        data = response.json()
        print(f"📥 Response: {json.dumps(data, indent=2)}")
        
        return json.dumps(data)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return f"Error calling workorders endpoint: {str(e)}"