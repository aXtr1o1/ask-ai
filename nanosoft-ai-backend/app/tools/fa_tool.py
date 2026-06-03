from langchain.tools import tool
import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import *
from app.models.schemas import *
from app.tools.tool_utils import resolveDate, getTime, logger
from datetime import date, timedelta
from app.api.routes.fa import get_fa

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
 
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AMBIGUOUS QUERIES — DO NOT ASK QUESTIONS:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# If user asks a generic complaint question with NO FA/BDM keyword:
#   e.g. "how many complaints are raised?" or "show all complaints"
# → DO NOT call this tool. DO NOT ask the user any question.
#   The upstream routing system handles all clarification automatically.
#   Simply do NOT invoke any tool — return no tool call.
 
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
- group_by_columns: DivisionName, BuildingName, FloorName, LocalityName, LocalityCode,
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
    locality_code=None,
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
        "locality_code":    locality_code,
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
 
    logger.info("📋 [FA PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str, ensure_ascii=False))
 
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
 
 
