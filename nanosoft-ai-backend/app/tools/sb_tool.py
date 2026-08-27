import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import *
from app.tools.tool_utils import getTime, logger
from app.api.routes.sb import get_sb

# SB — schedule-based maintenance work orders (system-generated scheduled service work orders).
# Called directly with a pre-built payload (see langchain_service._run_module);
# no LLM tool-selection or args_schema involved.
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
