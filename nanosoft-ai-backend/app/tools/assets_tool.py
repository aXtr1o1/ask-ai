import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import *
from app.tools.tool_utils import getTime, logger
from app.api.routes.assets import get_assets

# ASSETS — physical equipment / master asset records.
# Called directly with a pre-built payload (see langchain_service._run_module);
# no LLM tool-selection or args_schema involved.
def ASSETS(
    user_name=None,
    user_id=None,
    asset_tag_no=None,
    asset_barcode=None,
    equipment_name=None,
    equipment_ref_no=None,
    serial_no=None,
    status=None,
    condition=None,
    priority=None,
    asset_type=None,
    division=None,
    discipline=None,
    locality=None,
    locality_code=None,
    building=None,
    floor=None,
    spot_name=None,
    owner=None,
    make=None,
    model=None,
    service_area=None,
    trade_group=None,
    drawing_no=None,
    remarks=None,
    on_hold=None,
    is_snagged=None,
    is_scraped=None,
    enable_ppm=None,
    enable_bdm=None,
    enable_bms=None,
    enable_dsm=None,
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
        logger.error("❌ ASSETS called without user_name")
        return "Error: user_name is required. It is set from the authenticated request."

    logger.info(f"📦 ASSETS TOOL TRIGGERED for user_name: {user_name}")
    
    resolved_date_from, resolved_date_to = getTime(date_from, date_to)
    
    payload = {
        "user_name":    user_name,
        "user_id":      user_id,
        "asset_tag_no": asset_tag_no,
        "asset_barcode": asset_barcode,
        "equipment_name": equipment_name,
        "equipment_ref_no": equipment_ref_no,
        "serial_no":    serial_no,
        "status":       status,
        "condition":    condition,
        "priority":     priority,
        "asset_type":   asset_type,
        "division":     division,
        "discipline":   discipline,
        "locality":     locality,
        "locality_code":    locality_code,
        "building":     building,
        "floor":        floor,
        "spot_name":    spot_name,
        "owner":        owner,
        "make":         make,
        "model":        model,
        "service_area": service_area,
        "trade_group":  trade_group,
        "drawing_no":   drawing_no,
        "remarks":      remarks,
        "on_hold":      on_hold,
        "is_snagged":   is_snagged,
        "is_scraped":   is_scraped,
        "enable_ppm":   enable_ppm,
        "enable_bdm":   enable_bdm,
        "enable_bms":   enable_bms,
        "enable_dsm":   enable_dsm,
        "keyword":      keyword,
        "date_from":    resolved_date_from,
        "date_to":      resolved_date_to,
        "limit":        limit,
        "offset":       0,
        "is_aggregate":       is_aggregate,
        "group_by_columns":   group_by_columns,
        "aggregate_function": aggregate_function,

        
    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    if "offset" not in clean_payload:
        clean_payload["offset"] = 0
    #log when aggregate mode is triggered so you can debug easily
    if is_aggregate:
        logger.info("📊 AGGREGATE MODE | group_by=%s | function=%s", group_by_columns, aggregate_function)
    

    logger.info("📋 [ASSETS PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str, ensure_ascii=False))

    try:
        logger.info("🚀 Calling get_assets directly")
        req = AssetRequest(**clean_payload)
        result = get_assets(req)
        logger.info("✅ Assets data successfully processed")
        return json.dumps(result)
    except HTTPException as e:
        logger.error("❌ Assets API error: %s", e.detail)
        return f"❌ API Error: {e.detail}"
    except Exception as e:
        logger.error(f"❌ Assets tool error: {e}", exc_info=True)
        return f"Error calling assets: {str(e)}"


