import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import *
from app.tools.tool_utils import getTime, logger
from app.api.routes.contract import get_contracts

# CONTRACT — service contracts, maintenance agreements, and client contract records.
# Called directly with a pre-built payload (see langchain_service._run_module);
# no LLM tool-selection or args_schema involved.
def CONTRACT(
    user_name=None,
    user_id=None,
    contract_id=None,
    contract_code=None,
    contract_name=None,
    customer_name=None,
    contract_type=None,
    contract_categ=None,
    contract_group=None,
    organisation=None,
    status=None,
    status_type=None,
    tax_name=None,
    period=None,
    payment_terms=None,
    is_active=None,
    is_draft=None,
    is_renewal=None,
    is_extended=None,
    is_terminate=None,
    is_non_contract=None,
    is_ppm=None,
    is_bdm=None,
    is_dsm=None,
    is_incident=None,
    is_case=None,
    keyword=None,
    date_from=None,
    date_to=None,
    limit=None,
    offset=None,
    is_aggregate=False,
    group_by_columns=None,
    aggregate_function=None,
) -> str:
    if not user_name:
        logger.error("CONTRACT called without user_name")
        return "Error: user_name is required. It is set from the authenticated request."

    logger.info(f"CONTRACT TOOL TRIGGERED for user_name: {user_name}")

    resolved_date_from, resolved_date_to = getTime(date_from, date_to)

    payload = {
        "user_name":          user_name,
        "user_id":            user_id,
        "contract_id":        contract_id,
        "contract_code":      contract_code,
        "contract_name":      contract_name,
        "customer_name":      customer_name,
        "contract_type":      contract_type,
        "contract_categ":     contract_categ,
        "contract_group":     contract_group,
        "organisation":       organisation,
        "status":             status,
        "status_type":        status_type,
        "tax_name":           tax_name,
        "period":             period,
        "payment_terms":      payment_terms,
        "is_active":          is_active,
        "is_draft":           is_draft,
        "is_renewal":         is_renewal,
        "is_extended":        is_extended,
        "is_terminate":       is_terminate,
        "is_non_contract":    is_non_contract,
        "is_ppm":             is_ppm,
        "is_bdm":             is_bdm,
        "is_dsm":             is_dsm,
        "is_incident":        is_incident,
        "is_case":            is_case,
        "keyword":            keyword,
        "date_from":          resolved_date_from,
        "date_to":            resolved_date_to,
        "limit":              limit,
        "offset":             0,
        "is_aggregate":       is_aggregate,
        "group_by_columns":   group_by_columns,
        "aggregate_function": aggregate_function,
    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    if "offset" not in clean_payload:
        clean_payload["offset"] = 0

    if is_aggregate:
        logger.info("[CONTRACT] AGGREGATE MODE | group_by=%s | function=%s", group_by_columns, aggregate_function)

    logger.info("[CONTRACT PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str, ensure_ascii=False))

    try:
        logger.info("[CONTRACT] Calling get_contracts directly")
        req = ContractRequest(**clean_payload)
        result = get_contracts(req)
        logger.info("[CONTRACT] Data processed successfully")
        return json.dumps(result)
    except HTTPException as e:
        logger.error("[CONTRACT] API error: %s", e.detail)
        return json.dumps({"p_list": [], "p_count": 0, "error": "Unable to retrieve contract data. Please try a different query."})
    except Exception as e:
        logger.error("[CONTRACT] Tool error: %s", str(e), exc_info=True)
        return json.dumps({"p_list": [], "p_count": 0, "error": "Unable to retrieve contract data. Please try a different query."})
