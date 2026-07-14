import logging
from app.api.routes.sb import get_sb
from app.api.models.schemas import SBRequest

logger = logging.getLogger("advance.retrieval.sb")

def retrieve(
    filter_values: dict,          # flat filters from HTTP payload (across all modules)
    module_filter_values: dict | None = None  # flat pre-filters for THIS module only (from questions.py)
) -> list[dict]:
    # Combine: start with HTTP payload filters, then overlay this module's pre-filters
    filters = {}
    if filter_values:
        filters.update(filter_values)
    if module_filter_values:
        filters.update(module_filter_values)  # now safely a flat {col: val} dict for sb only
    
    # Helper to check case-insensitive presence of keys in filters
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

    # Map filters to SBRequest fields
    payload = {
        "user_name": str(get_filter_value("user_name", "userName") or "poc"),
        "user_id": str(get_filter_value("user_id", "userId") or "1"),
        "offset": 0,
        "limit": None,
        "is_aggregate": False
    }
    
    # Mappings for SBRequest fields
    mappings = {
        "work_order": ["SBCreWorkOrder", "work_order", "SBRequestNo"],
        "stage": ["PPMStageName", "SBStageName", "stage"],
        "frequency": ["Frequency", "frequency"],
        "service_type": ["ServiceTypeName", "service_type"],
        "division": ["DivisionName", "division"],
        "discipline": ["DisciplineName", "discipline"],
        "locality": ["LocalityName", "locality"],
        "locality_code": ["LocalityCode", "locality_code"],
        "building": ["BuildingName", "building"],
        "floor": ["FloorName", "floor"],
        "spot_name": ["SpotName", "spot_name"],
        "contract": ["ContractName", "contract"],
        "tech": ["SBTechName", "tech"],
        "keyword": ["Keyword", "keyword"],
        "date_from": ["date_from"],
        "date_to": ["date_to"],
        "comp_from": ["SBCreWoCompletedDate", "CompletedDateTime", "comp_from"],
        "comp_to": ["comp_to"]
    }
    
    for field_name, source_keys in mappings.items():
        val = get_filter_value(*source_keys)
        if val is not None:
            payload[field_name] = str(val)

    # Boolean fields
    bool_mappings = {
        "is_withdraw": ["IsSBCreWithDraw", "is_withdraw"],
        "is_reschedule": ["IsSbCreReschedule", "is_reschedule"],
        "is_rework": ["IsSBCreRework", "is_rework"],
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

    # Numeric/float fields
    for field_name, source_keys in {
        "sla_min": ["SBCreSLAHours", "sla_min"],
        "sla_max": ["sla_max"]
    }.items():
        val = get_filter_value(*source_keys)
        if val is not None:
            try:
                payload[field_name] = float(val)
            except (ValueError, TypeError):
                pass

    logger.info("Retrieving SB from DB using payload: %s", payload)
    try:
        req = SBRequest(**payload)
        response = get_sb(req)
        records = response.get("p_list") or []
        logger.info("Successfully retrieved %d SB records", len(records))
        return records
    except Exception as e:
        logger.error("Error retrieving SB: %s", e, exc_info=True)
        return []
        return []
