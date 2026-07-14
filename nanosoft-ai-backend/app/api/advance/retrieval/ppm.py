import logging
from app.api.routes.ppm import get_ppm
from app.api.models.schemas import PPMRequest

logger = logging.getLogger("advance.retrieval.ppm")

def retrieve(
    filter_values: dict,          # flat filters from HTTP payload (across all modules)
    module_filter_values: dict | None = None  # flat pre-filters for THIS module only (from questions.py)
) -> list[dict]:
    # Combine: start with HTTP payload filters, then overlay this module's pre-filters
    filters = {}
    if filter_values:
        filters.update(filter_values)
    if module_filter_values:
        filters.update(module_filter_values)  # now safely a flat {col: val} dict for ppm only
    
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

    # Map filters to PPMRequest fields
    payload = {
        "user_name": str(get_filter_value("user_name", "userName") or "poc"),
        "user_id": str(get_filter_value("user_id", "userId") or "1"),
        "offset": 0,
        "limit": None,
        "is_aggregate": False
    }
    # Snapshot the keys that exist BEFORE any filter mappings are added.
    # These are the structural/required fields — everything added after is optional/relaxable.
    base_payload_keys = set(payload.keys())
    
    # Mappings for PPMRequest fields
    mappings = {
        "work_order": ["WorkOrder", "work_order"],
        "asset_tag_no": ["AssetTagNo", "asset_tag_no"],
        "equipment_ref_no": ["EquipmentRefNo", "equipment_ref_no"],
        "status": ["PPMStatus", "status"],
        "stage": ["PPMStageName", "stage"],
        "frequency": ["Frequency", "frequency"],
        "division": ["DivisionName", "division"],
        "discipline": ["DisciplineName", "discipline"],
        "locality": ["LocalityName", "locality"],
        "locality_code": ["LocalityCode", "locality_code"],
        "building": ["BuildingName", "building"],
        "floor": ["FloorName", "floor"],
        "spot_name": ["SpotName", "spot_name"],
        "equipment": ["EquipmentName", "equipment"],
        "contract": ["ContractName", "contract"],
        "tech": ["PMTechName", "tech"],
        "keyword": ["Keyword", "keyword"],
        "date_from": ["date_from"],
        "date_to": ["date_to"],
        "comp_from": ["WoCompletedDate", "comp_from"],
        "comp_to": ["comp_to"]
    }
    
    for field_name, source_keys in mappings.items():
        val = get_filter_value(*source_keys)
        if val is not None:
            payload[field_name] = str(val)

    # Numeric fields
    for field_name, source_keys in {
        "sla_min": ["sla_min"],
        "sla_max": ["sla_max"]
    }.items():
        val = get_filter_value(*source_keys)
        if val is not None:
            try:
                payload[field_name] = int(val)
            except (ValueError, TypeError):
                pass

    logger.info("Retrieving PPM from DB using payload: %s", payload)
    try:
        req = PPMRequest(**payload)
        response = get_ppm(req)
        records = response.get("p_list") or []
        logger.info("Successfully retrieved %d PPM records", len(records))

        # Progressive filter relaxation: if 0 results, dynamically determine
        # which fields are optional (anything beyond the base required fields)
        # and drop them one at a time — most recently added first (most specific)
        # — until records are found.
        if not records:
            # optional_fields = everything added by filter mappings (not the base snapshot)
            optional_fields = [k for k in payload if k not in base_payload_keys]
            dropped = []
            current_payload = dict(payload)
            for field in reversed(optional_fields):  # reverse = most specific first
                current_payload = {k: v for k, v in current_payload.items() if k != field}
                dropped.append(field)
                logger.info("PPM retry — dropped fields: %s | retrying payload: %s", dropped, current_payload)
                try:
                    retry_req = PPMRequest(**current_payload)
                    retry_response = get_ppm(retry_req)
                    retry_records = retry_response.get("p_list") or []
                    if retry_records:
                        logger.info("PPM retry succeeded with %d records after dropping: %s", len(retry_records), dropped)
                        return retry_records
                except Exception as retry_e:
                    logger.warning("PPM retry error after dropping %s: %s", dropped, retry_e)

        return records
    except Exception as e:
        logger.error("Error retrieving PPM: %s", e, exc_info=True)
        return []
