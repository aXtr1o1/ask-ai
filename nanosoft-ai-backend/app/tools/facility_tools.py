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
       Use this tool for queries regarding physical equipment, master asset records, or metadata.
        
        DEFAULT ROUTING RULE: Trigger this tool for any general request to list, show, or search 
        categories of equipment or locations. Do not use PPM or BDM tools unless the user 
        explicitly mentions maintenance schedules, service complaints, or breakdowns.

        MAPPING DIRECTIVES:
        - division: Map if user mentions "Division", "Division Name", or "DivisionName". Matches p_division.
        - discipline: Map if user mentions "Discipline", "Discipline Name", or "DisciplineName". Matches p_discipline.
        - status: Map if user mentions "Status" or "Status Name".
        - keyword: Mandatory fallback for terms, equipment types, or manufacturers not explicitly labeled. Matches p_keyword.
        
        FULL PARAMETER CAPABILITIES:
        - user_id: Required for user isolation and ownership.
        - status, condition, priority: Filter by current operational state.
        - asset_type, division, discipline, trade_group: Filter by asset classification.
        - locality, building, floor, service_area: Filter by physical location hierarchy.
        - on_hold, is_snagged, is_scraped: Filter by asset lifecycle flags.
        - enable_ppm, enable_bdm: Filter by maintenance eligibility configuration.
        - asset_tag_no, barcode, keyword: Filter by specific identification or search terms.
        - date_from, date_to: Filter by asset creation or update timestamps.
        - limit, offset: Control data pagination.
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
        "status": status, "condition": condition, "priority": priority,
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
    

    formatted_payload = json.dumps(clean_payload, indent=2, default=str)
    logger.info(" [ALLOCATED PAYLOAD FROM AI]:\n%s", formatted_payload)

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
       Use this tool specifically for Planned / Preventive Maintenance (PPM) records and schedules.
        
        ROUTING RULE: Trigger this tool only if the user explicitly mentions maintenance schedules, 
        preventive tasks, PPM, or maintenance SLA compliance. Do not use for generic equipment lists.

        MAPPING DIRECTIVES:
        - division: Map if user mentions "Division", "Division Name", or "DivisionName". Matches p_division.
        - discipline: Map if user mentions "Discipline", "Discipline Name", or "DisciplineName". Matches p_discipline.
        - status: Map if user mentions "Status" or "Status Name".
        - keyword: Mandatory fallback for terms, equipment types, or manufacturers not explicitly labeled. Matches p_keyword.
        
        FULL PARAMETER CAPABILITIES:
        - user_id: Required for user isolation and ownership.
        - status, stage: Filter by maintenance workflow or execution state.
        - frequency: Filter by schedule intervals (e.g., daily, weekly, monthly).
        - division, discipline: Filter by organizational structure.
        - locality, building, floor: Filter by location hierarchy.
        - contract, tech: Filter by service provider or assigned technician.
        - keyword: General search for maintenance tasks or asset types.
        - date_from, date_to: Filter by planned or actual maintenance start dates.
        - comp_from, comp_to: Filter by maintenance completion date ranges.
        - sla_min, sla_max: Filter by SLA duration (in minutes).
        - limit, offset: Control data pagination.
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
    
    formatted_ppm_payload = json.dumps(clean_payload, indent=2, default=str)
    logger.info("[PPM ALLOCATED PAYLOAD FROM AI]:\n%s", formatted_ppm_payload)
    

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
       Use this tool for queries regarding BDM (Breakdown Maintenance) complaints or reactive work orders.
        
        ROUTING RULE: Trigger this tool only if the user explicitly mentions breakdowns, complaints, 
        failures, reactive maintenance, or breakdown SLA compliance. Do not use for general equipment lists.

        MAPPING DIRECTIVES:
        - division: Map if user mentions "Division", "Division Name", or "DivisionName". Matches p_division.
        - discipline: Map if user mentions "Discipline", "Discipline Name", or "DisciplineName". Matches p_discipline.
        - status: Map if user mentions "Status" or "Status Name".
        - keyword: Mandatory fallback for terms, equipment types, or manufacturers not explicitly labeled. Matches p_keyword.
        
        FULL PARAMETER CAPABILITIES:
        - user_id: Required for user isolation and ownership.
        - status, stage, priority: Filter by complaint lifecycle and urgency.
        - complaint_type, complaint_mode, complaint_nature: Filter by classification.
        - wo_type, service_type: Filter by work order or service category.
        - division, discipline: Filter by organizational structure.
        - locality, building, floor: Filter by location hierarchy.
        - contract, analysis_tech, execution_tech: Filter by service provider or assigned staff.
        - complainer: Filter by the individual who raised the complaint.
        - keyword: General search for complaints or equipment issues.
        - date_from, date_to: Filter by complaint registration date range.
        - completed_from, completed_to: Filter by complaint resolution date range.
        - limit, offset: Control data pagination.
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
    formatted_bdm_payload = json.dumps(clean_payload, indent=2, default=str)
    logger.info(" [BDM ALLOCATED PAYLOAD FROM AI]:\n%s", formatted_bdm_payload)

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