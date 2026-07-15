import logging
from app.api.routes.sb import get_sb
from app.api.models.schemas import SBRequest
from app.api.advance.retrieval.mappings import SB_MAPPINGS, SB_BOOL_MAPPINGS

logger = logging.getLogger("advance.retrieval.sb")


def retrieve(
    filter_values: dict,
    module_filter_values: dict | None = None
) -> list[dict]:
    # Combine HTTP-level filters + this module's pre-filters
    filters = {}
    if filter_values:
        filters.update(filter_values)
    if module_filter_values:
        filters.update(module_filter_values)

    # Case-insensitive key lookup — treats "" same as None (not a valid filter)
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

    payload = {
        "user_name": "poc",
        "user_id": "1",
        "offset": 0,
        "limit": None,
        "is_aggregate": False
    }

    # String fields — metadata col name -> SP param name (from mappings.py)
    for meta_col, sp_param in SB_MAPPINGS.items():
        val = get_filter_value(meta_col)
        if val is not None:
            payload[sp_param] = str(val)

    # Boolean fields
    for meta_col, sp_param in SB_BOOL_MAPPINGS.items():
        val = get_filter_value(meta_col)
        if val is not None:
            if isinstance(val, str):
                payload[sp_param] = val.lower() in ("true", "1", "yes")
            else:
                payload[sp_param] = bool(val)

    # Numeric/float SP params (no metadata column)
    for sp_param in ("sla_min", "sla_max"):
        val = get_filter_value(sp_param)
        if val is not None:
            try:
                payload[sp_param] = float(val)
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
