import logging
from app.api.routes.assets import get_assets
from app.api.models.schemas import AssetRequest
from app.api.advance.retrieval.mappings import ASSETS_MAPPINGS, ASSETS_BOOL_MAPPINGS

logger = logging.getLogger("advance.retrieval.assets")


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

    payload = {
        "user_name": "poc",
        "user_id": "1",
        "offset": 0,
        "limit": limit,
        "is_aggregate": False
    }

    # String fields  metadata col name -> SP param name (from mappings.py)
    for meta_col, sp_param in ASSETS_MAPPINGS.items():
        val = get_filter_value(meta_col)
        if val is not None:
            payload[sp_param] = str(val)

    # Boolean fields
    for meta_col, sp_param in ASSETS_BOOL_MAPPINGS.items():
        val = get_filter_value(meta_col)
        if val is not None:
            payload[sp_param] = to_bool(val)

        asset_tags = payload.get("asset_tag_no")

    # Handle multiple asset tags
    if asset_tags and "," in asset_tags:
        all_records = []

        for tag in asset_tags.split(","):
            single_payload = payload.copy()
            single_payload["asset_tag_no"] = tag.strip()

            logger.info(
                "Retrieving Assets from DB using payload: %s",
                single_payload,
            )

            try:
                req = AssetRequest(**single_payload)
                response = get_assets(req)
                all_records.extend(response.get("p_list") or [])
            except Exception as e:
                logger.error(
                    "Error retrieving asset %s: %s",
                    tag,
                    e,
                    exc_info=True,
                )

        logger.info("Successfully retrieved %d Asset records", len(all_records))
        return all_records

    # Existing logic for a single asset tag
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
