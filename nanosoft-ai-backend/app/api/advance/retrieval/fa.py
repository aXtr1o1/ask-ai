import logging
from app.api.routes.fa import get_fa
from app.api.models.schemas import FARequest

logger = logging.getLogger("advance.retrieval.fa")

def retrieve(
    filter_values: dict,          # flat filters from HTTP payload (across all modules)
    module_filter_values: dict | None = None  # flat pre-filters for THIS module only (from questions.py)
) -> list[dict]:
    # Combine: start with HTTP payload filters, then overlay this module's pre-filters
    filters = {}
    if filter_values:
        filters.update(filter_values)
    if module_filter_values:
        filters.update(module_filter_values)  # now safely a flat {col: val} dict for fa only
    
    # Helper to check case-insensitive presence of keys in filters.
    # Empty strings are treated the same as None (not a valid filter value).
    def get_filter_value(*keys):
        for k in keys:
            if k in filters and filters[k] is not None and filters[k] != "":
                return filters[k]
            kl = k.lower()
            if kl in filters and filters[kl] is not None and filters[kl] != "":
                return filters[kl]
            for fk, fv in filters.items():
                if fk.lower() == kl and fv is not None and fv != "":
                    return fv
        return None

    # Map filters to FARequest fields
    payload = {
        "user_name": str(get_filter_value("user_name", "userName") or "poc"),
        "user_id": str(get_filter_value("user_id", "userId") or "1"),
        "offset": 0,
        "limit": None,
        "is_aggregate": False
    }
    
    # Mappings for FARequest fields
    mappings = {
        "complaint_no": ["RMComplaintNo", "complaint_no"],
        "complaint_code": ["RMCCMComplaintCode", "complaint_code"],
        "x_complaint_no": ["RMXComplaintNo", "x_complaint_no"],
        "priority": ["PriorityName", "priority"],
        "stage": ["RMStageName", "stage"],
        "category": ["RMCategoryName", "category"],
        "category_sub": ["RMCategorySubName", "category_sub"],
        "division": ["DivisionName", "division"],
        "locality": ["LocalityName", "locality"],
        "locality_code": ["LocalityCode", "locality_code"],
        "building": ["BuildingName", "building"],
        "floor": ["FloorName", "floor"],
        "spot_name": ["SpotName", "spot_name"],
        "contract": ["ContractName", "contract"],
        "tech": ["RMTechName", "tech"],
        "frequency": ["Frequency", "frequency"],
        "request_desc": ["RMRequestDetailsDesc", "request_desc"],
        "keyword": ["Keyword", "keyword"],
        "date_from": ["date_from"],
        "date_to": ["date_to"],
        "comp_from": ["RMBDMWOCompletedDate", "comp_from"],
        "comp_to": ["comp_to"]
    }
    
    for field_name, source_keys in mappings.items():
        val = get_filter_value(*source_keys)
        if val is not None:
            payload[field_name] = str(val)

    # Boolean fields
    bool_mappings = {
        "is_withdraw": ["IsRMWithdraw", "is_withdraw"],
        "is_rework": ["IsRMRework", "is_rework"],
        "is_bms": ["IsRMBMS", "is_bms"],
        "is_active": ["IsActive", "is_active"],
        "is_draft": ["IsDraft", "is_draft"]
    }
    
    for field_name, source_keys in bool_mappings.items():
        val = get_filter_value(*source_keys)
        if val is not None:
            if isinstance(val, str):
                payload[field_name] = val.lower() in ("true", "1", "yes")
            else:
                payload[field_name] = bool(val)

    logger.info("Retrieving FA from DB using payload: %s", payload)
    try:
        req = FARequest(**payload)
        response = get_fa(req)
        records = response.get("p_list") or []
        logger.info("Successfully retrieved %d FA records", len(records))
        return records
    except Exception as e:
        logger.error("Error retrieving FA: %s", e, exc_info=True)
        return []
        return []
