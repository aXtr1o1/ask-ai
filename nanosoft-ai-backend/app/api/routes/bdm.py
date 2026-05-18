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
    logger.info("you can view the length of the p_list and p_count value so that you can cross verify it")
    if isinstance(data, dict):
        p_list = data.get("p_list", [])
        p_count = data.get("p_count", 0)
        logger.info("📊 format_response | p_list_length=%s | p_count=%s", len(p_list), p_count)
        return {"p_list": data.get("p_list", []), "p_count": data.get("p_count", 0)}
    safe_list = data if isinstance(data, list) else []
    logger.info("📊 format_response | p_list_length=%s | p_count=%s", len(safe_list), len(safe_list))
    return {"p_list": safe_list, "p_count": len(safe_list)}


@router.post("/get-bdm")
def get_bdm(req: BDMRequest):
    logger.info(
        "[GET-BDM] Incoming | user_name=%s | status=%s | limit=%s | offset=%s",
        req.user_name, req.status, req.limit, req.offset
    )
    logger.debug("[GET-BDM] Full payload: %s", req.model_dump())

    # Check if this is an aggregate query
    if getattr(req, "is_aggregate", False) and req.group_by_columns:
        logger.info("📊 [GET-BDM] AGGREGATE MODE detected → calling sp_bdm_aggregate")
        try:
            conn = get_pool()
            cursor = conn.cursor()

            #  Convert list to comma separated string for SP
            group_by_str = ",".join(req.group_by_columns) if req.group_by_columns else None
            agg_function = req.aggregate_function or "COUNT"

            logger.info("📊 [GET-BDM] group_by=%s | function=%s", group_by_str, agg_function)

            # Call aggregate SP with filters + group by
            cursor.callproc("sp_bdm_aggregate", [
                req.user_name,       # p_user_name
                req.user_id,         # p_user_id
                req.division,        # p_division
                req.discipline,      # p_discipline
                req.building,        # p_building
                req.floor,           # p_floor
                req.locality,        # p_locality
                req.status,          # p_status
                req.priority,        # p_priority
                req.stage,           # p_stage
                req.date_from,       # p_date_from
                req.date_to,         # p_date_to
                group_by_str,        # p_group_by_columns
                agg_function,        # p_aggregate_function
            ])

            row = cursor.fetchone()
            cursor.close()

            raw = row[0] if row else {}
            if isinstance(raw, str):
                raw = json.loads(raw)

            formatted = format_response(raw)
            logger.info("✅ [GET-BDM] Aggregate result | count=%s", formatted["p_count"])
            return formatted

        except Exception as e:
            err_msg = str(e)
            logger.error("[GET-BDM] Aggregate RPC failed | error=%s", err_msg, exc_info=True)
            raise HTTPException(status_code=500, detail=err_msg)
        

    try:
        conn = get_pool()
        cursor = conn.cursor()
        logger.info("[GET-BDM] Calling sp_bdm_query")

        cursor.callproc("sp_bdm_query", [
            req.user_name,
            req.user_id,
            req.complaint_no,
            req.status,
            req.priority,
            req.stage,
            req.complaint_type,
            req.complaint_mode,
            req.complaint_nature,
            req.wo_type,
            req.service_type,
            req.division,
            req.discipline,
            req.locality,
            req.building,
            req.floor,
            req.contract,
            req.analysis_tech,
            req.execution_tech,
            req.complainer,
            req.spot_name,
            req.keyword,
            req.date_from,
            req.date_to,
            req.completed_from,
            req.completed_to,
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

        # Fallback interceptor: if 0 records found and locality was specified but spot_name was not,
        # retry the query mapping locality to spot_name.
        if not p_list and req.locality and not req.spot_name:
            logger.info("🔄 0 records found with locality='%s' in BDM. Retrying query by mapping locality to spot_name...", req.locality)
            cursor = conn.cursor()
            cursor.callproc("sp_bdm_query", [
                req.user_name,
                req.user_id,
                req.complaint_no,
                req.status,
                req.priority,
                req.stage,
                req.complaint_type,
                req.complaint_mode,
                req.complaint_nature,
                req.wo_type,
                req.service_type,
                req.division,
                req.discipline,
                None,  # p_locality cleared
                req.building,
                req.floor,
                req.contract,
                req.analysis_tech,
                req.execution_tech,
                req.complainer,
                req.locality,  # p_spot_name mapped
                req.keyword,
                req.date_from,
                req.date_to,
                req.completed_from,
                req.completed_to,
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
            sample = [r.get("ComplaintNo") or r.get("id") or str(r)[:50] for r in p_list[:3]]
            logger.info("[GET-BDM] Fetched | count=%s | fields=%s | sample_ids=%s", formatted["p_count"], fields[:8], sample)
        else:
            logger.info("[GET-BDM] Success | count=0")


        return formatted

    except Exception as e:
        err_msg = str(e)
        if hasattr(e, "args") and e.args and isinstance(e.args[0], dict):
            err_dict = e.args[0]
            logger.error("[GET-BDM] RPC failed | code=%s | message=%s | hint=%s",
                err_dict.get("code", "?"), err_dict.get("message", err_msg), err_dict.get("hint", ""), exc_info=True)
        else:
            logger.error("[GET-BDM] RPC failed | error=%s", err_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=err_msg)