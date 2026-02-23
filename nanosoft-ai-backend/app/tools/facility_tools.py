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
        Use this tool when the user asks about ASSETS (physical or master equipment records).

        This tool retrieves asset details used as the foundation for SLA tracking, 
        maintenance planning, and compliance evaluation.

        It supports advanced filtering to identify assets by:
        - Ownership and user isolation (user_id)
        - Operational state (status, condition, priority)
        - Asset classification (asset_type, division, discipline, trade_group)
        - Physical location hierarchy (locality, building, floor, service_area)
        - Manufacturer details (make, model)
        - Maintenance configuration flags:
        - on_hold (temporarily inactive assets)
        - is_snagged (assets with issues)
        - is_scraped (decommissioned assets)
        - enable_ppm (Preventive Maintenance enabled)
        - enable_bdm (Breakdown Maintenance enabled)
        - Asset identification (barcode, keyword search)
        - Asset creation or update date range
        - Pagination support (limit, offset)

        This tool is commonly used to:
        - List active or inactive assets
        - Identify assets eligible for PPM or BDM
        - Filter assets for SLA compliance analysis
        - Perform asset-level searches before fetching PPM or BDM records

        Always use this tool when the query is about equipment, asset metadata, 
        or asset-level maintenance eligibility.
        """,
        args_schema=AssetsInput
)
def ASSETS(
    user_id=None,
    status=None, condition=None, priority=None, asset_type=None,asset_tag_no=None,
    division=None, discipline=None, locality=None, building=None, floor=None,
    owner=None, make=None, model=None, service_area=None, trade_group=None,
    on_hold=None, is_snagged=None, is_scraped=None, enable_ppm=None, enable_bdm=None,
    barcode=None, keyword=None, date_from=None, date_to=None,
    limit=None, offset=None 
) -> str:
    # user_id is always injected from the frontend request; never use model-provided value
    if not user_id:
        logger.error(" ASSETS called without user_id")
        return "Error: user_id is required. It is set from the authenticated request."
    logger.info(f"📦 ASSETS TOOL TRIGGERED for user_id: {user_id}")

    payload = {
        "user_id": user_id,
        "status": status, "condition": condition, "priority": priority,"asset_tag_no":asset_tag_no,
        "asset_type": asset_type, "division": division, "discipline": discipline,
        "locality": locality, "building": building, "floor": floor,
        "owner": owner, "make": make, "model": model,
        "service_area": service_area, "trade_group": trade_group,
        "on_hold": on_hold, "is_snagged": is_snagged, "is_scraped": is_scraped,
        "enable_ppm": enable_ppm, "enable_bdm": enable_bdm,
        "barcode": barcode, "keyword": keyword,
        "date_from": date_from, "date_to": date_to,
        "limit": limit,   
        "offset": 0,   
    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    

    logger.debug("Clean payload prepared: %s", clean_payload)

    try:
        logger.info("🚀 Sending payload to /get-assets endpoint")
        
        response = requests.post(f"{settings.DATABASE_API_URL}/get-assets", json=clean_payload)
        
        logger.info(
            "📥 Response received from /get-assets | status_code=%s",
            response.status_code
        )

        if response.status_code != 200:
            
            logger.error(f"❌ API Error Response No message is recived: {response.status_code,response.text}")
            return f"❌ API Error No message is recived:: {response.status_code,response.text}"

        response_json = response.json()
        
        logger.debug(
            "📦 Response data from DB: %s",
            json.dumps(response_json, indent=2)
        )
        logger.info("✅ Assets data successfully processed")
        
        return json.dumps(response_json)
    
    except Exception as e:
        
        logger.error(f"❌ Assets tool error: {e}", exc_info=True)
        return f"Error calling assets endpoint: {str(e)}"


# =====================================================
# ✅ TOOL 2: PPM
# =====================================================

@tool(
    description="""
        Use this tool when the user asks about PPM (Planned / Preventive Maintenance) records.

        This tool retrieves scheduled maintenance jobs and their SLA performance,
        helping to evaluate preventive maintenance compliance.

        It supports filtering by:
        - User isolation (user_id)
        - PPM execution status and workflow stage
        - Maintenance frequency (daily, weekly, monthly, etc.)
        - Organizational structure (division, discipline)
        - Location hierarchy (locality, building, floor)
        - Contract association
        - Assigned technician
        - Keyword-based search
        - Planned or actual maintenance date ranges
        - Completion date ranges
        - SLA duration filters (sla_min, sla_max in minutes)
        - Pagination (limit, offset)

        This tool is primarily used to:
        - Monitor PPM completion against SLA timelines
        - Identify delayed or overdue preventive maintenance
        - Analyze technician or contract-based SLA performance
        - Generate compliance reports for audits and dashboards

        Always use this tool when the query is about scheduled maintenance,
        preventive tasks, or SLA compliance related to PPM.
        """,
            args_schema=PPMInput
)
def PPM(
    user_id=None,
    status=None, stage=None, frequency=None,
    division=None, discipline=None, locality=None, building=None, floor=None,
    contract=None, tech=None, keyword=None,
    date_from=None, date_to=None, comp_from=None, comp_to=None,
    sla_min=None, sla_max=None,
    limit=None, offset=None 
) -> str:
    if not user_id:
        logger.error("❌ PPM called without user_id")
        return "Error: user_id is required. It is set from the authenticated request."
    
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
        "limit": limit,   
        "offset": 0,   
    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    
    logger.debug("📤 PPM payload prepared: %s", clean_payload)
    

    try:
        logger.info("🚀 Sending PPM request to /get-ppm")
        
        response = requests.post(f"{settings.DATABASE_API_URL}/get-ppm", json=clean_payload)
        
        logger.info(
            "📥 PPM response received | status_code=%s",
            response.status_code
        )

        if response.status_code != 200:
            
            logger.error(f"❌ API Error Response: {response.status_code,response.text}")
            return f"❌ API Error: {response.status_code,response.text}"

        response_json = response.json()
        logger.debug(
            "📦 PPM response data: %s",
            json.dumps(response_json, indent=2)
        )
        
        logger.info("✅ PPM data processed successfully")
        
        return json.dumps(response_json)
    
    except Exception as e:
        logger.error(f"❌ PPM tool error: {e}", exc_info=True)
        return f"Error calling PPM endpoint: {str(e)}"


# =====================================================
# ✅ TOOL 3: BDM
# =====================================================

@tool(
    description="""
        Use this tool when the user asks about BDM (Breakdown Maintenance) complaints 
        or reactive maintenance work orders.

        This tool retrieves breakdown complaints and work orders used to track
        response time, resolution time, and SLA violations.

        It supports filtering by:
        - User isolation (user_id)
        - Complaint lifecycle (status, stage, priority)
        - Complaint classification:
        - complaint_type
        - complaint_mode
        - complaint_nature
        - Work order and service classification (wo_type, service_type)
        - Organizational structure (division, discipline)
        - Location hierarchy (locality, building, floor)
        - Contract mapping
        - Assigned technicians (analysis_tech, execution_tech)
        - Complaint raised by (complainer)
        - Keyword search
        - Complaint raised date range
        - Complaint completion date range
        - Pagination support (limit, offset)

        This tool is mainly used to:
        - Track breakdown response and resolution SLAs
        - Identify overdue or escalated complaints
        - Analyze SLA violations by priority or technician
        - Support operational dashboards and real-time alerts

        Always use this tool when the query is about breakdown complaints,
        reactive maintenance, or SLA compliance related to failures.
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
    limit=None, offset=None 
) -> str:
    if not user_id:
        logger.error("❌ BDM called without user_id")
        return "Error: user_id is required. It is set from the authenticated request."
    
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
        "limit":limit,
        "offset": 0,  
    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    logger.debug("📤 BDM payload prepared: %s", clean_payload)

    try:
        logger.info("🚀 Sending BDM request to /get-bdm")
        
        response = requests.post(f"{settings.DATABASE_API_URL}/get-bdm", json=clean_payload)
        
        logger.info(
            "📥 BDM response received | status_code=%s",
            response.status_code
        )
        
        if response.status_code != 200:
            logger.error(
                "❌ BDM API error | status_code=%s | response=%s",
                response.status_code,
                response.text
            )
            return f"❌ API Error: {response.text}"

        response_json = response.json()
        
        logger.debug(
            "📦 BDM response data: %s",
            json.dumps(response_json, indent=2)
        )
        
        logger.info("✅ BDM data processed successfully")

        return json.dumps(response_json)
    
    except Exception as e:
        logger.error(f"❌ BDM tool error: {e}", exc_info=True)
        
        return f"Error calling BDM endpoint: {str(e)}"