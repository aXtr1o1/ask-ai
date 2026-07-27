import logging
from app.api.routes.fa import get_fa
from app.api.models.schemas import FARequest
from app.api.advance.retrieval.mappings import FA_MAPPINGS, FA_BOOL_MAPPINGS

logger = logging.getLogger("advance.retrieval.fa")


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

    # Case-insensitive key lookup -- treats "" same as None (not a valid filter)
    def get_filter_value(*keys):
        for k in keys:
            for fk, fv in [(k, filters.get(k)), (k.lower(), filters.get(k.lower()))]:
                if fv is None or fv == "":
                    continue
                if isinstance(fv, str) and fv.strip().lower() in ("null", "none"):
                    continue   # treat "null" string as no filter
                if fv is not None:
                    return fv
            for fk, fv in filters.items():
                if fk.lower() == k.lower():
                    if fv is None or fv == "":
                        continue
                    if isinstance(fv, str) and fv.strip().lower() in ("null", "none"):
                        continue
                    return fv
        return None

    payload = {
        "user_name": "poc",
        "user_id": "1",
        "offset": 0,
        "limit": limit,
        "is_aggregate": False
    }

    # String fields -- metadata col name -> SP param name (from mappings.py)
    for meta_col, sp_param in FA_MAPPINGS.items():
        val = get_filter_value(meta_col)
        if val is not None:
            payload[sp_param] = str(val)

    # Boolean fields (real SP params confirmed in FARequest schema)
    for meta_col, sp_param in FA_BOOL_MAPPINGS.items():
        val = get_filter_value(meta_col)
        if val is not None:
            if isinstance(val, str):
                payload[sp_param] = val.lower() in ("true", "1", "yes")
            else:
                payload[sp_param] = bool(val)

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
