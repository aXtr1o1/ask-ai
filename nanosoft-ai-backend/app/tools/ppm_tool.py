from langchain.tools import tool
import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import *
from app.models.schemas import *
from app.tools.tool_utils import resolveDate, getTime, logger
from datetime import date, timedelta
from app.api.routes.ppm import get_ppm

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
LocalityName, LocalityCode, FrequencyName, PPMStatus, PPMStageName,
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
    locality_code=None,
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
        "locality_code":    locality_code,
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

    logger.info("📋 [PPM PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str, ensure_ascii=False))

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


