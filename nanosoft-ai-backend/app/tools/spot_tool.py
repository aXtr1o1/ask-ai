import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import SpotRequest
from app.tools.tool_utils import getTime, logger
from app.api.routes.spot import get_spot

def SPOT(
    user_name=None,
    user_id=None,
    spot_code=None,
    spot_name=None,
    building=None,
    building_code=None,
    floor=None,
    locality=None,
    locality_code=None,
    spot_type=None,
    is_active=None,
    is_draft=None,
    is_occupied=None,
    is_parking=None,
    is_allocated=None,
    is_non_contract=None,
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
        logger.error("❌ SPOT called without user_name")
        return "Error: user_name is required. It is set from the authenticated request."

    logger.info(f"📦 SPOT TOOL TRIGGERED for user_name: {user_name}")
    
    resolved_date_from, resolved_date_to = getTime(date_from, date_to)
    
    payload = {
        "user_name": user_name,
        "user_id": user_id,
        "spot_code": spot_code,
        "spot_name": spot_name,
        "building": building,
        "building_code": building_code,
        "floor": floor,
        "locality": locality,
        "locality_code": locality_code,
        "spot_type": spot_type,
        "is_active": is_active,
        "is_draft": is_draft,
        "is_occupied": is_occupied,
        "is_parking": is_parking,
        "is_allocated": is_allocated,
        "is_non_contract": is_non_contract,
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

    logger.info("📋 [SPOT PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str, ensure_ascii=False))

    try:
        logger.info("🚀 Calling get_spot directly")
        req = SpotRequest(**clean_payload)
        result = get_spot(req)
        logger.info("✅ Spot data successfully processed")
        return json.dumps(result)
    except HTTPException as e:
        logger.error("❌ Spot API error: %s", e.detail)
        return f"❌ API Error: {e.detail}"
    except Exception as e:
        logger.error(f"❌ Spot tool error: {e}", exc_info=True)
        return f"Error calling spot: {str(e)}"
