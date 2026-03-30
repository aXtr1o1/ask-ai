"""
LangChain Tools for Facility Management
"""
from langchain.tools import tool
import json
import logging

from app.models.schemas import AssetsInput, PPMInput, BDMInput
from fastapi import HTTPException
from app.api.models.schemas import AssetRequest, PPMRequest, BDMRequest
from app.api.routes.assets import get_assets
from app.api.routes.ppm import get_ppm
from app.api.routes.bdm import get_bdm
from datetime import date, timedelta



logger = logging.getLogger("facility_tools")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


def getTime(date_from, date_to):
    today = date.today()

    # Case 1: both dates missing → last 7 days
    if date_from is None and date_to is None:
        resolved_date_from = (today - timedelta(days=6)).isoformat()
        resolved_date_to = today.isoformat()
        logger.info(
            "📅 ASSETS: no dates provided → defaulting to last 7 days: %s to %s",
            resolved_date_from,
            resolved_date_to
        )

    # Case 2: only from date missing
    elif date_from is None:
        resolved_date_from = (today - timedelta(days=6)).isoformat()
        resolved_date_to = date_to

    # Case 3: only to date missing
    elif date_to is None:
        resolved_date_from = date_from
        resolved_date_to = today.isoformat()

    # Case 4: both dates provided
    else:
        resolved_date_from = date_from
        resolved_date_to = date_to

    return resolved_date_from, resolved_date_to


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
- division: Map if user mentions "Division", "Division Name", or "DivisionName".
- discipline: Map if user mentions "Discipline", "Discipline Name", or "DisciplineName".
- status: Map if user mentions "Status" or "Status Name".
- spot_name: Map if user mentions "Spot", "Spot Name", or "Location Spot".
- serial_no: Map if user mentions "Serial", "Serial No", "Serial Number", or "S/N".
- keyword: Mandatory fallback for any terms not labeled as a field.

FULL PARAMETER CAPABILITIES:
- user_name: Required for user isolation and ownership.
- status, condition, priority: Filter by current operational state.
- asset_type, division, discipline, trade_group: Filter by asset classification.
- locality, building, floor, service_area: Filter by physical location hierarchy.
- spot_name, serial_no: Filter by spot or serial number.
- on_hold, is_snagged, is_scraped: Filter by asset lifecycle flags.
- enable_ppm, enable_bdm: Filter by maintenance eligibility configuration.
- asset_tag_no, keyword: Filter by specific identification or search terms.
- date_from, date_to: Filter by asset creation or update timestamps.
- limit, offset: Control data pagination.

AGGREGATE / GROUP BY GUIDANCE:
═══════════════════════════════════════
When the user asks questions like:
- "how many assets per division?"
- "total assets by building and floor?"
- "breakdown of assets by condition?"
- "summarize assets by discipline?"
- "how many assets are in each status?"
- "compare assets by make or model?"
- "group assets by building and floor"

→ Set is_aggregate = True
→ Fill group_by_columns with the columns the user mentioned
   for example ["DivisionName"] or ["BuildingName", "FloorName"]
→ Set aggregate_function based on what user wants
   COUNT for how many, SUM for total of a value, AVG for average

IMPORTANT: Only set is_aggregate=True when user mentions a grouping column
like "per division", "by building", "each status". If user asks "how many total"
or "how many assets exist" with NO grouping column → set is_aggregate=False.

For all normal filter and list queries:
→ is_aggregate = False (default — do not set)
→ group_by_columns = None
→ aggregate_function = None

Columns you can use in group_by_columns for ASSETS:
DivisionName, DisciplineName, BuildingName, FloorName,
LocalityName, StatusName, ConditionName, PriorityName,
AssetTypeName, MakeName, ModelName, SpotName,
TradeGroupName, ServiceAreaName, YearOfManuf


""",
    args_schema=AssetsInput
)
def ASSETS(
    user_name=None,
    user_id=None,
    asset_tag_no=None,
    status=None,
    condition=None,
    priority=None,
    asset_type=None,
    division=None,
    discipline=None,
    locality=None,
    building=None,
    floor=None,
    owner=None,
    make=None,
    model=None,
    service_area=None,
    trade_group=None,
    spot_name=None,
    serial_no=None,
    on_hold=None,
    is_snagged=None,
    is_scraped=None,
    enable_ppm=None,
    enable_bdm=None,
    keyword=None,
    date_from=None,
    date_to=None,
    limit=None,
    offset=None,
    is_aggregate=False,
    group_by_columns=None,
    aggregate_function=None,

    
) -> str:
    if not user_name:
        logger.error("❌ ASSETS called without user_name")
        return "Error: user_name is required. It is set from the authenticated request."

    logger.info(f"📦 ASSETS TOOL TRIGGERED for user_name: {user_name}")
    
    resolved_date_from,resolved_date_to = getTime(date_from,date_to)
    
    payload = {
        "user_name":    user_name,
        "user_id":      user_id,
        "asset_tag_no": asset_tag_no,
        "status":       status,
        "condition":    condition,
        "priority":     priority,
        "asset_type":   asset_type,
        "division":     division,
        "discipline":   discipline,
        "locality":     locality,
        "building":     building,
        "floor":        floor,
        "owner":        owner,
        "make":         make,
        "model":        model,
        "service_area": service_area,
        "trade_group":  trade_group,
        "spot_name":    spot_name,
        "serial_no":    serial_no,
        "on_hold":      on_hold,
        "is_snagged":   is_snagged,
        "is_scraped":   is_scraped,
        "enable_ppm":   enable_ppm,
        "enable_bdm":   enable_bdm,
        "keyword":      keyword,
        "date_from":    resolved_date_from,
        "date_to":      resolved_date_to,
        "limit":        limit,
        "offset":       0,
        "is_aggregate":       is_aggregate,
        "group_by_columns":   group_by_columns,
        "aggregate_function": aggregate_function,

        
    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    if "offset" not in clean_payload:
        clean_payload["offset"] = 0
    #log when aggregate mode is triggered so you can debug easily
    if is_aggregate:
        logger.info("📊 AGGREGATE MODE | group_by=%s | function=%s", group_by_columns, aggregate_function)
    

    logger.info("📋 [ASSETS PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str))

    try:
        logger.info("🚀 Calling get_assets directly")
        req = AssetRequest(**clean_payload)
        result = get_assets(req)
        logger.info("✅ Assets data successfully processed")
        return json.dumps(result)
    except HTTPException as e:
        logger.error("❌ Assets API error: %s", e.detail)
        return f"❌ API Error: {e.detail}"
    except Exception as e:
        logger.error(f"❌ Assets tool error: {e}", exc_info=True)
        return f"Error calling assets: {str(e)}"


# =====================================================
# ✅ TOOL 2: PPM
# =====================================================
@tool(
    description="""
Use this tool specifically for Planned / Preventive Maintenance (PPM) records and schedules.

ROUTING RULE: Trigger this tool only if the user explicitly mentions maintenance schedules,
preventive tasks, PPM, or maintenance SLA compliance. Do not use for generic equipment lists.

MAPPING DIRECTIVES:
- division: Map if user mentions "Division", "Division Name", or "DivisionName".
- discipline: Map if user mentions "Discipline", "Discipline Name", or "DisciplineName".
- status: Map if user mentions "Status" or "Status Name".
- spot_name: Map if user mentions "Spot", "Spot Name", or "Location Spot".
- keyword: Mandatory fallback for any terms not labeled as a field.

FULL PARAMETER CAPABILITIES:
- user_name: Required for user isolation and ownership.
- work_order, asset_tag_no: Filter by specific work order or asset.
- status, stage: Filter by maintenance workflow or execution state.
- frequency: Filter by schedule intervals (e.g., daily, weekly, monthly).
- division, discipline: Filter by organizational structure.
- locality, building, floor, spot_name: Filter by location hierarchy.
- contract, tech, equipment: Filter by service provider, technician, or equipment.
- keyword: General search for maintenance tasks or asset types.
- date_from, date_to: Filter by planned or actual maintenance start dates.
- comp_from, comp_to: Filter by maintenance completion date ranges.
- sla_min, sla_max: Filter by SLA duration (in minutes).
- limit, offset: Control data pagination.

AGGREGATE / GROUP BY GUIDANCE:

When the user asks questions like:
- "how many PPM tasks per division?"
- "breakdown of PPM by frequency?"
- "summarize PPM by status?"
- "how many planned tasks per building?"
- "group PPM by discipline and stage?"

→ Set is_aggregate = True
→ Fill group_by_columns with the columns the user mentioned
→ Set aggregate_function based on what user wants
   COUNT for how many, SUM for total, AVG for average
   
IMPORTANT: Only set is_aggregate=True when user mentions a grouping column
like "per division", "by frequency", "each stage". If user asks "how many total"
or "how many PPM tasks exist" with NO grouping column → set is_aggregate=False

For all normal filter and list queries:
→ is_aggregate = False (default — do not set)
→ group_by_columns = None
→ aggregate_function = None

Columns you can use in group_by_columns for PPM:
DivisionName, DisciplineName, BuildingName, FloorName,
LocalityName, FrequencyName, PPMStatus, PPMStageName,
ContractName, SpotName

""",
    args_schema=PPMInput
)
def PPM(
    user_name=None,
    user_id=None,
    work_order=None,
    asset_tag_no=None,
    status=None,
    stage=None,
    frequency=None,
    division=None,
    discipline=None,
    locality=None,
    building=None,
    floor=None,
    contract=None,
    tech=None,
    equipment=None,
    spot_name=None,
    keyword=None,
    date_from=None,
    date_to=None,
    comp_from=None,
    comp_to=None,
    sla_min=None,
    sla_max=None,
    limit=None,
    offset=None,
    is_aggregate=False,
    group_by_columns=None,
    aggregate_function=None,

    
) -> str:
    if not user_name:
        logger.error("❌ PPM called without user_name")
        return "Error: user_name is required. It is set from the authenticated request."

    logger.info(f"🛠️ PPM TOOL TRIGGERED for user_name: {user_name}")
    resolved_date_from,resolved_date_to = getTime(date_from=date_from,date_to=date_to)

    payload = {
        "user_name":    user_name,
        "user_id":      user_id,
        "work_order":   work_order,
        "asset_tag_no": asset_tag_no,
        "status":       status,
        "stage":        stage,
        "frequency":    frequency,
        "division":     division,
        "discipline":   discipline,
        "locality":     locality,
        "building":     building,
        "floor":        floor,
        "contract":     contract,
        "tech":         tech,
        "equipment":    equipment,
        "spot_name":    spot_name,
        "keyword":      keyword,
        "date_from":    resolved_date_from,
        "date_to":      resolved_date_to,
        "comp_from":    comp_from,
        "comp_to":      comp_to,
        "sla_min":      sla_min,
        "sla_max":      sla_max,
        "limit":        limit,
        "offset":       0,
        "is_aggregate": is_aggregate,
        "group_by_columns":group_by_columns,
        "aggregate_function":aggregate_function,

    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    if "offset" not in clean_payload:
        clean_payload["offset"] = 0
    
    if is_aggregate:
        logger.info("📊 AGGREGATE MODE | group_by=%s | function=%s", group_by_columns, aggregate_function)

    logger.info("📋 [PPM PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str))

    try:
        logger.info("🚀 Calling get_ppm directly")
        req = PPMRequest(**clean_payload)
        result = get_ppm(req)
        logger.info("✅ PPM data processed successfully")
        return json.dumps(result)
    except HTTPException as e:
        logger.error("❌ PPM API error: %s", e.detail)
        return f"❌ API Error: {e.detail}"
    except Exception as e:
        logger.error(f"❌ PPM tool error: {e}", exc_info=True)
        return f"Error calling PPM: {str(e)}"


# =====================================================
# ✅ TOOL 3: BDM
# =====================================================
@tool(
    description="""
Use this tool for queries regarding BDM (Breakdown Maintenance) complaints or reactive work orders.

ROUTING RULE: Trigger this tool only if the user explicitly mentions breakdowns, complaints,
failures, reactive maintenance, or breakdown SLA compliance. Do not use for general equipment lists.

MAPPING DIRECTIVES:
- division: Map if user mentions "Division", "Division Name", or "DivisionName".
- discipline: Map if user mentions "Discipline", "Discipline Name", or "DisciplineName".
- status: Map if user mentions "Status" or "Status Name".
- spot_name: Map if user mentions "Spot", "Spot Name", or "Location Spot".
- keyword: Mandatory fallback for any terms not labeled as a field.

FULL PARAMETER CAPABILITIES:
- user_name: Required for user isolation and ownership.
- complaint_no: Filter by specific complaint number.
- status, stage, priority: Filter by complaint lifecycle and urgency.
- complaint_type, complaint_mode, complaint_nature: Filter by classification.
- wo_type, service_type: Filter by work order or service category.
- division, discipline: Filter by organizational structure.
- locality, building, floor, spot_name: Filter by location hierarchy.
- contract, analysis_tech, execution_tech: Filter by service provider or assigned staff.
- complainer: Filter by the individual who raised the complaint.
- keyword: General search for complaints or equipment issues.
- date_from, date_to: Filter by complaint registration date range.
- completed_from, completed_to: Filter by complaint resolution date range.
- limit, offset: Control data pagination.

AGGREGATE / GROUP BY GUIDANCE:
When the user asks questions like:
- "how many complaints per division?"
- "breakdown of complaints by priority?"
- "summarize BDM by status?"
- "how many breakdowns per building?"
- "group complaints by type and stage?"

→ Set is_aggregate = True
→ Fill group_by_columns with the columns the user mentioned
→ Set aggregate_function based on what user wants
   COUNT for how many, SUM for total, AVG for average
   
IMPORTANT: Only set is_aggregate=True when user mentions a grouping column
like "per division", "by priority", "each status". If user asks "how many total"
or "how many complaints exist" with NO grouping column → set is_aggregate=False.

For all normal filter and list queries:
→ is_aggregate = False (default — do not set)
→ group_by_columns = None
→ aggregate_function = None

Columns you can use in group_by_columns for BDM:
DivisionName, DisciplineName, BuildingName, FloorName,
LocalityName, WoStatus, PriorityName, StageName,
ComplaintTypeName, ComplaintModeName, SpotName, ContractName


""",
    args_schema=BDMInput
)
def BDM(
    user_name=None,
    user_id=None,
    complaint_no=None,
    status=None,
    priority=None,
    stage=None,
    complaint_type=None,
    complaint_mode=None,
    complaint_nature=None,
    wo_type=None,
    service_type=None,
    division=None,
    discipline=None,
    locality=None,
    building=None,
    floor=None,
    contract=None,
    analysis_tech=None,
    execution_tech=None,
    complainer=None,
    spot_name=None,
    keyword=None,
    date_from=None,
    date_to=None,
    completed_from=None,
    completed_to=None,
    limit=None,
    offset=None,
    is_aggregate=False,
    group_by_columns=None,
    aggregate_function=None
) -> str:
    if not user_name:
        logger.error("❌ BDM called without user_name")
        return "Error: user_name is required. It is set from the authenticated request."

    logger.info(f"🔧 BDM TOOL TRIGGERED for user_name: {user_name}")
    resolved_date_from,resolved_date_to = getTime(date_from,date_to)

    payload = {
        "user_name":        user_name,
        "user_id":      user_id,
        "complaint_no":     complaint_no,
        "status":           status,
        "priority":         priority,
        "stage":            stage,
        "complaint_type":   complaint_type,
        "complaint_mode":   complaint_mode,
        "complaint_nature": complaint_nature,
        "wo_type":          wo_type,
        "service_type":     service_type,
        "division":         division,
        "discipline":       discipline,
        "locality":         locality,
        "building":         building,
        "floor":            floor,
        "contract":         contract,
        "analysis_tech":    analysis_tech,
        "execution_tech":   execution_tech,
        "complainer":       complainer,
        "spot_name":        spot_name,
        "keyword":          keyword,
        "date_from":        resolved_date_from,
        "date_to":          resolved_date_to,
        "completed_from":   completed_from,
        "completed_to":     completed_to,
        "limit":            limit,
        "offset":           0,
        "is_aggregate":       is_aggregate,
        "group_by_columns":   group_by_columns,
        "aggregate_function": aggregate_function,

    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    if "offset" not in clean_payload:
        clean_payload["offset"] = 0
        
    if is_aggregate:
        logger.info("📊 AGGREGATE MODE | group_by=%s | function=%s", group_by_columns, aggregate_function)

    logger.info("📋 [BDM PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str))

    try:
        logger.info("🚀 Calling get_bdm directly")
        req = BDMRequest(**clean_payload)
        result = get_bdm(req)
        logger.info("✅ BDM data processed successfully")
        return json.dumps(result)
    except HTTPException as e:
        logger.error("❌ BDM API error: %s", e.detail)
        return f"❌ API Error: {e.detail}"
    except Exception as e:
        logger.error(f"❌ BDM tool error: {e}", exc_info=True)
        return f"Error calling BDM: {str(e)}"