"""
Preprocessing Layer — Between Retrieval and Execution

Purpose:
    Clean raw DB records BEFORE they reach the execution tools.
    This prevents tool crashes caused by bad data types, None values,
    malformed dates, and other data-quality issues from the database.
"""
import logging
import time
from typing import Any

from app.api.advance.preprocessing.field_type_map import FIELD_TYPE_MAP as _FIELD_TYPE_MAP

logger = logging.getLogger("advance.preprocessing")

DASH = "-" * 55


# =============================================================================
# DATE FORMAT PATTERNS
# =============================================================================
_DATE_FORMATS = [
    "%d-%m-%Y %H:%M:%S",   # "06-03-2026 15:32:58"
    "%d-%m-%Y",             # "13-01-2022"
    "%Y-%m-%dT%H:%M:%S",    # "2026-03-07T13:50:36"
    "%Y-%m-%d %H:%M:%S",    # "2026-03-07 13:50:36"
    "%Y-%m-%d",             # "2026-03-07"
    "%m/%d/%Y %H:%M:%S",    # US format with time
    "%m/%d/%Y",             # US date only
    "%d/%m/%Y",             # European slash format
]

_PARSE_FAILED = "__PARSE_FAILED__"   # sentinel returned by _clean_datetime on failure


# =============================================================================
# TYPE CLEANERS
# =============================================================================

def _clean_text(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _clean_bool(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return False


def _clean_int(v: Any) -> "int | None":
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _clean_bigint(v: Any) -> "int | None":
    return _clean_int(v)


def _clean_float(v: Any) -> "float | None":
    if v is None:
        return None
    if isinstance(v, bool):
        return float(int(v))
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _clean_numeric_str(v: Any) -> "float | None":
    """Money/value fields stored as text (e.g. '25000.00') → float."""
    return _clean_float(v)


def _clean_datetime(v: Any) -> "str | None":
    """
    Normalise any date/datetime string to 'YYYY-MM-DD HH:MM:SS'.
    """
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None

    for tz_sep in ("+", "Z"):
        idx = s.find(tz_sep, 10)
        if idx != -1:
            s = s[:idx]

    from datetime import datetime
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    try:
        from dateutil import parser as duparser
        return duparser.parse(s, dayfirst=True).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return _PARSE_FAILED


# =============================================================================
# CLEANER DISPATCH
# =============================================================================
_CLEANERS = {
    "text":        _clean_text,
    "bool":        _clean_bool,
    "int":         _clean_int,
    "bigint":      _clean_bigint,
    "float":       _clean_float,
    "numeric_str": _clean_numeric_str,
    "datetime":    _clean_datetime,
}


# =============================================================================
# SINGLE-RECORD CLEANER
# =============================================================================

def _preprocess_record(record: dict, module: str, counters: dict) -> dict:
    type_map = _FIELD_TYPE_MAP.get(module, {})
    cleaned  = {}

    for field, raw_value in record.items():
        type_tag = type_map.get(field)

        if type_tag and type_tag in _CLEANERS:
            value = _CLEANERS[type_tag](raw_value)

            if type_tag == "datetime" and value == _PARSE_FAILED:
                counters["date_failures"] += 1
                logger.debug(
                    "  %-8s  %-30s  unparseable date: %r  → None",
                    module, field, raw_value,
                )
                cleaned[field] = None
            else:
                counters[type_tag] = counters.get(type_tag, 0) + 1
                cleaned[field] = value
        else:
            if raw_value is None or isinstance(raw_value, (int, float, bool)):
                cleaned[field] = raw_value
            else:
                cleaned[field] = _clean_text(raw_value)

    return cleaned


# =============================================================================
# PUBLIC FUNCTION
# =============================================================================

def preprocess_records(filtered_records: dict[str, dict]) -> dict[str, dict]:
    """
    Clean all retrieved records for all modules before they reach the tools.
    Expects structure: { module: {"p_list": [records], "p_count": int} }
    """
    result = {}
    total_records  = sum(len(module_data.get("p_list", [])) for module_data in filtered_records.values())
    total_warnings = 0
    _start         = time.perf_counter()

    logger.info(DASH)
    logger.info(
        "PREPROCESS : %d module(s) | %d records total",
        len(filtered_records), total_records,
    )
    logger.info(DASH)

    for module, module_data in filtered_records.items():
        records = module_data.get("p_list", [])

        if not records:
            logger.info("  %-8s : 0 records (skipped — no data)", module)
            result[module] = module_data
            continue

        counters = {"date_failures": 0}
        cleaned_records = []

        for i, record in enumerate(records):
            try:
                cleaned_records.append(_preprocess_record(record, module, counters))
            except Exception as exc:
                logger.warning(
                    "  %-8s  record[%d]  unexpected error: %s  → kept original",
                    module, i, exc,
                )
                cleaned_records.append(record)

        tag_summary_parts = []
        for tag in ("bool", "datetime", "int", "bigint", "float", "numeric_str"):
            n = counters.get(tag, 0)
            if n:
                tag_summary_parts.append(f"{tag}={n}")
        tag_summary = "  ".join(tag_summary_parts) if tag_summary_parts else "text only"

        date_failures  = counters["date_failures"]
        total_warnings += date_failures
        failure_note   = f"{date_failures} bad date(s)→None" if date_failures else ""

        logger.info(
            "  %-8s : %4d records | %s%s",
            module, len(cleaned_records), tag_summary, failure_note,
        )
        
        result[module] = {
            "p_list": cleaned_records,
            "p_count": module_data.get("p_count", len(cleaned_records))
        }

    elapsed_ms = (time.perf_counter() - _start) * 1000
    logger.info(DASH)
    if total_warnings:
        logger.warning(
            "  WARNINGS   : %d date parse failure(s) → set to None",
            total_warnings,
        )
    else:
        logger.info("  WARNINGS   : none")
    logger.info("  TIME       : %.2f ms", elapsed_ms)
    logger.info(DASH)

    return result
