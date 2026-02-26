"""
Asset Query Functions - Direct Database Access
"""
import logging
from app.api.models.schemas import AssetRequest
from app.api.database.supabase_client import get_supabase_client

logger = logging.getLogger("asset_queries")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


def format_response(data):
    """
    Format the response from Supabase RPC call
    """
    logger.info("you can view the length of the p_list and p_count value so that you can cross verify it")
    if isinstance(data, dict):
        p_list = data.get("p_list", [])
        p_count = data.get("p_count", 0)
        
        logger.info(
            "📊 format_response | p_list_length=%s | p_count=%s",
            len(p_list),
            p_count
        )
        return {"p_list": data.get("p_list", []), "p_count": data.get("p_count", 0)}
    
    safe_list = data if isinstance(data, list) else []

    logger.info(
        "📊 format_response | p_list_length=%s | p_count=%s",
        len(safe_list),
        len(safe_list)
    )

    return {
        "p_list": safe_list,
        "p_count": len(safe_list)
    }

def query_assets(req: AssetRequest) -> dict:
    """
    Query assets from database - Direct function call (no HTTP)

    """
    logger.info(
        "📦 [QUERY-ASSETS] Incoming | user_id=%s | limit=%s | offset=%s",
        req.user_id, req.limit, req.offset
    )
    logger.debug("[QUERY-ASSETS] Full payload: %s", req.model_dump())

    rpc_params = {
        "p_user_id": req.user_id,
        "p_status": req.status,
        "p_condition": req.condition,
        "p_priority": req.priority,
        "p_asset_type": req.asset_type,
        "p_asset_tag_no": req.asset_tag_no,
        "p_division": req.division,
        "p_discipline": req.discipline,
        "p_locality": req.locality,
        "p_building": req.building,
        "p_floor": req.floor,
        "p_owner": req.owner,
        "p_make": req.make,
        "p_model": req.model,
        "p_service_area": req.service_area,
        "p_trade_group": req.trade_group,
        "p_on_hold": req.on_hold,
        "p_is_snagged": req.is_snagged,
        "p_is_scraped": req.is_scraped,
        "p_enable_ppm": req.enable_ppm,
        "p_enable_bdm": req.enable_bdm,
        "p_keyword": req.keyword,
        "p_date_from": req.date_from,
        "p_date_to": req.date_to,
        "p_limit": req.limit,
        "p_offset": req.offset,
    }
    
    logger.info("[QUERY-ASSETS] Calling sp_asset_query | params=%s", list(rpc_params.keys()))

    try:
        client = get_supabase_client()
        response = client.rpc("sp_asset_query", rpc_params).execute()
        formatted = format_response(response.data)
        p_list = formatted.get("p_list", [])
        if p_list:
            fields = list(p_list[0].keys()) if isinstance(p_list[0], dict) else []
            sample = [r.get("asset_tag_no") or r.get("id") or str(r)[:50] for r in p_list[:3]]
            logger.info("[QUERY-ASSETS] Fetched | count=%s | fields=%s | sample_ids=%s", formatted["p_count"], fields[:8], sample)
        else:
            logger.info("[QUERY-ASSETS] Success | count=0")
        return formatted
    except Exception as e:
        err_msg = str(e)
        # Parse PostgREST/Supabase error for easier debugging
        if hasattr(e, "args") and e.args and isinstance(e.args[0], dict):
            err_dict = e.args[0]
            logger.error(
                "[QUERY-ASSETS] RPC failed | code=%s | message=%s | hint=%s",
                err_dict.get("code", "?"),
                err_dict.get("message", err_msg),
                err_dict.get("hint", ""),
                exc_info=True
            )
        else:
            logger.error("[QUERY-ASSETS] RPC failed | error=%s", err_msg, exc_info=True)
        raise Exception(f"Asset query failed: {err_msg}")