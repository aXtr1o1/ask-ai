from fastapi import APIRouter, HTTPException
import logging

from app.api.models.schemas import AssetRequest
from app.api.database.supabase_client import get_supabase_client

router = APIRouter()

logger = logging.getLogger("assets_route")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)

def format_response(data):
    if isinstance(data, dict):
        return {"p_list": data.get("p_list", []), "p_count": data.get("p_count", 0)}
    safe = data if isinstance(data, list) else []
    return {"p_list": safe, "p_count": len(safe)}

@router.post("/get-assets")
def get_assets(req: AssetRequest):
    query_type = getattr(req, "query_type", "main").lower()
    logger.info(f"📦 Assets Single Endpoint | user_id={req.user_id} | type={query_type}")
    
    try:
        client = get_supabase_client()

        if query_type == "detail":
            response = client.rpc("sp_asset_detail", {
                "p_asset_tag_no": getattr(req, 'asset_tag_no', None),
                "p_user_id": req.user_id,
                "p_table_name": getattr(req, 'table_name', 'asset')
            }).execute()
            return response.data

        elif query_type == "lifecycle":
            response = client.rpc("sp_asset_lifecycle_query", {
                "p_user_id": req.user_id,
                "p_checktype": getattr(req, 'checktype', 'AGING'),
                "p_table_name": getattr(req, 'table_name', 'asset'),
                "p_limit": getattr(req, 'limit', None)
            }).execute()
            return format_response(response.data)

        elif query_type == "summary":
            response = client.rpc("sp_asset_summary_query", {
                "p_user_id": req.user_id,
                "p_groupby": getattr(req, 'groupby', 'DivisionName'),
                "p_table_name": getattr(req, 'table_name', 'asset')
            }).execute()
            return response.data

        elif query_type == "dataquality":
            response = client.rpc("sp_asset_dataquality_query", {
                "p_user_id": req.user_id,
                "p_checktype": getattr(req, 'checktype', 'MISSING_SERIAL'),
                "p_table_name": getattr(req, 'table_name', 'asset'),
                "p_limit": getattr(req, 'limit', None),
                "p_offset": getattr(req, 'offset', 0)
            }).execute()
            return format_response(response.data)

        else:
            # Default to "main" query
            response = client.rpc("sp_asset_query", {
                "p_user_id": req.user_id,
                "p_table_name": getattr(req, 'table_name', 'asset'),
                "p_asset_tag_no": getattr(req, 'asset_tag_no', None),
                "p_status": getattr(req, 'status', None),
                "p_condition": getattr(req, 'condition', None),
                "p_priority": getattr(req, 'priority', None),
                "p_asset_type": getattr(req, 'asset_type', None),
                "p_division": getattr(req, 'division', None),
                "p_discipline": getattr(req, 'discipline', None),
                "p_locality": getattr(req, 'locality', None),
                "p_building": getattr(req, 'building', None),
                "p_floor": getattr(req, 'floor', None),
                "p_owner": getattr(req, 'owner', None),
                "p_make": getattr(req, 'make', None),
                "p_model": getattr(req, 'model', None),
                "p_service_area": getattr(req, 'service_area', None),
                "p_trade_group": getattr(req, 'trade_group', None),
                "p_on_hold": getattr(req, 'on_hold', None),
                "p_is_snagged": getattr(req, 'is_snagged', None),
                "p_is_scraped": getattr(req, 'is_scraped', None),
                "p_enable_ppm": getattr(req, 'enable_ppm', None),
                "p_enable_bdm": getattr(req, 'enable_bdm', None),
                "p_keyword": getattr(req, 'keyword', None),
                "p_date_from": getattr(req, 'date_from', None),
                "p_date_to": getattr(req, 'date_to', None),
                "p_limit": getattr(req, 'limit', None),
                "p_offset": getattr(req, 'offset', 0)
            }).execute()
            return format_response(response.data)

    except Exception as e:
        logger.error(f"❌ Assets Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))