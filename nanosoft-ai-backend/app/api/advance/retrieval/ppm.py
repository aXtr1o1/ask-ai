import logging
from app.api.routes.ppm import get_ppm
from app.api.models.schemas import PPMRequest
from app.api.advance.retrieval.mappings import PPM_MAPPINGS

logger = logging.getLogger("advance.retrieval.ppm")


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

    # Case-insensitive key lookup  treats "" same as None (not a valid filter)
    def get_filter_value(*keys):
        for k in keys:
            val = None
            if k in filters and filters[k] is not None and filters[k] != "":
                val = filters[k]
            elif k.lower() in filters and filters[k.lower()] is not None and filters[k.lower()] != "":
                val = filters[k.lower()]
            else:
                for fk, fv in filters.items():
                    if fk.lower() == k.lower() and fv is not None and fv != "":
                        val = fv
                        break
            if val is not None:
                if isinstance(val, list):
                    return str(val[0]).strip() if val else None
                return str(val).strip()
        return None

    payload = {
        "user_name": "poc",
        "user_id": "1",
        "offset": 0,
        "limit": limit,
        "is_aggregate": False
    }
    # Snapshot base keys before optional filters are added (used for retry relaxation)
    base_payload_keys = set(payload.keys())

    # String fields � metadata col name -> SP param name (from mappings.py)
    for meta_col, sp_param in PPM_MAPPINGS.items():
        val = get_filter_value(meta_col)
        if val is not None:
            payload[sp_param] = str(val)

    # Numeric-only SP params (no metadata column, HTTP pass-through only)
    for sp_param in ("sla_min", "sla_max"):
        val = get_filter_value(sp_param)
        if val is not None:
            try:
                payload[sp_param] = int(val)
            except (ValueError, TypeError):
                pass

    logger.info("Retrieving PPM from DB using payload: %s", payload)
    try:
        req = PPMRequest(**payload)
        response = get_ppm(req)
        records = response.get("p_list") or []
        logger.info("Successfully retrieved %d PPM records", len(records))

        # Progressive filter relaxation: if 0 results, drop optional filters one by one
        if not records:
            optional_fields = [k for k in payload if k not in base_payload_keys]
            dropped = []
            current_payload = dict(payload)
            for field in reversed(optional_fields):
                current_payload = {k: v for k, v in current_payload.items() if k != field}
                dropped.append(field)
                logger.info("PPM retry  dropped fields: %s | retrying payload: %s", dropped, current_payload)
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
