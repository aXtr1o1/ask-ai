"""
Assets Route
"""
from fastapi import APIRouter, HTTPException
import logging
import json

from app.api.models.schemas import AssetRequest
from app.api.database.postgres_client import get_pool
from .query_search_fallback import (
    ASSET_TEXT_FILTER_FIELDS,
    apply_limit_offset,
    enrich_with_search_fallback,
    merge_format_response,
)
from app.services.tool_payload_validator import validate_aggregate_request

router = APIRouter()

logger = logging.getLogger("assets_route")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


def format_response(data):
    logger.info("you can view the length of the p_list and p_count value so that you can cross verify it")
    out = merge_format_response(data)
    logger.info(
        "📊 format_response | p_list_length=%s | p_count=%s",
        len(out.get("p_list", [])),
        out.get("p_count", 0),
    )
    return out


def _call_sp_asset_query(req: AssetRequest) -> dict:
    conn = get_pool()
    cursor = conn.cursor()
    cursor.callproc("sp_asset_query", [
        req.user_name,
        req.user_id,
        req.asset_tag_no,
        req.asset_barcode,
        req.equipment_name,
        req.equipment_ref_no,
        req.serial_no,
        req.status,
        req.condition,
        req.priority,
        req.asset_type,
        req.division,
        req.discipline,
        req.locality,
        req.building,
        req.floor,
        req.spot_name,
        req.owner,
        req.make,
        req.model,
        req.service_area,
        req.trade_group,
        req.drawing_no,
        req.remarks,
        req.on_hold,
        req.is_snagged,
        req.is_scraped,
        req.enable_ppm,
        req.enable_bdm,
        req.enable_bms,
        req.enable_dsm,
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
    return format_response(raw)


@router.post("/get-assets")
def get_assets(req: AssetRequest):
    logger.info(
        "📦 [GET-ASSETS] Incoming | user_name=%s | limit=%s | offset=%s",
        req.user_name, req.limit, req.offset
    )
    logger.debug("[GET-ASSETS] Full payload: %s", req.model_dump())

    if getattr(req, "is_aggregate", False):
        try:
            validate_aggregate_request(True, req.group_by_columns)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        logger.info("📊 [GET-ASSETS] AGGREGATE MODE detected → calling sp_asset_aggregate")
        try:
            conn = get_pool()
            cursor = conn.cursor()
            group_by_str = ",".join(req.group_by_columns) if req.group_by_columns else None
            agg_function = req.aggregate_function or "COUNT"
            logger.info("📊 [GET-ASSETS] group_by=%s | function=%s", group_by_str, agg_function)
            cursor.callproc("sp_asset_aggregate", [
                req.user_name,
                req.user_id,
                req.division,
                req.discipline,
                req.building,
                req.floor,
                req.locality,
                req.status,
                req.condition,
                req.date_from,
                req.date_to,
                group_by_str,
                agg_function,
            ])
            row = cursor.fetchone()
            cursor.close()
            raw = row[0] if row else {}
            if isinstance(raw, str):
                raw = json.loads(raw)
            formatted = format_response(raw)
            logger.info("✅ [GET-ASSETS] Aggregate result | count=%s", formatted["p_count"])
            return formatted
        except Exception as e:
            err_msg = str(e)
            logger.error("[GET-ASSETS] Aggregate RPC failed | error=%s", err_msg, exc_info=True)
            raise HTTPException(status_code=500, detail=err_msg)

    logger.info("[GET-ASSETS] Calling sp_asset_query")
    try:
        formatted = enrich_with_search_fallback(
            req,
            _call_sp_asset_query(req),
            text_filter_fields=ASSET_TEXT_FILTER_FIELDS,
            call_query=_call_sp_asset_query,
            log_prefix="[GET-ASSETS]",
            logger=logger,
            sp_label="sp_asset_query",
        )
        formatted = apply_limit_offset(formatted, req)
        p_list = formatted.get("p_list", [])

        if p_list:
            fields = list(p_list[0].keys()) if isinstance(p_list[0], dict) else []
            sample = [r.get("AssetTagNo") or r.get("id") or str(r)[:50] for r in p_list[:3]]
            logger.info(
                "[GET-ASSETS] Fetched | count=%s | fields=%s | sample_ids=%s",
                formatted["p_count"], fields[:8], sample,
            )
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
                exc_info=True,
            )
        else:
            logger.error("[GET-ASSETS] RPC failed | error=%s", err_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=err_msg)
