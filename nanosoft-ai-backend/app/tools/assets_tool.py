from langchain.tools import tool
import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import *
from app.models.schemas import *
from app.tools.tool_utils import resolveDate, getTime, logger
from datetime import date, timedelta
from app.api.routes.assets import get_assets

# ✅ TOOL 1: ASSETS
# =====================================================
@tool(
    description="""
Use this tool for queries regarding physical equipment, master asset records, or metadata.

ROUTING RULE: Trigger this tool only for queries regarding physical equipment, master asset records, or equipment categories/locations. Do not use this tool for generic requests to list, show, or search general data unless the user explicitly mentions assets or equipment.

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
LocalityName, LocalityCode, StatusName, ConditionName, PriorityName,
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
    locality_code=None,
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
        "locality_code":    locality_code,
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
    

    logger.info("📋 [ASSETS PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str, ensure_ascii=False))

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


