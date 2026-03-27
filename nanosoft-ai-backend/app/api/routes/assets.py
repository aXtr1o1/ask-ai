"""
Assets Route
"""
from fastapi import APIRouter, HTTPException
import logging
import json

from app.api.models.schemas import AssetRequest
from app.api.database.postgres_client import get_pool

router = APIRouter()

logger = logging.getLogger("assets_route")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)



def format_response(data):
    logger.info("you can view the length of the p_list and p_count value so that you can cross verify it")
    if isinstance(data, dict):
        p_list = data.get("p_list", [])
        p_count = data.get("p_count", 0)
        logger.info("📊 format_response | p_list_length=%s | p_count=%s", len(p_list), p_count)
        return {"p_list": data.get("p_list", []), "p_count": data.get("p_count", 0)}
    safe_list = data if isinstance(data, list) else []
    logger.info("📊 format_response | p_list_length=%s | p_count=%s", len(safe_list), len(safe_list))
    return {"p_list": safe_list, "p_count": len(safe_list)}


@router.post("/get-assets")
def get_assets(req: AssetRequest):
    logger.info(
        "📦 [GET-ASSETS] Incoming | user_name=%s | limit=%s | offset=%s",
        req.user_name, req.limit, req.offset
    )
    logger.debug("[GET-ASSETS] Full payload: %s", req.model_dump())
    
    logger.info("[GET-ASSETS] Calling sp_asset_query")

    #Check if this is an aggregate query
    # If is_aggregate is True → run GROUP BY path
    # If is_aggregate is False or None → run existing normal path 
    if getattr(req, "is_aggregate", False) and req.group_by_columns:
        logger.info("📊 [GET-ASSETS] AGGREGATE MODE detected → calling sp_asset_aggregate")
        try:
            conn = get_pool()
            cursor = conn.cursor()

            # Convert group_by_columns list to comma separated string for SP
            # Example: ["DivisionName", "BuildingName"] → "DivisionName,BuildingName"
            group_by_str = ",".join(req.group_by_columns) if req.group_by_columns else None
            agg_function = req.aggregate_function or "COUNT"

            logger.info("📊 [GET-ASSETS] group_by=%s | function=%s", group_by_str, agg_function)

            #Call the aggregate SP with filters + group by params
            cursor.callproc("sp_asset_aggregate", [
                req.user_name,    # p_user_name
                req.user_id,      # p_user_id
                req.division,     # p_division     — optional filter before grouping
                req.discipline,   # p_discipline   — optional filter before grouping
                req.building,     # p_building     — optional filter before grouping
                req.floor,        # p_floor        — optional filter before grouping
                req.locality,     # p_locality     — optional filter before grouping
                req.status,       # p_status       — optional filter before grouping
                req.condition,    # p_condition    — optional filter before grouping
                req.date_from,    # p_date_from    — optional filter before grouping
                req.date_to,      # p_date_to      — optional filter before grouping
                group_by_str,     # p_group_by_columns  e.g. "DivisionName,BuildingName"
                agg_function,     # p_aggregate_function e.g. COUNT / SUM / AVG
            ])

            row = cursor.fetchone()
            cursor.close()

            raw = row[0] if row else {}
            if isinstance(raw, str):
                raw = json.loads(raw)

            # format_response works the same way
            # SP returns same shape: { p_list: [...], p_count: N }
            # p_list here contains grouped summary rows like:
            # [{"DivisionName": "Electrical", "result": 45}, ...]
            formatted = format_response(raw)
            logger.info("✅ [GET-ASSETS] Aggregate result | count=%s", formatted["p_count"])
            return formatted

        except Exception as e:
            err_msg = str(e)
            logger.error("[GET-ASSETS] Aggregate RPC failed | error=%s", err_msg, exc_info=True)
            raise HTTPException(status_code=500, detail=err_msg)
   

    # normal path runs exactly as before
    logger.info("[GET-ASSETS] Calling sp_asset_query")
    try:
        conn = get_pool()
        cursor = conn.cursor()

        cursor.callproc("sp_asset_query", [
            req.user_name,
            req.user_id,
            req.asset_tag_no,
            req.status,
            req.condition,
            req.priority,
            req.asset_type,
            req.division,
            req.discipline,
            req.locality,
            req.building,
            req.floor,
            req.owner,
            req.make,
            req.model,
            req.service_area,
            req.trade_group,
            req.spot_name,
            req.serial_no,
            req.on_hold,
            req.is_snagged,
            req.is_scraped,
            req.enable_ppm,
            req.enable_bdm,
            req.keyword,
            req.date_from,
            req.date_to,
            req.limit,
            req.offset,
        ])

        row = cursor.fetchone()
        cursor.close()

        raw = row[0] if row else {}
        if isinstance(raw, str):
            raw = json.loads(raw)

        formatted = format_response(raw)
        p_list = formatted.get("p_list", [])

        if p_list:
            fields = list(p_list[0].keys()) if isinstance(p_list[0], dict) else []
            sample = [r.get("AssetTagNo") or r.get("id") or str(r)[:50] for r in p_list[:3]]
            logger.info("[GET-ASSETS] Fetched | count=%s | fields=%s | sample_ids=%s", formatted["p_count"], fields[:8], sample)
        else:
            logger.info("[GET-ASSETS] Success | count=0")

        return formatted

    except Exception as e:
        err_msg = str(e)
        if hasattr(e, "args") and e.args and isinstance(e.args[0], dict):
            err_dict = e.args[0]
            logger.error(
                "[GET-ASSETS] RPC failed | code=%s | message=%s | hint=%s",
                err_dict.get("code", "?"),
                err_dict.get("message", err_msg),
                err_dict.get("hint", ""),
                exc_info=True
            )
        else:
            logger.error("[GET-ASSETS] RPC failed | error=%s", err_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=err_msg)