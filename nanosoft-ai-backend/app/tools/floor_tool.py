import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import FloorRequest
from app.tools.tool_utils import getTime, logger
from app.api.routes.floor import get_floor

def FLOOR(
    user_name=None,
    user_id=None,
    floor_code=None,
    floor_name=None,
    building=None,
    building_code=None,
    locality=None,
    locality_code=None,
    is_active=None,
    is_draft=None,
    is_non_contract=None,
    is_default=None,
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
        logger.error("❌ FLOOR called without user_name")
        return "Error: user_name is required. It is set from the authenticated request."

    logger.info(f"📦 FLOOR TOOL TRIGGERED for user_name: {user_name}")
    
    resolved_date_from, resolved_date_to = getTime(date_from, date_to)
    
    payload = {
        "user_name": user_name,
        "user_id": user_id,
        "floor_code": floor_code,
        "floor_name": floor_name,
        "building": building,
        "building_code": building_code,
        "locality": locality,
        "locality_code": locality_code,
        "is_active": is_active,
        "is_draft": is_draft,
        "is_non_contract": is_non_contract,
        "is_default": is_default,
        "keyword": keyword,
        "date_from": resolved_date_from,
        "date_to": resolved_date_to,
        "limit": limit,
        "offset": 0,
        "is_aggregate": is_aggregate,
        "group_by_columns": group_by_columns,
        "aggregate_function": aggregate_function,
    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    if "offset" not in clean_payload:
        clean_payload["offset"] = 0
    if is_aggregate:
        logger.info("📊 AGGREGATE MODE | group_by=%s | function=%s", group_by_columns, aggregate_function)

    logger.info("📋 [FLOOR PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str, ensure_ascii=False))

    try:
        logger.info("🚀 Calling get_floor directly")
        req = FloorRequest(**clean_payload)
        result = get_floor(req)
        logger.info("✅ Floor data successfully processed")
        return json.dumps(result)
    except HTTPException as e:
        logger.error("❌ Floor API error: %s", e.detail)
        return f"❌ API Error: {e.detail}"
    except Exception as e:
        logger.error(f"❌ Floor tool error: {e}", exc_info=True)
        return f"Error calling floor: {str(e)}"
