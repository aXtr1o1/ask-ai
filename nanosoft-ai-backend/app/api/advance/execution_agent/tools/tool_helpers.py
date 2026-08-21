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
  _clean_records            — convert NaN/NaT/inf values to None in a list of record dicts (keys kept)
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

    Matching is case-insensitive and normalises internal whitespace (collapses
    runs of spaces to one), so "Mail  Building" (double space, as DB may store it)
    matches a filter value of "Mail Building" (single space) — consistent with how
    the stored procedure's word-boundary regex finds records.

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

        # Collapse internal whitespace on both sides so "Mail  Building" (DB) matches
        # a filter value of "Mail Building" — the SP's word-boundary regex is looser
        # than an exact string match, so the tool filter must not be stricter than it.
        col = df[actual].fillna("").astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
        norm_value = " ".join(value.split())
        if norm_value == "":
            df = df[col == ""]
        else:
            df = df[col.str.lower() == norm_value.lower()]

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
        (filtered_df, None)          — on success
        (empty_df_like_df, error_dict) — on failure

    On failure an EMPTY DataFrame (same columns as df) is returned instead of the
    original unfiltered df, so a caller that forgets to check `err` before reusing
    `df` can never silently compute over unfiltered data.
    """
    try:
        return _apply_conditions(df, filters), None
    except ValueError as exc:
        return df.iloc[0:0], _err(str(exc))


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
    Convert NaN/NaT/inf scalars to None in a list of record dicts, for safe
    JSON serialization.

    Keys are always kept, even when their value is None. Dropping a None key
    (as this used to do) makes that record's dict shorter than its siblings;
    when such dicts are later reloaded into a DataFrame (e.g. by a downstream
    tool), pandas fills the "missing" column with NaN for every row that had
    it dropped, so the column silently becomes all-NaN and numeric tools then
    fail with "no usable numeric values" even though the data was legitimately
    None, not absent.

    Args:
        records: list of dicts (typically rows from df.to_dict("records"))

    Returns:
        list of dicts with NaN/NaT/inf values converted to None, same keys as input
    """
    return [{k: _nan_to_none(v) for k, v in row.items()} for row in records]


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