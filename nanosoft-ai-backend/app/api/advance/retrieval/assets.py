import logging
from app.api.routes.assets import get_assets
from app.api.models.schemas import AssetRequest

logger = logging.getLogger("advance.retrieval.assets")

def retrieve(
    filter_values: dict,          # flat filters from HTTP payload (across all modules)
    module_filter_values: dict | None = None  # flat pre-filters for THIS module only (from questions.py)
) -> list[dict]:
    # Combine: start with HTTP payload filters, then overlay this module's pre-filters
    filters = {}
    if filter_values:
        filters.update(filter_values)
    if module_filter_values:
        filters.update(module_filter_values)  # now safely a flat {col: val} dict for assets only
    
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

    def to_bool(val):
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes")
        return bool(val)

    # Map filters to AssetRequest fields
    payload = {
        "user_name": str(get_filter_value("user_name", "userName") or "poc"),
        "user_id": str(get_filter_value("user_id", "userId") or "1"),
        "offset": 0,
        "limit": None,
        "is_aggregate": False
    }
    
    # Mappings for AssetRequest string fields
    mappings = {
        "asset_tag_no": ["AssetTagNo", "asset_tag_no"],
        "asset_barcode": ["AssetBarcode", "asset_barcode"],
        "equipment_name": ["EquipmentName", "equipment_name"],
        "equipment_ref_no": ["EquipmentRefNo", "equipment_ref_no"],
        "serial_no": ["SerialNo", "serial_no"],
        "status": ["StatusName", "status"],
        "condition": ["ConditionName", "condition"],
        "priority": ["PriorityName", "priority"],
        "asset_type": ["AssetTypeName", "asset_type"],
        "division": ["DivisionName", "division"],
        "discipline": ["DisciplineName", "discipline"],
        "locality": ["LocalityName", "locality"],
        "building": ["BuildingName", "building"],
        "floor": ["FloorName", "floor"],
        "spot_name": ["SpotName", "spot_name"],
        "owner": ["Owner", "owner"],
        "make": ["Make", "make"],
        "model": ["Model", "model"],
        "service_area": ["ServiceArea", "service_area"],
        "trade_group": ["TradeGroup", "trade_group"],
        "drawing_no": ["DrawingNo", "drawing_no"],
        "remarks": ["Remarks", "remarks"],
        "keyword": ["Keyword", "keyword"],
        "date_from": ["date_from"],
        "date_to": ["date_to"]
    }
    
    for field_name, source_keys in mappings.items():
        val = get_filter_value(*source_keys)
        if val is not None:
            payload[field_name] = str(val)

    # Boolean fields mapping
    bool_mappings = {
        "on_hold": ["OnHold", "on_hold"],
        "is_snagged": ["IsSnagged", "is_snagged"],
        "is_scraped": ["IsScrapped", "IsScraped", "is_scraped", "is_scrapped"],
        "enable_ppm": ["IsEnablePPM", "EnablePPM", "enable_ppm"],
        "enable_bdm": ["IsEnableBDM", "EnableBDM", "enable_bdm"],
        "enable_bms": ["IsEnableBMS", "EnableBMS", "enable_bms"],
        "enable_dsm": ["IsEnableDSM", "EnableDSM", "enable_dsm"]
    }

    for field_name, source_keys in bool_mappings.items():
        val = get_filter_value(*source_keys)
        if val is not None:
            payload[field_name] = to_bool(val)

    logger.info("Retrieving Assets from DB using payload: %s", payload)
    try:
        req = AssetRequest(**payload)
        response = get_assets(req)
        records = response.get("p_list") or []
        logger.info("Successfully retrieved %d Asset records", len(records))
        return records
    except Exception as e:
        logger.error("Error retrieving Assets: %s", e, exc_info=True)
        return []
