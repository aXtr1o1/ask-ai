"""
Retrieval — Data Loader and Filter Function

get_filtered_records(modules, filter_fields, filter_values)
  → loads each module's JSON file
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
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("advance.retrieval")

# The JSON data files live in the same folder as this file
_DATA_DIR = Path(__file__).parent


# =============================================================================
# STEP 1: Load raw JSON records for a module
#
# Each module has its own JSON file: bdm.json, ppm.json, assets.json, fa.json, sb.json
#
# Called by: get_filtered_records
# =============================================================================
def _load_module_data(module: str) -> list[dict]:
    """Load all raw records from the JSON file for a given module."""
    path = _DATA_DIR / f"{module}.json"
    if not path.exists():
        logger.warning("[RETRIEVAL] File not found: %s", path)
        return []
    return json.loads(path.read_text(encoding="utf-8"))


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
            continue   # skip empty filter values

        # Only filter on columns that are defined for this module
        if column_name not in filter_fields:
            continue

        # Keep only rows where the column contains the filter value (case-insensitive)
        result = [
            row for row in result
            if str(filter_value).lower() in str(row.get(column_name, "")).lower()
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
    """Keep only the columns whose names are defined as keys in filter_fields."""
    keep_columns = set(filter_fields.keys())   # keys are already the column names
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
) -> dict[str, list[dict]]:
    """
    For each module:
      1. Load raw records from its JSON file
      2. Apply module-level pre-filters (from question definition)
      3. Apply HTTP-level filters (from request, flat dict)
      4. Project to only the relevant columns (defined in filter_fields)
    Returns { module_name: [filtered_rows] }

    filter_values      — flat dict applied to all modules: {"BuildingName": "Tower A"}
    module_filter_values — per-module pre-filters: {"bdm": {"WoStatus": "Closed"}, "ppm": {"PPMStatus": "Closed"}}
    """
    output: dict[str, list[dict]] = {}

    for module in modules:
        # Step 1: load raw data
        raw_records = _load_module_data(module)

        # Step 2: get this module's column definitions
        module_filter_fields = filter_fields.get(module, {})

        # Step 3: apply module-level pre-filters (from question definition)
        pre_filtered = raw_records
        if module_filter_values and module in module_filter_values:
            module_pre_filter = module_filter_values[module]
            # Apply directly — no filter_fields guard, these are always valid
            for col, val in module_pre_filter.items():
                if val:
                    pre_filtered = [
                        row for row in pre_filtered
                        if str(val).lower() in str(row.get(col, "")).lower()
                    ]
                    logger.info(
                        "[RETRIEVAL] module=%s | pre-filter col=%s val=%s → %d records",
                        module, col, val, len(pre_filtered),
                    )

        # Step 4: apply HTTP-level filters (flat, applies to all modules)
        filtered = _apply_filters(pre_filtered, module_filter_fields, filter_values)

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
