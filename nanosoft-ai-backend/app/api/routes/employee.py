"""
Employee Route — GET /get-employees
Supports full filterable query + aggregate mode
"""
from fastapi import APIRouter, HTTPException
import logging
import json

from app.api.models.schemas import EmployeeRequest
from app.api.database.postgres_client import get_pool
from .query_search_fallback import (
    EMPLOYEE_TEXT_FILTER_FIELDS,
    apply_limit_offset,
    enrich_with_search_fallback,
    merge_format_response,
)
from app.services.tool_payload_validator import validate_aggregate_request

router = APIRouter()

logger = logging.getLogger("employee_route")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)



def format_response(data):
    logger.info("you can view the length of the p_list and p_count value so that you can cross verify it")
    out = merge_format_response(data)
    logger.info(
        "format_response | p_list_length=%s | p_count=%s",
        len(out.get("p_list", [])),
        out.get("p_count", 0),
    )
    return out


def _call_sp_employee_query(req: EmployeeRequest) -> dict:
    conn   = get_pool()
    cursor = conn.cursor()
    cursor.callproc("sp_employee_query", [
        req.user_name,
        req.user_id,
        req.employee_id,      # NEW — EXACT ID MATCH
        req.employee_code,
        req.employee_name,
        req.first_name,
        req.last_name,
        req.organisation,
        req.department,
        req.designation,
        req.classification,
        req.branch,
        req.nature_of_work,
        req.employee_type,
        req.employment_type,
        req.shift_name,
        req.shift_code,
        req.gender,
        req.marital_status,
        req.nationality,
        req.country,
        req.employee_group,
        req.emp_grade,
        req.emp_title,
        req.vehicle_no,
        req.is_active,
        req.is_attendance_enable,
        req.is_single_punch,
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


@router.post("/get-employees")
def get_employees(req: EmployeeRequest):
    logger.info(
        "[GET-EMPLOYEES] Incoming | user_name=%s | department=%s | keyword=%s | limit=%s | offset=%s",
        req.user_name, req.department, req.keyword, req.limit, req.offset
    )
    logger.debug("[GET-EMPLOYEES] Full payload: %s", req.model_dump())

    if getattr(req, "is_aggregate", False):
        try:
            validate_aggregate_request(True, req.group_by_columns)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        logger.info("[GET-EMPLOYEES] AGGREGATE MODE detected -> calling sp_employee_aggregate")
        try:
            conn   = get_pool()
            cursor = conn.cursor()
            group_by_str = ",".join(req.group_by_columns) if req.group_by_columns else None
            agg_function = req.aggregate_function or "COUNT"
            logger.info("[GET-EMPLOYEES] group_by=%s | function=%s", group_by_str, agg_function)
            cursor.callproc("sp_employee_aggregate", [
                req.user_name,
                req.user_id,
                req.organisation,
                req.department,
                req.designation,
                req.classification,
                req.branch,
                req.nature_of_work,
                req.employee_type,
                req.employment_type,
                req.shift_name,
                req.gender,
                req.nationality,
                req.is_active,
                req.is_attendance_enable,
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
            logger.info("[GET-EMPLOYEES] Aggregate result | count=%s", formatted["p_count"])
            return formatted
        except Exception as e:
            err_msg = str(e)
            logger.error("[GET-EMPLOYEES] Aggregate RPC failed | error=%s", err_msg, exc_info=True)
            raise HTTPException(status_code=500, detail=err_msg)

    logger.info("[GET-EMPLOYEES] Calling sp_employee_query")
    try:
        formatted = enrich_with_search_fallback(
            req,
            _call_sp_employee_query(req),
            text_filter_fields=EMPLOYEE_TEXT_FILTER_FIELDS,
            call_query=_call_sp_employee_query,
            log_prefix="[GET-EMPLOYEES]",
            logger=logger,
            sp_label="sp_employee_query",
        )
        formatted = apply_limit_offset(formatted, req)
        p_list = formatted.get("p_list", [])

        if p_list:
            fields = list(p_list[0].keys()) if isinstance(p_list[0], dict) else []
            sample = [r.get("EmployeeIDPK") or r.get("EmployeeCode") or str(r)[:50] for r in p_list[:3]]
            logger.info(
                "[GET-EMPLOYEES] Fetched | count=%s | fields=%s | sample_ids=%s",
                formatted["p_count"], fields[:8], sample,
            )
        else:
            logger.info("[GET-EMPLOYEES] Success | count=0")

        return formatted

    except Exception as e:
        err_msg = str(e)
        if hasattr(e, "args") and e.args and isinstance(e.args[0], dict):
            err_dict = e.args[0]
            logger.error(
                "[GET-EMPLOYEES] RPC failed | code=%s | message=%s | hint=%s",
                err_dict.get("code", "?"),
                err_dict.get("message", err_msg),
                err_dict.get("hint", ""),
                exc_info=True,
            )
        else:
            logger.error("[GET-EMPLOYEES] RPC failed | error=%s", err_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=err_msg)
