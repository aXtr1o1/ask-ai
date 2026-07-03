"""
Retrieval — Data Loader + Filter Function

get_filtered_records(modules, filter_fields, filter_values)
  → loads each module's JSON
  → applies filter_values using filter_fields column map
  → returns { module: [filtered_rows] }

The filtered records go DIRECTLY to the tools — never to the LLM.
"""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("advance.retrieval")

_DATA_DIR = Path(__file__).parent


def _load_module(module: str) -> list[dict]:
    """Load raw JSON records for a module (assets / bdm / ppm / fa / sb)."""
    path = _DATA_DIR / f"{module}.json"
    if not path.exists():
        logger.warning("[RETRIEVAL] File not found: %s", path)
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _apply_filters(
    records: list[dict],
    filter_fields: dict[str, str],    # { filter_key → actual column name }
    filter_values: dict[str, Any],    # { filter_key → value from HTTP request }
) -> list[dict]:
    """
    For each non-null filter_value:
      - look up the actual column name from filter_fields
      - keep only records where that column contains the value (case-insensitive)
    """
    result = records
    for key, val in filter_values.items():
        if not val:
            continue
        col = filter_fields.get(key)
        if not col:
            continue
        result = [
            r for r in result
            if str(val).lower() in str(r.get(col, "")).lower()
        ]
        logger.info("[RETRIEVAL] filter '%s' (%s)=%s → %d records remaining", key, col, val, len(result))
    return result


def _project_columns(
    records: list[dict],
    filter_fields: dict[str, str],
) -> list[dict]:
    """
    Keep ONLY the columns listed as VALUES in filter_fields.
    Nothing else is added — no hardcoded ID fields.
    """
    keep_cols = set(filter_fields.values())
    return [{k: v for k, v in rec.items() if k in keep_cols} for rec in records]



def get_filtered_records(
    modules: list[str],
    filter_fields: dict[str, dict],
    filter_values: dict[str, Any],
) -> dict[str, list[dict]]:
    """
    Main retrieval function.
    1. Loads each module's JSON
    2. Applies filter_values (row filtering)
    3. Projects to only filter_fields columns (column filtering)
    Returns { module_name: [projected_filtered_records] }
    """
    output: dict[str, list[dict]] = {}
    for module in modules:
        raw = _load_module(module)
        module_filter_fields = filter_fields.get(module, {})
        filtered = _apply_filters(raw, module_filter_fields, filter_values)
        projected = _project_columns(filtered, module_filter_fields)
        output[module] = projected
        logger.info(
            "[RETRIEVAL] module=%s | raw=%d | filtered=%d | columns=%s",
            module, len(raw), len(filtered), list(module_filter_fields.values()),
        )
    return output
