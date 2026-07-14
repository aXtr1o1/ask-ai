import logging
from app.api.routes.bdm import get_bdm
from app.api.models.schemas import BDMRequest

logger = logging.getLogger("advance.retrieval.bdm")

def retrieve(
    filter_values: dict,          # flat filters from HTTP payload (across all modules)
    module_filter_values: dict | None = None  # flat pre-filters for THIS module only (from questions.py)
) -> list[dict]:
    # Combine: start with HTTP payload filters, then overlay this module's pre-filters
    filters = {}
    if filter_values:
        filters.update(filter_values)
    if module_filter_values:
        filters.update(module_filter_values)  # now safely a flat {col: val} dict for bdm only
    
    # Helper to check case-insensitive presence of keys in filters
    # Returns None if the value is None OR an empty string (treats "" as "no filter")
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

    # Map filters to BDMRequest fields
    payload = {
        "user_name": str(get_filter_value("user_name", "userName") or "poc"),
        "user_id": str(get_filter_value("user_id", "userId") or "1"),
        "offset": 0,
        "limit": None,
        "is_aggregate": False
    }
    
    # Mappings for BDMRequest fields
    mappings = {
        "complaint_no": ["ComplaintNo", "complaint_no"],
        "asset_tag_no": ["AssetTagNo", "asset_tag_no"],
        "asset_barcode": ["AssetBarcode", "asset_barcode"],
        "client_wo_no": ["ClientWoNo", "client_wo_no"],
        "status": ["WoStatus", "status"],
        "priority": ["PriorityName", "priority"],
        "stage": ["StageName", "stage"],
        "complaint_type": ["ComplaintTypeName", "complaint_type"],
        "complaint_header": ["ComplaintHeader", "complaint_header"],
        "complaint_mode": ["ComplaintModeName", "complaint_mode"],
        "complaint_nature": ["ComplaintNatureName", "complaint_nature"],
        "wo_type": ["WoType", "wo_type"],
        "service_type": ["ServiceTypeName", "service_type"],
        "division": ["DivisionName", "division"],
        "discipline": ["DisciplineName", "discipline"],
        "locality": ["LocalityName", "locality"],
        "locality_code": ["LocalityCode", "locality_code"],
        "building": ["BuildingName", "building"],
        "floor": ["FloorName", "floor"],
        "spot_name": ["SpotName", "spot_name"],
        "contract": ["ContractName", "contract"],
        "complainer": ["Complainer", "complainer"],
        "register_by": ["RegisterBy", "register_by"],
        "analysis_tech": ["AnalysisTechName", "analysis_tech"],
        "execution_tech": ["ExecutionTechName", "execution_tech"],
        "keyword": ["Keyword", "keyword"],
        "date_from": ["date_from"],
        "date_to": ["date_to"],
        "completed_from": ["completed_from"],
        "completed_to": ["completed_to"]
    }
    
    for field_name, source_keys in mappings.items():
        val = get_filter_value(*source_keys)
        if val is not None and val != "":  # skip empty strings — no filter applied
            payload[field_name] = str(val)

    logger.info("Retrieving BDM from DB using payload: %s", payload)
    try:
        req = BDMRequest(**payload)
        response = get_bdm(req)
        records = response.get("p_list") or []
        logger.info("Successfully retrieved %d BDM records", len(records))
        return records
    except Exception as e:
        logger.error("Error retrieving BDM: %s", e, exc_info=True)
        return []
        return []
