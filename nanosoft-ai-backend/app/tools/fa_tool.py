import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import *
from app.tools.tool_utils import getTime, logger
from app.api.routes.fa import get_fa

# FA — facility audit records (system-generated scheduled inspection complaints).
# Called directly with a pre-built payload (see langchain_service._run_module);
# no LLM tool-selection or args_schema involved.
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
 
 
