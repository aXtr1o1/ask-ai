from langchain.tools import tool
import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import *
from app.models.schemas import *
from app.tools.tool_utils import resolveDate, getTime, logger
from datetime import date, timedelta
from app.api.routes.sb import get_sb

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
 
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AMBIGUOUS QUERIES — DO NOT ASK QUESTIONS:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# If user asks a generic maintenance query with NO SB/PPM keyword:
#   e.g. "how many scheduled tasks?" or "show maintenance work orders"
# → DO NOT call this tool. DO NOT ask the user any question.
#   The upstream routing system handles all clarification automatically.
#   Simply do NOT invoke any tool — return no tool call.
 
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
                    LocalityName, LocalityCode, PPMStageName, FrequencyName, ContractName, SpotName
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
    locality_code=None,
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
        "locality_code":    locality_code,
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
 
    logger.info("📋 [SB PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str, ensure_ascii=False))
 
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
