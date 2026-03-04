"""
BDM Route (Breakdown Maintenance / Complaints)
"""
from fastapi import APIRouter, HTTPException
import logging
import json

from app.api.models.schemas import BDMRequest
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


@router.post("/get-bdm")
def get_bdm(req: BDMRequest):
    logger.info(
        "[GET-BDM] Incoming | user_name=%s | status=%s | limit=%s | offset=%s",
        req.user_name, req.status, req.limit, req.offset
    )
    logger.debug("[GET-BDM] Full payload: %s", req.model_dump())

    try:
        conn = get_pool()
        cursor = conn.cursor()

        logger.info("[GET-BDM] Calling sp_bdm_query")

        # sp_bdm_query — 27 params matching DB function exactly
        cursor.callproc("sp_bdm_query", [
            req.user_name,         # p_user_name          text
            req.complaint_no,      # p_complaint_no       varchar
            req.status,            # p_status             varchar
            req.priority,          # p_priority           varchar
            req.stage,             # p_stage              varchar
            req.complaint_type,    # p_complaint_type     varchar
            req.complaint_mode,    # p_complaint_mode     varchar
            req.complaint_nature,  # p_complaint_nature   varchar
            req.wo_type,           # p_wo_type            varchar
            req.service_type,      # p_service_type       varchar
            req.division,          # p_division           varchar
            req.discipline,        # p_discipline         varchar
            req.locality,          # p_locality           varchar
            req.building,          # p_building           varchar
            req.floor,             # p_floor              varchar
            req.contract,          # p_contract           varchar
            req.analysis_tech,     # p_analysis_tech      varchar
            req.execution_tech,    # p_execution_tech     varchar
            req.complainer,        # p_complainer         varchar
            req.spot_name,         # p_spot_name          varchar 
            req.keyword,           # p_keyword            varchar
            req.date_from,         # p_date_from          date
            req.date_to,           # p_date_to            date
            req.completed_from,    # p_completed_from     date
            req.completed_to,      # p_completed_to       date
            req.limit,             # p_limit              integer
            req.offset,            # p_offset             integer
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
            sample = [r.get("ComplaintNo") or r.get("id") or str(r)[:50] for r in p_list[:3]]
            logger.info("[GET-BDM] Fetched | count=%s | fields=%s | sample_ids=%s", formatted["p_count"], fields[:8], sample)
        else:
            logger.info("[GET-BDM] Success | count=0")

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
            logger.error("[GET-BDM] RPC failed | error=%s", err_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=err_msg)
