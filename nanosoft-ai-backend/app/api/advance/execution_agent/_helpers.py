"""
Execution Agent — Internal Helpers

  _is_unresolved_ref        — guard against unresolved $step_N strings in tool args
  _strip_markdown           — clean markdown code fences from LLM JSON responses
  _err                      — shorthand for a consistent error return dict
  load_records_as_dataframe — load one module's preprocessed records into a DataFrame
  resolve_column            — case-insensitive column name lookup in a DataFrame
  get_numeric_column        — get a column as a clean numeric Series
  _apply_conditions         — apply a list of {field, value} filters to a DataFrame
  _safe_apply               — apply filters, catching ValueError and returning _err dict
  _clean_records            — strip NaN/None values from a list of record dicts
  _nan_to_none              — convert NaN/NaT scalar to None for JSON serialization
"""
import math
import re
import pandas as pd
from typing import Any


# =============================================================================
# _is_unresolved_ref
# =============================================================================

def _is_unresolved_ref(val) -> bool:
    """
    Returns True when val is a string that still contains an unresolved
    $step_N reference.  Used as a defensive guard in tools.
    """
    if isinstance(val, str):
        stripped = val.strip()
        if stripped.startswith("$step_") or "$step_" in stripped:
            return True
    return False


# =============================================================================
# _strip_markdown
# =============================================================================

def _strip_markdown(raw: str) -> str:
    """Strip markdown code fences (e.g. ```json ... ```) from LLM output before JSON parsing."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.IGNORECASE)
        raw = raw.rstrip("`").strip()
    return raw


# =============================================================================
# load_records_as_dataframe
# =============================================================================

def load_records_as_dataframe(state_or_data, module: str) -> pd.DataFrame:
    """
    Load one module's records from the preprocessed data dict into a DataFrame.

    Accepts either:
      - The raw execution context dict: {"filtered_records": {"bdm": {"p_list": [...]}}}
      - The preprocessed data dict directly: {"bdm": {"p_list": [...]}}

    The preprocessing layer outputs:
        {
            "bdm":  {"p_list": [record_dict, ...], "p_count": 120},
            "ppm":  {"p_list": [record_dict, ...], "p_count": 80},
            ...
        }

    Args:
        state_or_data: execution context dict (has "filtered_records" key) or
                       preprocessed data dict directly
        module:        the module name to load (e.g. "bdm", "ppm")

    Returns:
        pd.DataFrame — one row per record, columns = field names
    """
    # Unwrap execution context if passed
    if "filtered_records" in state_or_data:
        preprocessed_data = state_or_data["filtered_records"]
    else:
        preprocessed_data = state_or_data

    module_data = preprocessed_data.get(module, {})
    records = module_data.get("p_list", [])

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records)


# =============================================================================
# resolve_column
# =============================================================================

def resolve_column(df: pd.DataFrame, column: str) -> str | None:
    """
    Case-insensitive column name lookup in a DataFrame.

    The retrieval layer trims records to filter_fields, but column names from
    the DB may have different casing than what the LLM produces.

    Returns:
        The actual column name as it exists in df.columns, or None if not found.
    """
    if column in df.columns:
        return column
    col_lower = column.lower()
    for c in df.columns:
        if c.lower() == col_lower:
            return c
    return None


# =============================================================================
# get_numeric_column
# =============================================================================

def get_numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    """
    Return the specified column as a clean numeric Series with non-numeric
    and NaN values dropped.

    Args:
        df:     DataFrame containing the column
        column: Exact column name (use resolve_column first if needed)

    Returns:
        pd.Series of float/int values — empty if no usable values exist
    """
    return pd.to_numeric(df[column], errors="coerce").dropna()


# =============================================================================
# _apply_conditions
# =============================================================================

def _apply_conditions(df: pd.DataFrame, conditions: list) -> pd.DataFrame:
    """
    Apply a list of {field, value} filter conditions to a DataFrame using AND logic.

    Each condition is a dict:
        {"field": "WoStatus", "value": "Open"}

    Matching is case-insensitive and strips leading/trailing whitespace.

    Args:
        df:         DataFrame to filter
        conditions: list of {"field": str, "value": str} dicts

    Returns:
        Filtered DataFrame — subset of rows where ALL conditions match.

    Raises:
        ValueError: if a field name is not found in df.columns.
    """
    for cond in conditions:
        field = cond.get("field", "")
        value = str(cond.get("value", ""))

        actual = resolve_column(df, field)
        if actual is None:
            raise ValueError(
                f"Filter field '{field}' not found. "
                f"Available columns: {sorted(df.columns.tolist())}"
            )

        col = df[actual].fillna("").astype(str).str.strip()
        if value == "":
            df = df[col == ""]
        else:
            df = df[col.str.lower() == value.lower()]

    return df


# =============================================================================
# _safe_apply
# =============================================================================

def _safe_apply(df: pd.DataFrame, filters: list) -> tuple:
    """Apply a filter list to a DataFrame, converting ValueError to an _err dict.

    _apply_conditions raises ValueError when a filter field is not found in the
    DataFrame. _safe_apply catches that and returns it as an error dict so every
    tool can handle filter failures with a single clean check:

        df, err = _safe_apply(df, filters)
        if err:
            return err

    Returns:
        (filtered_df, None)       — on success
        (original_df, error_dict) — on failure
    """
    try:
        return _apply_conditions(df, filters), None
    except ValueError as exc:
        return df, _err(str(exc))


# =============================================================================
# _err
# =============================================================================

def _err(msg: str) -> dict:
    """Return a consistent error dict. Used by all tools to signal failure."""
    return {"_result_type": "error", "error": msg}


# =============================================================================
# _clean_records
# =============================================================================

def _clean_records(records: list[dict]) -> list[dict]:
    """
    Strip NaN/None values from a list of record dicts.

    Converts NaN/NaT scalars to None and removes keys whose value is None,
    producing clean dicts that are safe for JSON serialization.

    Args:
        records: list of dicts (typically rows from df.to_dict("records"))

    Returns:
        list of dicts with NaN/None keys removed
    """
    cleaned = []
    for row in records:
        clean_row = {k: _nan_to_none(v) for k, v in row.items()}
        cleaned.append({k: v for k, v in clean_row.items() if v is not None})
    return cleaned


# =============================================================================
# _nan_to_none
# =============================================================================

def _nan_to_none(val: Any) -> Any:
    """
    Convert a NaN, NaT, or +/-inf scalar to None for JSON serialization.
    All other values are returned unchanged.
    """
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    return val