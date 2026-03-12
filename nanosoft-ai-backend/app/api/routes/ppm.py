"""
PPM Route (Planned Preventive Maintenance)
"""
from fastapi import APIRouter, HTTPException
import logging
import json

from app.api.models.schemas import PPMRequest
from app.api.models.schemas import PPMRequest
from app.api.database.postgres_client import get_pool

router = APIRouter()

logger = logging.getLogger("ppm_route")
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


@router.post("/get-ppm")
def get_ppm(req: PPMRequest):
def get_ppm(req: PPMRequest):
    logger.info(
        "[GET-PPM] Incoming | user_name=%s | status=%s | limit=%s | offset=%s",
        req.user_name, req.status, req.limit, req.offset
    )
    logger.debug("[GET-PPM] Full payload: %s", req.model_dump())

    # Check if this is an aggregate query
    if getattr(req, "is_aggregate", False) and req.group_by_columns:
        logger.info("📊 [GET-PPM] AGGREGATE MODE detected → calling sp_ppm_aggregate")
        try:
            conn = get_pool()
            cursor = conn.cursor()

            # Convert list to comma separated string for SP
            group_by_str = ",".join(req.group_by_columns) if req.group_by_columns else None
            agg_function = req.aggregate_function or "COUNT"

            logger.info("📊 [GET-PPM] group_by=%s | function=%s", group_by_str, agg_function)

            # Call aggregate SP with filters + group by
            cursor.callproc("sp_ppm_aggregate", [
                req.user_name,    # p_user_name
                req.division,     # p_division
                req.discipline,   # p_discipline
                req.building,     # p_building
                req.floor,        # p_floor
                req.locality,     # p_locality
                req.status,       # p_status
                req.frequency,    # p_frequency
                req.date_from,    # p_date_from
                req.date_to,      # p_date_to
                group_by_str,     # p_group_by_columns
                agg_function,     # p_aggregate_function
            ])

            row = cursor.fetchone()
            cursor.close()

            raw = row[0] if row else {}
            if isinstance(raw, str):
                raw = json.loads(raw)

            formatted = format_response(raw)
            logger.info("✅ [GET-PPM] Aggregate result | count=%s", formatted["p_count"])
            return formatted

        except Exception as e:
            err_msg = str(e)
            logger.error("[GET-PPM] Aggregate RPC failed | error=%s", err_msg, exc_info=True)
            raise HTTPException(status_code=500, detail=err_msg)
        
    try:
        conn = get_pool()
        cursor = conn.cursor()
        logger.info("[GET-PPM] Calling sp_ppm_query")

        cursor.callproc("sp_ppm_query", [
            req.user_name,
            req.work_order,
            req.asset_tag_no,
            req.status,
            req.stage,
            req.frequency,
            req.division,
            req.discipline,
            req.locality,
            req.building,
            req.floor,
            req.contract,
            req.tech,
            req.equipment,
            req.spot_name,
            req.keyword,
            req.date_from,
            req.date_to,
            req.comp_from,
            req.comp_to,
            req.sla_min,
            req.sla_max,
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
            sample = [r.get("WorkOrder") or r.get("id") or str(r)[:50] for r in p_list[:3]]
            logger.info("[GET-PPM] Fetched | count=%s | fields=%s | sample_ids=%s", formatted["p_count"], fields[:8], sample)
            sample = [r.get("WorkOrder") or r.get("id") or str(r)[:50] for r in p_list[:3]]
            logger.info("[GET-PPM] Fetched | count=%s | fields=%s | sample_ids=%s", formatted["p_count"], fields[:8], sample)
        else:
            logger.info("[GET-PPM] Success | count=0")

            logger.info("[GET-PPM] Success | count=0")

        return formatted

    except Exception as e:
        err_msg = str(e)
        if hasattr(e, "args") and e.args and isinstance(e.args[0], dict):
            err_dict = e.args[0]
            logger.error("[GET-PPM] RPC failed | code=%s | message=%s | hint=%s",
                err_dict.get("code", "?"), err_dict.get("message", err_msg), err_dict.get("hint", ""), exc_info=True)
        else:
            logger.error("[GET-PPM] RPC failed | error=%s", err_msg, exc_info=True)
            logger.error("[GET-PPM] RPC failed | error=%s", err_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=err_msg)
