"""
LangChain Tools for Facility Management
"""
from langchain.tools import tool
import requests
import json
import logging

from app.models.schemas import AssetsInput, PPMInput, BDMInput
from app.config import settings

logger = logging.getLogger("facility_tools")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


# =====================================================
# ✅ TOOL 1: ASSETS
# =====================================================

@tool(
    description="""
Use this tool when the user asks about ASSETS (physical equipment/master equipment list).

Covers:
- Asset tag, name, make, model, serial number
- Location: locality, building, floor, service area
- Division, discipline, trade group
- Status, condition, priority
- Boolean flags: on hold, snagged, scraped, PPM enabled, BDM enabled
- Barcode lookup, keyword search, date range

Example queries:
- List active assets in HVAC division
- Show assets on Floor 2
- Find asset by barcode
- Assets with PPM enabled
""",
    args_schema=AssetsInput
)
def ASSETS(
    user_id=None,
    status=None, condition=None, priority=None, asset_type=None,
    division=None, discipline=None, locality=None, building=None, floor=None,
    owner=None, make=None, model=None, service_area=None, trade_group=None,
    on_hold=None, is_snagged=None, is_scraped=None, enable_ppm=None, enable_bdm=None,
    barcode=None, keyword=None, date_from=None, date_to=None,
    limit=20, offset=0
) -> str:
    logger.info(f"📦 ASSETS TOOL TRIGGERED for user_id: {user_id}")

    payload = {
        "user_id": user_id,
        "status": status, "condition": condition, "priority": priority,
        "asset_type": asset_type, "division": division, "discipline": discipline,
        "locality": locality, "building": building, "floor": floor,
        "owner": owner, "make": make, "model": model,
        "service_area": service_area, "trade_group": trade_group,
        "on_hold": on_hold, "is_snagged": is_snagged, "is_scraped": is_scraped,
        "enable_ppm": enable_ppm, "enable_bdm": enable_bdm,
        "barcode": barcode, "keyword": keyword,
        "date_from": date_from, "date_to": date_to,
        "limit": limit, "offset": offset
    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    logger.debug(f"📤 Payload: {clean_payload}")

    try:
        response = requests.post(f"{settings.DATABASE_API_URL}/get-assets", json=clean_payload)
        logger.info(f"✅ API Status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"❌ API Error Response: {response.text}")
            return f"❌ API Error: {response.text}"

        response_json = response.json()
        logger.debug("📥 API Response JSON:")
        logger.debug(json.dumps(response_json, indent=2))

        return json.dumps(response_json)
    except Exception as e:
        logger.error(f"❌ Assets tool error: {e}", exc_info=True)
        return f"Error calling assets endpoint: {str(e)}"


# =====================================================
# ✅ TOOL 2: PPM
# =====================================================

@tool(
    description="""
Use this tool when the user asks about PPM (Planned Preventive Maintenance) work orders.

Covers:
- Work order status, stage, frequency (Monthly/Weekly/etc.)
- Division, discipline, locality, building, floor
- Contract, assigned technician
- Scheduled date range, completion date range
- SLA duration filters
- Keyword search

Example queries:
- Show open PPM work orders
- Monthly PPM tasks for technician Ravi
- PPM jobs due this month
- Completed work orders in Electric division
""",
    args_schema=PPMInput
)
def PPM(
    user_id=None,
    status=None, stage=None, frequency=None,
    division=None, discipline=None, locality=None, building=None, floor=None,
    contract=None, tech=None, keyword=None,
    date_from=None, date_to=None, comp_from=None, comp_to=None,
    sla_min=None, sla_max=None, limit=20, offset=0
) -> str:
    logger.info(f"🛠️ PPM TOOL TRIGGERED for user_id: {user_id}")

    payload = {
        "user_id": user_id,
        "status": status, "stage": stage, "frequency": frequency,
        "division": division, "discipline": discipline,
        "locality": locality, "building": building, "floor": floor,
        "contract": contract, "tech": tech, "keyword": keyword,
        "date_from": date_from, "date_to": date_to,
        "comp_from": comp_from, "comp_to": comp_to,
        "sla_min": sla_min, "sla_max": sla_max,
        "limit": limit, "offset": offset
    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    logger.debug(f"📤 Payload: {clean_payload}")

    try:
        response = requests.post(f"{settings.DATABASE_API_URL}/get-ppm", json=clean_payload)
        logger.info(f"✅ API Status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"❌ API Error Response: {response.text}")
            return f"❌ API Error: {response.text}"

        response_json = response.json()
        logger.debug("📥 API Response JSON:")
        logger.debug(json.dumps(response_json, indent=2))

        return json.dumps(response_json)
    except Exception as e:
        logger.error(f"❌ PPM tool error: {e}", exc_info=True)
        return f"Error calling PPM endpoint: {str(e)}"


# =====================================================
# ✅ TOOL 3: BDM
# =====================================================

@tool(
    description="""
Use this tool when the user asks about BDM (Breakdown Maintenance) complaints.

Covers:
- Complaint status, priority, stage
- Complaint type, mode, nature
- Work order type, service type
- Division, discipline, locality, building, floor
- Contract, analysis technician, execution technician, complainer
- Complaint date range, completion date range
- Keyword search

Example queries:
- Show open breakdown complaints
- Complaints raised by John in Building A
- High priority BDM jobs pending
- Breakdown jobs completed this week
""",
    args_schema=BDMInput
)
def BDM(
    user_id=None,
    status=None, priority=None, stage=None,
    complaint_type=None, complaint_mode=None, complaint_nature=None,
    wo_type=None, service_type=None,
    division=None, discipline=None, locality=None, building=None, floor=None,
    contract=None, analysis_tech=None, execution_tech=None, complainer=None,
    keyword=None, date_from=None, date_to=None,
    completed_from=None, completed_to=None,
    limit=20, offset=0
) -> str:
    logger.info(f"🔧 BDM TOOL TRIGGERED for user_id: {user_id}")

    payload = {
        "user_id": user_id,
        "status": status, "priority": priority, "stage": stage,
        "complaint_type": complaint_type, "complaint_mode": complaint_mode,
        "complaint_nature": complaint_nature, "wo_type": wo_type,
        "service_type": service_type, "division": division, "discipline": discipline,
        "locality": locality, "building": building, "floor": floor,
        "contract": contract, "analysis_tech": analysis_tech,
        "execution_tech": execution_tech, "complainer": complainer,
        "keyword": keyword, "date_from": date_from, "date_to": date_to,
        "completed_from": completed_from, "completed_to": completed_to,
        "limit": limit, "offset": offset
    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    logger.debug(f"📤 Payload: {clean_payload}")

    try:
        response = requests.post(f"{settings.DATABASE_API_URL}/get-bdm", json=clean_payload)
        logger.info(f"✅ API Status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"❌ API Error Response: {response.text}")
            return f"❌ API Error: {response.text}"

        response_json = response.json()
        logger.debug("📥 API Response JSON:")
        logger.debug(json.dumps(response_json, indent=2))

        return json.dumps(response_json)
    except Exception as e:
        logger.error(f"❌ BDM tool error: {e}", exc_info=True)
        return f"Error calling BDM endpoint: {str(e)}"