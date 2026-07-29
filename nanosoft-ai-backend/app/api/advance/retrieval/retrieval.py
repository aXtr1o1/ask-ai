"""
Retrieval — Data Loader and Filter Function

get_filtered_records(modules, filter_fields, filter_values)
  → loads each module's data dynamically
  → applies filter_values to keep only matching rows
  → keeps only the columns defined in filter_fields
  → returns { module_name: [filtered_rows] }

filter_fields format (new):
  { "ColumnName": "description of the column" }
  The KEY is the actual column name. The VALUE is description metadata for the LLM.
  No mapping needed — the key IS the column name used directly for filtering.

The filtered records go DIRECTLY to tools via agent state.
They are NEVER sent to the LLM.
"""
import logging
from typing import Any

logger = logging.getLogger("advance.retrieval")

# Data is loaded dynamically via routes (assets.py, bdm.py, etc.)


# =============================================================================
# STEP 2: Filter rows — keep only records that match the user's filter values
#
# filter_fields keys ARE the column names (new format).
# filter_values keys are also column names: {"BuildingName": "Tower A"}
# For each filter, keep only rows where that column contains the value.
#
# Called by: get_filtered_records
# =============================================================================
def _apply_filters(
    records: list[dict],
    filter_fields: dict[str, str],   # { column_name → description }
    filter_values: dict[str, Any],   # { column_name → value from HTTP request }
) -> list[dict]:
    """Filter records to only those matching the user-supplied filter values."""
    result = records

    for column_name, filter_value in filter_values.items():
        if not filter_value:
            continue   # skip None / "" / 0 / False
        if isinstance(filter_value, str) and filter_value.strip().lower() in ("null", "none"):
            continue   # skip literal "null"/"none" strings — treat as no filter

        # Only filter on columns that are defined for this module
        if column_name not in filter_fields:
            continue

        # Treat comma-separated filter values as multiple targets (OR logic)
        targets = [t.strip().lower() for t in str(filter_value).split(',')]

        # Keep only rows where the column contains ANY of the targets (OR logic)
        result = [
            row for row in result
            if any(t in str(row.get(column_name, "")).lower() for t in targets)
        ]
        logger.info(
            "[RETRIEVAL] filter column=%s value=%s → %d records remaining",
            column_name, filter_value, len(result),
        )

    return result


# =============================================================================
# STEP 3: Project columns — keep only the columns defined in filter_fields
#
# filter_fields keys are the column names to keep (new format).
# Any other columns in the raw data are stripped out.
#
# Called by: get_filtered_records
# =============================================================================
def _project_columns(
    records: list[dict],
    filter_fields: dict[str, str],   # { column_name → description }
) -> list[dict]:
    """
    Keep only the columns whose names are defined as keys in filter_fields.

    If filter_fields is empty (Analysis Agent returned no fields), return
    all columns so the Execution Agent still has usable data.
    """
    if not filter_fields:
        return records   # no projection — keep everything
    keep_columns = set(filter_fields.keys())
    return [{k: v for k, v in row.items() if k in keep_columns} for row in records]


# =============================================================================
# MAIN FUNCTION: get_filtered_records
#
# Called by: routes.py → run_agent()
# Returns:   { module_name: [filtered_projected_rows] }
# =============================================================================
def get_filtered_records(
    modules: list[str],
    filter_fields: dict[str, dict],         # { module → { column_name → description } }
    filter_values: dict[str, Any],          # { column_name → value } from HTTP request (flat, all modules)
    module_filter_values: dict[str, dict] | None = None,  # { module → { column → value } } from question definition
    limit: int | None = None,
) -> dict[str, list[dict]]:
    """
    For each module:
      1. Load raw records dynamically
      2. Apply module-level pre-filters (from question definition)
      3. Apply HTTP-level filters (from request, flat dict)
      4. Project to only the relevant columns (defined in filter_fields)
    Returns { module_name: [filtered_rows] }

    filter_values      — flat dict applied to all modules: {"BuildingName": "Tower A"}
    module_filter_values — per-module pre-filters: {"bdm": {"WoStatus": "Closed"}, "ppm": {"PPMStatus": "Closed"}}
    limit              — max records to retrieve from database
    """
    output: dict[str, list[dict]] = {}

    for module in modules:
        # Step 1: load data dynamically from route functions
        raw_records = []
        try:
            # Pass only this module's slice of module_filter_values so each
            # retrieval function receives only its own pre-filters, not all modules'.
            this_module_filters = (module_filter_values or {}).get(module, {})

            if module == "assets":
                from app.api.advance.retrieval.assets import retrieve as assets_retrieve
                raw_records = assets_retrieve(filter_values, this_module_filters, limit=limit)
            elif module == "bdm":
                from app.api.advance.retrieval.bdm import retrieve as bdm_retrieve
                raw_records = bdm_retrieve(filter_values, this_module_filters, limit=limit)
            elif module == "fa":
                from app.api.advance.retrieval.fa import retrieve as fa_retrieve
                raw_records = fa_retrieve(filter_values, this_module_filters, limit=limit)
            elif module == "ppm":
                from app.api.advance.retrieval.ppm import retrieve as ppm_retrieve
                raw_records = ppm_retrieve(filter_values, this_module_filters, limit=limit)
            elif module == "sb":
                from app.api.advance.retrieval.sb import retrieve as sb_retrieve
                raw_records = sb_retrieve(filter_values, this_module_filters, limit=limit)
        except Exception as e:
            logger.warning("[RETRIEVAL] Retrieval failed for module %s: %s", module, e)
            
        if not raw_records:
            logger.warning("[RETRIEVAL] Retrieval returned 0 records for module %s", module)

        # Step 2: get this module's column definitions
        module_filter_fields = filter_fields.get(module, {})

        if not module_filter_fields:
            logger.warning(
                "[RETRIEVAL] module=%s has empty filter_fields — Analysis Agent returned no fields. "
                "Projecting all columns so Execution Agent has usable data.",
                module,
            )

        # Step 3: apply filters — merge HTTP-level + module pre-filters
        # Fields that couldn't be mapped to SP params (e.g. ResolutionTAT) still
        # get applied here as exact post-filters on the raw records.
        combined_filters = {**this_module_filters, **filter_values}  # HTTP overrides pre-filter
        filtered = _apply_filters(raw_records, module_filter_fields, combined_filters)

        # Step 5: keep only relevant columns
        projected = _project_columns(filtered, module_filter_fields)

        output[module] = projected

        logger.info(
            "[RETRIEVAL] module=%s | raw=%d | after_filter=%d | columns_kept=%s",
            module,
            len(raw_records),
            len(filtered),
            list(module_filter_fields.keys()),
        )

    return output
