import logging
from app.api.routes.bdm import get_bdm
from app.api.models.schemas import BDMRequest
from app.api.advance.retrieval.mappings import BDM_MAPPINGS, BDM_BOOL_MAPPINGS

logger = logging.getLogger("advance.retrieval.bdm")


def retrieve(
    filter_values: dict,
    module_filter_values: dict | None = None,
    limit: int | None = None,
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
        "limit": limit,
        "is_aggregate": False
    }

    # String fields  metadata col name -> SP param name (from mappings.py)
    for meta_col, sp_param in BDM_MAPPINGS.items():
        val = get_filter_value(meta_col)
        if val is not None and val != "":
            payload[sp_param] = str(val)

    # Boolean fields
    for meta_col, sp_param in BDM_BOOL_MAPPINGS.items():
        val = get_filter_value(meta_col)
        if val is not None:
            if isinstance(val, str):
                payload[sp_param] = val.lower() in ("true", "1", "yes")
            else:
                payload[sp_param] = bool(val)

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
