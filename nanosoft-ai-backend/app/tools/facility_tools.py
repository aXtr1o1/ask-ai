"""
LangChain Tools for Facility Management
"""
from langchain.tools import tool
import json
import logging

from app.models.schemas import AssetsInput, PPMInput, BDMInput
from fastapi import HTTPException
from app.api.models.schemas import AssetRequest, PPMRequest, BDMRequest
from app.models.schemas import FAInput, SBInput
from app.api.routes.assets import get_assets
from app.api.routes.ppm import get_ppm
from app.api.routes.bdm import get_bdm
from app.api.models.schemas import FARequest, SBRequest
from app.api.routes.fa import get_fa
from app.api.routes.sb import get_sb
from datetime import date, timedelta



logger = logging.getLogger("facility_tools")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


def resolveDate(date_value, fallback, is_end_date=False):
    """Resolve relative date keywords to actual dates."""
    if date_value is None:
        return None

    today = date.today()
    val = str(date_value).strip().lower()

    # ── Relative keyword resolution ──
    if val in ("today",):
        resolved = today.isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    if val in ("yesterday",):
        resolved = (today - timedelta(days=1)).isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    if val in ("this week", "thisweek"):
        if is_end_date:
            resolved = today.isoformat()
        else:
            resolved = (today - timedelta(days=today.weekday())).isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    if val in ("last week", "lastweek"):
        last_monday = today - timedelta(days=today.weekday() + 7)
        if is_end_date:
            resolved = (last_monday + timedelta(days=6)).isoformat()
        else:
            resolved = last_monday.isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    if val in ("this month", "thismonth"):
        if is_end_date:
            resolved = today.isoformat()
        else:
            resolved = today.replace(day=1).isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    if val in ("last month", "lastmonth"):
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        if is_end_date:
            resolved = last_month_end.isoformat()
        else:
            resolved = last_month_end.replace(day=1).isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    if val in ("this year", "thisyear"):
        if is_end_date:
            resolved = today.isoformat()
        else:
            resolved = today.replace(month=1, day=1).isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    # ── Dynamic pattern: X days/weeks/months/years ago/before ──
    import re
    match = re.search(r"(\d+)\s*(day|week|month|year)s?\s*(ago|before)", val)
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        
        if unit == "day":
            delta = timedelta(days=num)
        elif unit == "week":
            delta = timedelta(weeks=num)
        elif unit == "month":
            delta = timedelta(days=num * 30)
        elif unit == "year":
            delta = timedelta(days=num * 365)
        else:
            delta = timedelta(days=num)
            
        resolved = (today - delta).isoformat()
        logger.info("📅 Relative pattern '%s' → resolved to %s", date_value, resolved)
        return resolved

    # ── Validate actual date string ──
    try:
        from datetime import datetime
        datetime.strptime(date_value, "%Y-%m-%d").date()
        logger.info("📅 Date '%s' validated successfully", date_value)
        return date_value
    except Exception:
        logger.warning("⚠️ Invalid date format '%s' → using fallback %s", date_value, fallback)
        return fallback


def getTime(date_from, date_to):
    # today = date.today()
    # today_str = today.isoformat()
    # default_from = (today - timedelta(days=6)).isoformat()

    # ── Resolve relative keywords first ──
    # ✅ fallback=None means no default 7-day filter is applied
    date_from = resolveDate(date_from, fallback=None, is_end_date=False)
    date_to   = resolveDate(date_to,   fallback=None, is_end_date=True)

    # # Case 1: both dates missing → last 7 days (HASHED BY USER REQUEST)
    # if date_from is None and date_to is None:
    #     logger.info("📅 No dates provided → defaulting to last 7 days: %s to %s", default_from, today_str)
    #     return default_from, today_str

    # # Case 2: only from date missing
    # elif date_from is None:
    #     logger.info("📅 date_from missing → defaulting to 7 days before date_to: %s to %s", default_from, date_to)
    #     return default_from, date_to

    # # Case 3: only to date missing
    # elif date_to is None:
    #     logger.info("📅 date_to missing → defaulting to today: %s to %s", date_from, today_str)
    #     return date_from, today_str

    # Case 4: Return resolved values
    logger.info("📅 Date Resolution (No Default) | from: %s -> %s | to: %s -> %s", date_from, date_from, date_to, date_to)
    return date_from, date_to


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
- keyword: General text search when a value does not map cleanly to another field.

FULL PARAMETER CAPABILITIES:
- user_name: Required for user isolation and ownership.
- status, condition, priority: Filter by current operational state.
- asset_type, division, discipline, trade_group: Filter by asset classification.
- locality, building, floor, service_area: Filter by physical location hierarchy.
- spot_name, serial_no: Filter by spot or serial number.
- on_hold, is_snagged, is_scraped: FILTER by specific boolean value. For "how many OnHolds" breakdown use is_aggregate=True with group_by_columns=['OnHold'] instead.
- enable_ppm, enable_bdm: Filter by maintenance eligibility configuration.
- asset_tag_no, keyword: Filter by specific identification or search terms. DO NOT include conversational stop-words, prepositions, articles, or time/date references as keywords.
- date_from, date_to: Filter by timestamps. Supports relative keywords: 'today', 'yesterday', 'this week', 'last week', 'this month', 'last month', 'this year', 'last year', or 'X days ago' (e.g., '3 days ago').
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
- "how many OnHolds are there?" / "how many on hold?" / "OnHold breakdown"
- "how many snagged assets?" / "how many scraped?" / "PPM enabled count"

→ Set is_aggregate = True
→ Fill group_by_columns with the columns the user mentioned
   for example ["DivisionName"] or ["BuildingName", "FloorName"] or ["OnHold"]
→ Set aggregate_function based on what user wants
   COUNT for how many, SUM for total of a value, AVG for average

COLUMN VALUE BREAKDOWN (CRITICAL):
When user asks "how many [ColumnName]?" or "how many [column] are there?" about a
data column — especially boolean columns (OnHold, IsSnagged, IsScraped, EnablePPM,
EnableBDM) or categorical columns (StatusName, ConditionName, etc.) — treat it as
aggregate: is_aggregate=True, group_by_columns=[exact DB column name], aggregate_function="COUNT".
Do NOT set the corresponding filter parameter (e.g., do NOT set on_hold=true).
The result should show count per distinct value (true/false for booleans).

Use FILTER (not aggregate) only when user specifies ONE value:
- "how many assets on hold" → on_hold=true, is_aggregate=False
- "show snagged assets" → is_snagged=true, is_aggregate=False

IMPORTANT: Only set is_aggregate=True when user mentions a grouping column
like "per division", "by building", "each status", or asks "how many [columnName]".
If user asks "how many total" or "how many assets exist" with NO grouping column
→ set is_aggregate=False.

For all normal filter and list queries:
→ is_aggregate = False (default — do not set)
→ group_by_columns = None
→ aggregate_function = None

Columns you can use in group_by_columns for ASSETS:
DivisionName, DisciplineName, BuildingName, FloorName,
LocalityName, StatusName, ConditionName, PriorityName,
AssetTypeName, EquipmentName, MakeName, ModelName, SpotName,
TradeGroupName, ServiceAreaName, YearOfManuf,
OnHold, IsSnagged, IsScraped, EnablePPM, EnableBDM


""",
    args_schema=AssetsInput
)
def ASSETS(
    user_name=None,
    user_id=None,
    asset_tag_no=None,
    asset_barcode=None,
    equipment_name=None,
    equipment_ref_no=None,
    serial_no=None,
    status=None,
    condition=None,
    priority=None,
    asset_type=None,
    division=None,
    discipline=None,
    locality=None,
    building=None,
    floor=None,
    spot_name=None,
    owner=None,
    make=None,
    model=None,
    service_area=None,
    trade_group=None,
    drawing_no=None,
    remarks=None,
    on_hold=None,
    is_snagged=None,
    is_scraped=None,
    enable_ppm=None,
    enable_bdm=None,
    enable_bms=None,
    enable_dsm=None,
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
    
    resolved_date_from, resolved_date_to = getTime(date_from, date_to)
    
    payload = {
        "user_name":    user_name,
        "user_id":      user_id,
        "asset_tag_no": asset_tag_no,
        "asset_barcode": asset_barcode,
        "equipment_name": equipment_name,
        "equipment_ref_no": equipment_ref_no,
        "serial_no":    serial_no,
        "status":       status,
        "condition":    condition,
        "priority":     priority,
        "asset_type":   asset_type,
        "division":     division,
        "discipline":   discipline,
        "locality":     locality,
        "building":     building,
        "floor":        floor,
        "spot_name":    spot_name,
        "owner":        owner,
        "make":         make,
        "model":        model,
        "service_area": service_area,
        "trade_group":  trade_group,
        "drawing_no":   drawing_no,
        "remarks":      remarks,
        "on_hold":      on_hold,
        "is_snagged":   is_snagged,
        "is_scraped":   is_scraped,
        "enable_ppm":   enable_ppm,
        "enable_bdm":   enable_bdm,
        "enable_bms":   enable_bms,
        "enable_dsm":   enable_dsm,
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
- keyword: General text search when a value does not map cleanly to another field.

FULL PARAMETER CAPABILITIES:
- user_name: Required for user isolation and ownership.
- work_order, asset_tag_no: Filter by specific work order or asset.
- status, stage: Filter by maintenance workflow or execution state.
- frequency: Filter by schedule intervals (e.g., daily, weekly, monthly).
- division, discipline: Filter by organizational structure.
- locality, building, floor, spot_name: Filter by location hierarchy.
- contract, tech, equipment: Filter by service provider, technician, or equipment.
- keyword: General search for maintenance tasks or asset types. DO NOT include conversational stop-words, prepositions, articles, or time/date references as keywords.
- date_from, date_to: Filter by timestamps. Supports relative keywords: 'today', 'yesterday', 'this week', 'last week', 'this month', 'last month', 'this year', 'last year', or 'X days ago' (e.g., '3 days ago').
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

COLUMN VALUE BREAKDOWN: "how many [ColumnName]?" → is_aggregate=True,
group_by_columns=[column], do NOT set the filter parameter.

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
    equipment_ref_no=None,
    status=None,
    stage=None,
    frequency=None,
    division=None,
    discipline=None,
    locality=None,
    building=None,
    floor=None,
    spot_name=None,
    equipment=None,
    contract=None,
    tech=None,
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
    
    resolved_date_from, resolved_date_to = getTime(date_from, date_to)

    payload = {
        "user_name":    user_name,
        "user_id":      user_id,
        "work_order":   work_order,
        "asset_tag_no": asset_tag_no,
        "equipment_ref_no": equipment_ref_no,
        "status":       status,
        "stage":        stage,
        "frequency":    frequency,
        "division":     division,
        "discipline":   discipline,
        "locality":     locality,
        "building":     building,
        "floor":        floor,
        "spot_name":    spot_name,
        "equipment":    equipment,
        "contract":     contract,
        "tech":         tech,
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
- service_type vs division (CRITICAL): "... Services" (e.g. Electrical Services, Housekeeping Services)
  → service_type. "... System" or explicit "division" → division. Never map "Housekeeping Services"
  to division Housekeeping. Compare two Services types → is_aggregate=True, group_by_columns=['ServiceTypeName'].
- service_type: Map for "Service Type" or any "<trade> Services" phrase.
- division: Map ONLY when the user explicitly uses the word "Division" or explicitly names a building system like "Fire System" or "Cooling System". NEVER map entire sentences or conversational phrases like "in the system".
- discipline: Map only for "Discipline" or short trade names — not full Services/System names.
- status: Map if user mentions "Status" or "Status Name".
- spot_name: Map if user mentions "Spot", "Spot Name", or "Location Spot".
- keyword: General text search when a value does not map cleanly to another field.

FULL PARAMETER CAPABILITIES:
- user_name: Required for user isolation and ownership.
- complaint_no: Filter by specific complaint number.
- status, stage, priority: Filter by complaint lifecycle and urgency.
- complaint_type: e.g. "Service Request", "Corrective Maintenance" — NOT workflow stage text.
- complaint_header: e.g. "ANA Approval Flow", "Without Approval Flow" — map "under ANA Approval Flow" here, NOT stage.
- complaint_mode, complaint_nature: Filter by classification.
- Do NOT set stage, complaint_type, complaint_header, and keyword together for one phrase — use the single best field.
- wo_type, service_type: Filter by work order or service category.
- division, discipline: Filter by organizational structure.
- locality, building, floor, spot_name: Filter by location hierarchy.
- contract, analysis_tech, execution_tech: Filter by service provider or assigned staff.
- complainer: Filter by the individual who raised the complaint.
- keyword: General search. DO NOT include conversational stop-words, prepositions, articles, or time/date references as keywords.
- date_from, date_to: Filter by timestamps. Supports relative keywords: 'today', 'yesterday', 'this week', 'last week', 'this month', 'last month', 'this year', 'last year', or 'X days ago' (e.g., '3 days ago').
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

COLUMN VALUE BREAKDOWN: "how many [ColumnName]?" → is_aggregate=True,
group_by_columns=[column], do NOT set the filter parameter.

IMPORTANT: Only set is_aggregate=True when user mentions a grouping column
like "per division", "by priority", "each status", or "BuildingName" breakdown.
"low count" / "lowest count" = smallest numeric counts — do NOT set priority.
Only set priority for P1–P4 or explicit "low priority" / "critical".
If user asks "how many total" with NO grouping column → set is_aggregate=False.

For all normal filter and list queries:
→ is_aggregate = False (default — do not set)
→ group_by_columns = None
→ aggregate_function = None

Columns you can use in group_by_columns for BDM:
DivisionName, DisciplineName, BuildingName, FloorName,
LocalityName, WoStatus, PriorityName, StageName,
ComplaintTypeName, ComplaintModeName, ServiceTypeName, SpotName, ContractName


""",
    args_schema=BDMInput
)
def BDM(
    user_name=None,
    user_id=None,
    complaint_no=None,
    asset_tag_no=None,
    asset_barcode=None,
    client_wo_no=None,
    status=None,
    priority=None,
    stage=None,
    complaint_type=None,
    complaint_header=None,
    complaint_mode=None,
    complaint_nature=None,
    wo_type=None,
    service_type=None,
    division=None,
    discipline=None,
    locality=None,
    building=None,
    floor=None,
    spot_name=None,
    contract=None,
    complainer=None,
    register_by=None,
    analysis_tech=None,
    execution_tech=None,
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
    resolved_date_from, resolved_date_to = getTime(date_from, date_to)

    payload = {
        "user_name":        user_name,
        "user_id":      user_id,
        "complaint_no":     complaint_no,
        "asset_tag_no":     asset_tag_no,
        "asset_barcode":    asset_barcode,
        "client_wo_no":     client_wo_no,
        "status":           status,
        "priority":         priority,
        "stage":            stage,
        "complaint_type":   complaint_type,
        "complaint_header": complaint_header,
        "complaint_mode":   complaint_mode,
        "complaint_nature": complaint_nature,
        "wo_type":          wo_type,
        "service_type":     service_type,
        "division":         division,
        "discipline":       discipline,
        "locality":         locality,
        "building":         building,
        "floor":            floor,
        "spot_name":        spot_name,
        "contract":         contract,
        "complainer":       complainer,
        "register_by":      register_by,
        "analysis_tech":    analysis_tech,
        "execution_tech":   execution_tech,
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
    

 
# =====================================================
# ✅ TOOL 4: FA — Facility Audit
# =====================================================
@tool(
    description="""
Use this tool ONLY for Facility Audit (FA) records — system-generated scheduled inspection complaints.
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT ROUTING RULE — WHEN TO USE THIS TOOL:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 USE this tool when user mentions ANY of these:
  - "FA", "facility audit", "audit complaints", "audit requests"
  - "pest control", "pest control checks", "rodent activity", "RODENT ACTIVITY"
  - "facility audit request raised" (stage name)
  - "scheduled inspection complaints"
  - "system-generated complaints"
  - "housekeeping audit", "audit category", "audit sub-category"
  - "how many FA", "show FA", "list FA"
 
 NEVER use this tool when user mentions:
  - "breakdown", "heater", "HVAC failure", "equipment fault"
  - "who reported", "complainer", "tenant complaint"
  - "reactive maintenance", "corrective maintenance"
  - "BDM", "breakdown complaint"
  - "PPM", "preventive maintenance", "scheduled maintenance"
  - "SB", "schedule based", "work order AA-"
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEY DIFFERENTIATORS vs BDM:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FA = System-generated audit | No human complainer | Has category/sub-category
  BDM = Human-reported breakdown | Has complainer | Has complaint type/mode
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AMBIGUOUS QUERIES — DO NOT GUESS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If user asks a generic complaint question with NO FA/BDM keyword:
  e.g. "how many complaints are raised?" or "show all complaints"
→ DO NOT call this tool. Ask the user:
  "Do you mean Facility Audit (FA) complaints or Breakdown Maintenance (BDM) complaints?"
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PARAMETERS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- user_name: Always required (from authenticated session)
- complaint_no: FA complaint number
- priority: e.g. "P2 High"
- stage: RMStageName only (no status field). User 'Closed'/'Open' → stage='Closed' or 'Open' (not category)
- category: e.g. "Pest Control Checks"
- category_sub: e.g. "RODENT ACTIVITY"
- division: e.g. "Housekeeping"
- locality, building, floor, spot_name: Location filters
- contract: Contract name
- tech: Technician name
- frequency: e.g. "MONTHLY", "WEEKLY"
- request_desc: e.g. "Pest Control"
- is_withdraw, is_rework, is_active: Boolean flags
- keyword: General search. DO NOT include conversational stop-words, prepositions, articles, or time/date references as keywords.
- date_from, date_to: Filter by timestamps. Supports relative keywords: 'today', 'yesterday', 'this week', 'last week', 'this month', 'last month', 'this year', 'last year', or 'X days ago' (e.g., '3 days ago').
- comp_from, comp_to: Completion date range
- limit, offset: Pagination
 
AGGREGATE / GROUP BY:
- is_aggregate=True for "how many FA per division", "breakdown by audit category", "BuildingName" counts
- "BuildingName Category" / "building categories" → group_by_columns=['BuildingName'] — NOT category/RMCategoryName
- "audit category" / "Pest Control" → group_by_columns=['RMCategoryName'] or category filter
- "low count" / "lowest" = smallest counts — do NOT set priority unless user says P4 / low priority
- group_by_columns: DivisionName, BuildingName, FloorName, LocalityName,
                    PriorityName, RMStageName, RMCategoryName, RMCategorySubName,
                    FrequencyName, ContractName, SpotName,
                    IsWithdraw, IsRework, IsActive
- aggregate_function: COUNT / SUM / AVG
- COLUMN VALUE BREAKDOWN: "how many [columnName]?" → is_aggregate=True, group_by_columns=[column], do NOT set filter
""",
    args_schema=FAInput
)
def FA(
    user_name=None,
    user_id=None,
    complaint_no=None,
    complaint_code=None,
    x_complaint_no=None,
    priority=None,
    stage=None,
    category=None,
    category_sub=None,
    division=None,
    locality=None,
    building=None,
    floor=None,
    spot_name=None,
    contract=None,
    tech=None,
    frequency=None,
    request_desc=None,
    is_withdraw=None,
    is_rework=None,
    is_bms=None,
    is_active=None,
    is_draft=None,
    keyword=None,
    date_from=None,
    date_to=None,
    comp_from=None,
    comp_to=None,
    limit=None,
    offset=None,
    is_aggregate=False,
    group_by_columns=None,
    aggregate_function=None,
) -> str:
    if not user_name:
        logger.error("❌ FA called without user_name")
        return "Error: user_name is required."
 
    logger.info(f"📋 FA TOOL TRIGGERED for user_name: {user_name}")

    # ✅ Use shared getTime so relative keywords resolve correctly
    resolved_date_from, resolved_date_to = getTime(date_from, date_to)
 
    payload = {
        "user_name":          user_name,
        "user_id":            user_id,
        "complaint_no":       complaint_no,
        "complaint_code":     complaint_code,
        "x_complaint_no":     x_complaint_no,
        "priority":           priority,
        "stage":              stage,
        "category":           category,
        "category_sub":       category_sub,
        "division":           division,
        "locality":           locality,
        "building":           building,
        "floor":              floor,
        "spot_name":          spot_name,
        "contract":           contract,
        "tech":               tech,
        "frequency":          frequency,
        "request_desc":       request_desc,
        "is_withdraw":        is_withdraw,
        "is_rework":          is_rework,
        "is_bms":             is_bms,
        "is_active":          is_active,
        "is_draft":           is_draft,
        "keyword":            keyword,
        "date_from":          resolved_date_from,
        "date_to":            resolved_date_to,
        "comp_from":          comp_from,
        "comp_to":            comp_to,
        "limit":              limit,
        "offset":             0,
        "is_aggregate":       is_aggregate,
        "group_by_columns":   group_by_columns,
        "aggregate_function": aggregate_function,
    }
 
    clean_payload = {k: v for k, v in payload.items() if v is not None}
    if "offset" not in clean_payload:
        clean_payload["offset"] = 0
 
    if is_aggregate:
        logger.info("📊 FA AGGREGATE MODE | group_by=%s | function=%s", group_by_columns, aggregate_function)
 
    logger.info("📋 [FA PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str))
 
    try:
        req    = FARequest(**clean_payload)
        result = get_fa(req)
        logger.info("✅ FA data successfully processed")
        return json.dumps(result)
    except HTTPException as e:
        logger.error("❌ FA API error: %s", e.detail)
        return f"❌ API Error: {e.detail}"
    except Exception as e:
        logger.error(f"❌ FA tool error: {e}", exc_info=True)
        return f"Error calling FA: {str(e)}"
 
 
# =====================================================
# ✅ TOOL 5: SB — Schedule Based
# =====================================================
@tool(
    description="""
Use this tool ONLY for Schedule Based (SB) maintenance work orders — system-generated scheduled service work orders.
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT ROUTING RULE — WHEN TO USE THIS TOOL:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
USE this tool when user mentions ANY of these:
  - "SB", "schedule based", "schedule-based work orders"
  - "SB work orders", "scheduled work orders"
  - work order numbers like "AA-1-2026" (format: code-number-year)
  - "environmental services work orders", "landscaping work orders"
  - "staff yet to be allocated" (SB stage name)
  - "how many SB", "show SB", "list SB work orders"
  - "service type" work orders (Environmental Services, Landscaping)
 
  NEVER use this tool when user mentions:
  - "PPM", "preventive maintenance", "planned maintenance", "chiller inspection"
  - "breakdown", "complaint", "heater", "equipment failure"
  - "FA", "facility audit", "pest control audit", "rodent activity"
  - "BDM", "corrective maintenance"
  - "asset", "equipment tag", "barcode"
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEY DIFFERENTIATORS vs PPM:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SB = Schedule-based work orders | Has ServiceTypeName | Has DisciplineName
       Work order format: AA-1-2026 | No asset tag linked
  PPM = Preventive maintenance | Has AssetTagNo | Has equipment name
        Work order format: AMC-2023-0002-RAE-19366-2025
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AMBIGUOUS QUERIES — DO NOT GUESS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If user asks a generic maintenance query with NO SB/PPM keyword:
  e.g. "how many scheduled tasks?" or "show maintenance work orders"
→ DO NOT call this tool. Ask the user:
  "Do you mean PPM (Preventive Maintenance) work orders or SB (Schedule Based) work orders?"
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PARAMETERS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- user_name: Always required (from authenticated session)
- work_order: Work order number e.g. "AA-1-2026"
- asset_tag_no: Asset tag number if linked to an asset
- status: SB work order status e.g. "Completed", "Pending"
- stage: Workflow stage e.g. "Staff Yet to be Allocated"
- frequency: Schedule frequency e.g. "MONTHLY"
- division: e.g. "Environmental Services"
- discipline: e.g. "Landscaping"
- locality, building, floor, spot_name: Location filters
- contract: Contract name
- tech: Technician name
- equipment: Equipment name
- sla_min, sla_max: SLA duration range in minutes
- keyword: General search. DO NOT include conversational stop-words, prepositions, articles, or time/date references as keywords.
- date_from, date_to: Filter by timestamps. Supports relative keywords: 'today', 'yesterday', 'this week', 'last week', 'this month', 'last month', 'this year', 'last year', or 'X days ago' (e.g., '3 days ago').
- comp_from, comp_to: Completion date range
- limit, offset: Pagination
 
AGGREGATE / GROUP BY:
- is_aggregate=True for "how many SB per division", "breakdown by frequency"
- group_by_columns: DivisionName, DisciplineName, BuildingName, FloorName,
                    LocalityName, PPMStageName, FrequencyName, ContractName, SpotName
- aggregate_function: COUNT / SUM / AVG
- COLUMN VALUE BREAKDOWN: "how many [columnName]?" → is_aggregate=True, group_by_columns=[column], do NOT set filter
""",
    args_schema=SBInput
)
def SB(
    user_name=None,
    user_id=None,
    work_order=None,
    stage=None,
    frequency=None,
    service_type=None,
    division=None,
    discipline=None,
    locality=None,
    building=None,
    floor=None,
    spot_name=None,
    contract=None,
    tech=None,
    is_withdraw=None,
    is_reschedule=None,
    is_rework=None,
    is_active=None,
    is_draft=None,
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
        logger.error("❌ SB called without user_name")
        return "Error: user_name is required."
 
    logger.info(f"🗓️ SB TOOL TRIGGERED for user_name: {user_name}")

    # ✅ Use shared getTime so relative keywords resolve correctly
    resolved_date_from, resolved_date_to = getTime(date_from, date_to)
 
    payload = {
        "user_name":          user_name,
        "user_id":            user_id,
        "work_order":         work_order,
        "stage":              stage,
        "frequency":          frequency,
        "service_type":       service_type,
        "division":           division,
        "discipline":         discipline,
        "locality":           locality,
        "building":           building,
        "floor":              floor,
        "spot_name":          spot_name,
        "contract":           contract,
        "tech":               tech,
        "is_withdraw":        is_withdraw,
        "is_reschedule":      is_reschedule,
        "is_rework":          is_rework,
        "is_active":          is_active,
        "is_draft":           is_draft,
        "keyword":            keyword,
        "date_from":          resolved_date_from,
        "date_to":            resolved_date_to,
        "comp_from":          comp_from,
        "comp_to":            comp_to,
        "sla_min":            sla_min,
        "sla_max":            sla_max,
        "limit":              limit,
        "offset":             0,
        "is_aggregate":       is_aggregate,
        "group_by_columns":   group_by_columns,
        "aggregate_function": aggregate_function,
    }
 
    clean_payload = {k: v for k, v in payload.items() if v is not None}
    if "offset" not in clean_payload:
        clean_payload["offset"] = 0
 
    if is_aggregate:
        logger.info("📊 SB AGGREGATE MODE | group_by=%s | function=%s", group_by_columns, aggregate_function)
 
    logger.info("📋 [SB PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str))
 
    try:
        req    = SBRequest(**clean_payload)
        result = get_sb(req)
        logger.info("✅ SB data successfully processed")
        return json.dumps(result)
    except HTTPException as e:
        logger.error("❌ SB API error: %s", e.detail)
        return f"❌ API Error: {e.detail}"
    except Exception as e:
        logger.error(f"❌ SB tool error: {e}", exc_info=True)
        return f"Error calling SB: {str(e)}"