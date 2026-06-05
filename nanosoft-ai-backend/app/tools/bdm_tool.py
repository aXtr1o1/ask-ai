from langchain.tools import tool
import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import *
from app.models.schemas import *
from app.tools.tool_utils import resolveDate, getTime, logger
from datetime import date, timedelta
from app.api.routes.bdm import get_bdm

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
LocalityName, LocalityCode, WoStatus, PriorityName, StageName,
ComplaintTypeName, ComplaintModeName, ServiceTypeName, SpotName, ContractName
ComplaintHeaderName


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
    locality_code=None,
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
        "locality_code":    locality_code,
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

    logger.info("📋 [BDM PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str, ensure_ascii=False))

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
    

 
