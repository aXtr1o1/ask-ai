"""
BDM Route (Breakdown Maintenance / Complaints)
"""
from fastapi import APIRouter, HTTPException
import logging
import json

from app.api.models.schemas import PPMRequest
from app.api.database.postgres_client import get_pool

router = APIRouter()

logger = logging.getLogger("bdm_route")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


def format_response(data):
    
    logger.info("you can view the length of the p_list  and p_count value so that you can cross verify it")
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


@router.post("/get-ppm")
def get_ppm(req: PPMRequest):
    logger.info(
        "[GET-PPM] Incoming | user_name=%s | status=%s | limit=%s | offset=%s",
        req.user_name, req.status, req.limit, req.offset
    )
    logger.debug("[GET-PPM] Full payload: %s", req.model_dump())

    try:
        conn = get_pool()
        cursor = conn.cursor()

        logger.info("[GET-PPM] Calling sp_ppm_query")

        # sp_ppm_query — 24 params matching DB function exactly
        cursor.callproc("sp_ppm_query", [
            req.user_name,      # p_user_name      text
            req.work_order,     # p_work_order     varchar
            req.asset_tag_no,   # p_asset_tag_no   varchar
            req.status,         # p_status         varchar
            req.stage,          # p_stage          varchar
            req.frequency,      # p_frequency      varchar
            req.division,       # p_division       varchar
            req.discipline,     # p_discipline     varchar
            req.locality,       # p_locality       varchar
            req.building,       # p_building       varchar
            req.floor,          # p_floor          varchar
            req.contract,       # p_contract       varchar
            req.tech,           # p_tech           varchar
            req.equipment,      # p_equipment      varchar
            req.spot_name,      # p_spot_name      varchar
            req.keyword,        # p_keyword        varchar
            req.date_from,      # p_date_from      date
            req.date_to,        # p_date_to        date
            req.comp_from,      # p_comp_from      date
            req.comp_to,        # p_comp_to        date
            req.sla_min,        # p_sla_min        integer
            req.sla_max,        # p_sla_max        integer
            req.limit,          # p_limit          integer
            req.offset,         # p_offset         integer
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
        else:
            logger.info("[GET-PPM] Success | count=0")

        return formatted

    except Exception as e:
        err_msg = str(e)
        if hasattr(e, "args") and e.args and isinstance(e.args[0], dict):
            err_dict = e.args[0]
            logger.error(
                "[GET-BDM] RPC failed | code=%s | message=%s | hint=%s",
                err_dict.get("code", "?"),
                err_dict.get("message", err_msg),
                err_dict.get("hint", ""),
                exc_info=True
            )
        else:
            logger.error("[GET-PPM] RPC failed | error=%s", err_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=err_msg)
