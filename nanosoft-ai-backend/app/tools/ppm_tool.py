import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import *
from app.tools.tool_utils import getTime, logger
from app.api.routes.ppm import get_ppm

# PPM — planned / preventive maintenance records and schedules.
# Called directly with a pre-built payload (see langchain_service._run_module);
# no LLM tool-selection or args_schema involved.
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


