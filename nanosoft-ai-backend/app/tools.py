#Here is the list of tools
from schemas import AssetsInput,ComplaintsInput,WorkOrdersInput
from langchain.tools import tool
import requests
import json


# =====================================================
# ✅ TOOL 1: ASSETS
# =====================================================


@tool(description="""
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
""",args_schema=AssetsInput)
def ASSETS(division=None,
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
    limit=20) -> str:
    print("\n==============================")
    print("🔧 ASSETS TOOL TRIGGERED")
    print("==============================")

    # ✅ Payload to API
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
    clean_payload = {k: v for k, v in payload.items() if v is not None}
    print("\n📤 Clean Payload Sent to Endpoint (No None Values):")
    print(clean_payload)

    FASTAPI_URL = "http://127.0.0.1:8000/get-assets"

    try:
        # ✅ Call FastAPI Endpoint
        response = requests.post(FASTAPI_URL, json=clean_payload)

        print("\n✅ Raw Response Status Code:", response.status_code)

        if response.status_code != 200:
            return f"❌ API Error: {response.text}"

        # ✅ JSON Output
        data = response.json()

        print("\n📥 Parsed JSON Response (Endpoint → Tool):")
        print(json.dumps(data, indent=4))

        return json.dumps(data)

    except Exception as e:
        print("❌ Endpoint Call Failed:", str(e))
        return f"Error calling endpoint: {str(e)}"


# =====================================================
# ✅ TOOL 2: COMPLAINTS
# =====================================================

@tool(description="""
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
""",args_schema=ComplaintsInput)
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

    print("\n==============================")
    print("🚨 COMPLAINTS TOOL TRIGGERED")
    print("==============================")

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

    # Remove None values
    clean_payload = {k: v for k, v in payload.items() if v is not None}

    print("\n📤 Clean Payload Sent to Complaints Endpoint:")
    print(clean_payload)

    FASTAPI_URL = "http://127.0.0.1:8000/get-complaints"

    try:
        response = requests.post(FASTAPI_URL, json=clean_payload)

        print("\n✅ Raw Response Status Code:", response.status_code)

        if response.status_code != 200:
            return f"❌ API Error: {response.text}"

        data = response.json()

        print("\n📥 Parsed JSON Response (Endpoint → Tool):")
        print(json.dumps(data, indent=4))

        return json.dumps(data)

    except Exception as e:
        print("❌ Endpoint Call Failed:", str(e))
        return f"Error calling complaints endpoint: {str(e)}"


# =====================================================
# ✅ TOOL 3: WORK ORDERS
# =====================================================
@tool(description="""
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
""",args_schema= WorkOrdersInput)
def WORK_ORDERS(
    status=None,
    frequency=None,
    tech_name=None,
    date_from=None,
    date_to=None,
    output_type="LIST",
    limit=20
) -> str:

    print("\n==============================")
    print("📅 WORK ORDERS TOOL TRIGGERED")
    print("==============================")

    payload = {
        "status": status,
        "frequency": frequency,
        "tech_name": tech_name,
        "date_from": date_from,
        "date_to": date_to,
        "output_type": output_type,
        "limit": limit
    }

    # Remove None values
    clean_payload = {k: v for k, v in payload.items() if v is not None}

    print("\n📤 Clean Payload Sent to WorkOrders Endpoint:")
    print(clean_payload)

    FASTAPI_URL = "http://127.0.0.1:8000/get-workorders"

    try:
        response = requests.post(FASTAPI_URL, json=clean_payload)

        print("\n✅ Raw Response Status Code:", response.status_code)

        if response.status_code != 200:
            return f"❌ API Error: {response.text}"

        data = response.json()

        print("\n📥 Parsed JSON Response (Endpoint → Tool):")
        print(json.dumps(data, indent=4))

        return json.dumps(data)

    except Exception as e:
        print("❌ Endpoint Call Failed:", str(e))
        return f"Error calling workorders endpoint: {str(e)}"

