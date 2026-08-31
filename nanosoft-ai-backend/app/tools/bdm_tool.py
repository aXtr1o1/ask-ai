import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import *
from app.tools.tool_utils import getTime, logger
from app.api.routes.bdm import get_bdm

# BDM — breakdown maintenance complaints and reactive work orders.
# Called directly with a pre-built payload (see langchain_service._run_module);
# no LLM tool-selection or args_schema involved.
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
    

 
