"""
Internal Helpers — shared across all tool modules.
Not tools — used inside tools to load and extract data.
"""
import math
import re

import pandas as pd


# =============================================================================
# _ID_COLUMN_SUFFIXES / _is_identifier_column
# =============================================================================

# Column name suffixes and prefixes that indicate an ID / code / reference field.
# These columns should NOT have numeric conversion applied even when every value
# parses as a number — e.g. "00123" must not silently become 123.
_ID_SUFFIXES  = ("no", "code", "id", "key", "barcode", "ref", "tag", "seq", "pk", "fk",
                 "workorder", "order")
_ID_PREFIXES  = ("is", "has", "dele")   # IsActive, HasRework, DeleStat


def _is_identifier_column(col_name: str) -> bool:
    """
    Heuristic: return True when a column is likely an ID / code / flag field
    that should stay as a string even if all values look numeric.
    """
    lower = col_name.lower()
    return (
        any(lower.endswith(s) for s in _ID_SUFFIXES) or
        any(lower.startswith(p) for p in _ID_PREFIXES)
    )


# =============================================================================
# load_records_as_dataframe
# =============================================================================

def load_records_as_dataframe(state: dict, module: str) -> pd.DataFrame:
    """
    Load the already-filtered records for a module into a pandas DataFrame.

    Numeric conversion is applied only when:
      1. The column name does NOT look like an identifier/code (see _is_identifier_column).
      2. Every non-null value in the column successfully converts to numeric.

    This prevents ID/code columns (e.g. '00123', 'A-12') from being silently
    coerced to float and losing their string identity.

    Called by: all tools
    """
    # Defensive: if LLM passed a resolved list as `module`, build DF from it directly.
    if isinstance(module, list):
        return pd.DataFrame(module) if module else pd.DataFrame()

    records = state.get("filtered_records", {}).get(module, [])
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    for col in df.columns:
        # Skip conversion for identifier-like column names
        if _is_identifier_column(col):
            continue

        # Skip columns where any non-null value has a leading zero — likely a code
        str_vals = df[col].dropna().astype(str)
        if str_vals.str.match(r'^0\d').any():
            continue

        converted = pd.to_numeric(df[col], errors="coerce")
        non_null_original  = df[col].notna().sum()
        non_null_converted = converted.notna().sum()
        # Only apply numeric conversion when it succeeds for ALL non-null values
        if non_null_original > 0 and non_null_converted == non_null_original:
            df[col] = converted
    return df


# =============================================================================
# get_numeric_column
# =============================================================================

def get_numeric_column(df: pd.DataFrame, field: str) -> "pd.Series":
    """
    Return a clean numeric series for a column, dropping blanks and non-numeric values.

    Called by: sum_values, get_average
    """
    if field not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[field], errors="coerce").dropna()


# =============================================================================
# resolve_column
# =============================================================================

def resolve_column(df: pd.DataFrame, field: str) -> str | None:
    """
    Resolve a field name to an actual DataFrame column name using case-insensitive matching.

    Handles:
      1. Direct / case-insensitive matching.
      2. Module prefix stripping (e.g. 'assets.AssetTagNo' -> 'AssetTagNo').
      3. Join suffix fallbacks (e.g. 'BuildingName' -> 'BuildingName_a' if renamed during join).
    """
    if not isinstance(field, str) or not field.strip():
        return None

    # Strip module prefix if present (e.g. 'assets.AssetTagNo' -> 'AssetTagNo')
    clean_field = field.strip()
    if "." in clean_field:
        clean_field = clean_field.split(".")[-1]

    if clean_field in df.columns:
        return clean_field

    clean_lower = clean_field.lower()
    for col in df.columns:
        if col.lower() == clean_lower:
            return col

    # Join suffix fallback (_a / _b)
    for col in df.columns:
        if col.lower() in (f"{clean_lower}_a", f"{clean_lower}_b"):
            return col

    return None

def _is_unresolved_ref(val) -> bool:
    """
    Returns True if the value is a string that looks like an unresolved $step_N reference.
    Used for defensive validation to prevent silent conversion errors if the runner
    failed to resolve a reference or the planner hallucinated a string.
    """
    if isinstance(val, str):
        val = val.strip()
        if val.startswith("$step_") or "$step_" in val:
            return True
    return False

# =============================================================================
# _apply_conditions
# =============================================================================

def _apply_conditions(
    df: pd.DataFrame,
    conditions: list[dict],
    invalid_fields: list | None = None,
) -> pd.DataFrame:
    """
    Apply a list of AND-joined field=value conditions to a DataFrame.
    Each condition dict: {"field": str, "value": str}
    Matching is case-insensitive string comparison.
    Empty value matches blank/null rows.

    If a field cannot be resolved or a value is an unresolved reference,
    raises ValueError. (The invalid_fields argument is deprecated but kept
    in signature temporarily for backwards compatibility until tools are updated).

    Called by: all tools that accept filters: list[dict]
    """
    if df.empty:
        return df

    # Group conditions by field name to support multiple values for the same field (OR/IN filtering)
    field_conditions: dict[str, list] = {}
    for cond in conditions:
        field = cond.get("field", "")
        value = cond.get("value", "")
        if not field:
            continue

        # Handle unresolved references — lists can contain $step_ refs too
        if isinstance(value, str) and _is_unresolved_ref(value):
            raise ValueError(f"Unresolved reference in filter: field='{field}', value='{value}'")
        if isinstance(value, list) and any(_is_unresolved_ref(v) for v in value if isinstance(v, str)):
            raise ValueError(f"Unresolved reference in filter: field='{field}', value contains unresolved $step refs")
        if _is_unresolved_ref(field):
            raise ValueError(f"Unresolved reference in filter: field='{field}', value='{value}'")

        if field not in field_conditions:
            field_conditions[field] = []
        if isinstance(value, list):
            field_conditions[field].extend(value)
        else:
            field_conditions[field].append(value)

    for field, values in field_conditions.items():
        actual = resolve_column(df, field)
        if actual is None:
            if invalid_fields is not None:
                invalid_fields.append(field)
            raise ValueError(f"Filter field '{field}' not found. Available columns: {sorted(df.columns.tolist())}")

        col = df[actual].fillna("").astype(str).str.strip()

        if len(values) > 1:
            # Multiple values for the same field -> OR / IN filter
            lower_vals = {str(v).strip().lower() for v in values if v is not None}
            df = df[col.str.lower().isin(lower_vals)]
        elif len(values) == 1:
            value = values[0]
            if isinstance(value, list):
                lower_vals = {str(v).strip().lower() for v in value if v is not None}
                df = df[col.str.lower().isin(lower_vals)]
            elif value == "":
                df = df[col == ""]
            else:
                val_str = str(value).strip().lower()
                if val_str in ("current_year", "this_year", "current year", "this year"):
                    import datetime
                    curr_yr = str(datetime.datetime.now().year)
                    if col.str.lower().str.contains(curr_yr, regex=False).any():
                        val_str = curr_yr
                    else:
                        extracted_years = col.str.extract(r'(\b20\d{2}\b)')[0].dropna()
                        if not extracted_years.empty:
                            val_str = str(extracted_years.max())
                        else:
                            val_str = curr_yr
                is_date_col = any(term in actual.lower() for term in ("date", "time", "dt", "period"))
                if is_date_col and len(val_str) <= 7:
                    df = df[col.str.lower().str.contains(val_str, regex=False)]
                else:
                    df = df[col.str.lower() == val_str]
    return df


# =============================================================================
# _nan_to_none / _clean_records
# =============================================================================

def _nan_to_none(v):
    """Convert a float NaN to Python None. Pass all other values through."""
    if isinstance(v, float) and math.isnan(v):
        return None
    # Handle numpy scalar types
    try:
        if hasattr(v, "item"):
            v = v.item()
    except Exception:
        pass
    return v


def _clean_records(records: list[dict]) -> list[dict]:
    """Replace NaN values with None in a list of dicts for clean JSON output."""
    return [{k: _nan_to_none(val) for k, val in row.items()} for row in records]
