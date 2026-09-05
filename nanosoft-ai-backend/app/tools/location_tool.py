import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import LocationRequest
from app.tools.tool_utils import getTime, logger
from app.api.routes.location import get_location

def LOCATION(
    user_name=None,
    user_id=None,
    locality_code=None,
    locality_name=None,
    city=None,
    city_code=None,
    locality_group=None,
    admin_locality_type=None,
    is_active=None,
    is_draft=None,
    is_portal_display=None,
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
        logger.error("❌ LOCATION called without user_name")
        return "Error: user_name is required. It is set from the authenticated request."

    logger.info(f"📦 LOCATION TOOL TRIGGERED for user_name: {user_name}")
    
    resolved_date_from, resolved_date_to = getTime(date_from, date_to)
    
    payload = {
        "user_name": user_name,
        "user_id": user_id,
        "locality_code": locality_code,
        "locality_name": locality_name,
        "city": city,
        "city_code": city_code,
        "locality_group": locality_group,
        "admin_locality_type": admin_locality_type,
        "is_active": is_active,
        "is_draft": is_draft,
        "is_portal_display": is_portal_display,
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

    logger.info("📋 [LOCATION PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str, ensure_ascii=False))

    try:
        logger.info("🚀 Calling get_location directly")
        req = LocationRequest(**clean_payload)
        result = get_location(req)
        logger.info("✅ Location data successfully processed")
        return json.dumps(result)
    except HTTPException as e:
        logger.error("❌ Location API error: %s", e.detail)
        return f"❌ API Error: {e.detail}"
    except Exception as e:
        logger.error(f"❌ Location tool error: {e}", exc_info=True)
        return f"Error calling location: {str(e)}"
