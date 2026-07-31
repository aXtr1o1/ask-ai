"""
FM Analytics Tools

The data passed to these tools is ALREADY filtered by the retrieval step.
Tools only perform the requested operation on the data they receive.
No additional filtering inside tools unless it is part of the operation semantics.

Tools:
   1.  count_records          → count all records or records matching condition(s)
   2.  sum_values             → sum a numeric field
   3.  get_average            → mean of a numeric field
   4.  get_minimum            → minimum value of a numeric field
   5.  get_maximum            → maximum value of a numeric field
   6.  calculate_time_between → elapsed minutes between two datetime fields
   7.  group_by_and_count     → group by a field and count per group
   8.  get_unique_values      → list all distinct values in a field
   9.  join_records           → match records from two modules on a shared key field
  10.  do_math                → arithmetic: ADD | SUB | MUL | DIV | MOD | POWER | SQRT | ABS
  11.  sort_and_limit         → sort a list from a prior step and optionally keep top/bottom N
  12.  group_by_and_aggregate → SUM | AVG | MIN | MAX of a numeric field per group
  13.  get_record_fields      → return actual record data — specific fields or all fields
  14.  final_answer_tool      → marks queue complete, MUST be the last step

  Phase 3-5 Intelligence Tools:
  15.  calculate_age_from_now    → days from a date field to today (WO aging, asset age)
  16.  group_by_time_period      → group records by month/week/quarter from a date field (trends)
  17.  calculate_mtbf            → mean time between failures per asset/group
  18.  calculate_weighted_score  → composite score from multiple weighted numeric fields
  19.  flag_by_threshold         → mark/count records where a field exceeds a threshold
  20.  calculate_rate_of_change  → % change between two numeric values (period-over-period)
  21.  calculate_percentile      → P50/P90/P95/P99 of a numeric field (outlier detection)
  22.  forecast_linear           → linear regression forecast on grouped time-series data
"""
import math
from datetime import datetime, timezone
from typing import Annotated

import numpy as np
import pandas as pd
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState


# =============================================================================
# INTERNAL HELPERS
# Not tools — used inside tools to load and extract data.
# =============================================================================

def load_records_as_dataframe(state: dict, module: str) -> pd.DataFrame:
    """
    Load the already-filtered records for a module into a pandas DataFrame.

    Only converts columns to numeric when every non-null value in that column
    is numeric. This prevents ID/code columns (e.g. '001', 'A-12') from being
    silently coerced to float and losing their string identity.

    Called by: all tools
    """
    records = state.get("filtered_records", {}).get(module, [])
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        non_null_original  = df[col].notna().sum()
        non_null_converted = converted.notna().sum()
        # Only apply numeric conversion when it succeeds for ALL non-null values
        if non_null_original > 0 and non_null_converted == non_null_original:
            df[col] = converted
    return df


def get_numeric_column(df: pd.DataFrame, field: str) -> pd.Series:
    """
    Return a clean numeric series for a column, dropping blanks and non-numeric values.

    Called by: sum_values, get_average, get_minimum, get_maximum
    """
    if field not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[field], errors="coerce").dropna()


def resolve_column(df: pd.DataFrame, field: str) -> str | None:
    """
    Resolve a field name to an actual DataFrame column name using case-insensitive matching.

    The LLM uses PascalCase names from module_fields (e.g. 'Complainer', 'AnalysisTechName'),
    but the stored procedure may return columns with different casing or slight name variations.
    This resolver finds the best match so tools don't fail on casing mismatches.

    Returns the actual column name if found, or None if no match exists.

    Called by: all field-dependent tools
    """
    if field in df.columns:
        return field  # exact match — fast path

    field_lower = field.lower()
    for col in df.columns:
        if col.lower() == field_lower:
            return col  # case-insensitive match

    return None  # no match found


def _apply_conditions(df: pd.DataFrame, conditions: list[dict]) -> pd.DataFrame:
    """
    Apply a list of AND-joined field=value conditions to a DataFrame.
    Each condition dict: {"field": str, "value": str}
    Matching is case-insensitive string comparison.
    Empty value matches blank/null rows.

    Called by: count_records (multi-condition path)
    """
    for cond in conditions:
        field = cond.get("field", "")
        value = cond.get("value", "")
        if not field:
            continue
        actual = resolve_column(df, field)
        if actual is None:
            continue
        col = df[actual].fillna("").astype(str).str.strip()
        if value == "":
            df = df[col == ""]
        else:
            df = df[col.str.lower() == str(value).lower()]
    return df


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


# =============================================================================
# TOOL 1: count_records
# =============================================================================
@tool
def count_records(
    module: str,
    state: Annotated[dict, InjectedState()],
    condition_field: str = "",
    condition_value: str = "",
    conditions: list | None = None,
) -> dict:
    """
    Count records in a module.

    Two modes:
      Single condition: pass condition_field and condition_value.
        Leave condition_field empty to count all records.
        Pass condition_value="" to count rows where the field is blank or null.

      Multi-condition AND: pass conditions as a list of dicts, e.g.:
        [{"field": "Status", "value": "Open"}, {"field": "Priority", "value": "High"}]
        All conditions are applied with AND logic.

    Args:
        module:          Data module name
        condition_field: Column to filter on (single condition, optional)
        condition_value: Value to match in condition_field; "" matches blank/null
        conditions:      List of {"field": str, "value": str} dicts for AND filtering
    """
    df = load_records_as_dataframe(state, module)

    if conditions:
        # Multi-condition AND path
        df = _apply_conditions(df, conditions)
        return {
            "module":     module,
            "count":      len(df),
            "conditions": conditions,
        }

    # Single-condition path (backward compatible)
    if condition_field:
        actual_field = resolve_column(df, condition_field)
        if actual_field:
            col = df[actual_field].fillna("").astype(str).str.strip()
            if condition_value == "":
                df = df[col == ""]
            else:
                df = df[col.str.lower() == condition_value.lower()]
    return {
        "module":          module,
        "count":           len(df),
        "condition_field": condition_field,
        "condition_value": condition_value,
    }


# =============================================================================
# TOOL 2: sum_values
# =============================================================================
@tool
def sum_values(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
    condition_field: str = "",
    condition_value: str = "",
) -> dict:
    """
    Sum all values in a numeric field across all records in a module.
    Optionally filter to rows where condition_field equals condition_value
    before summing.

    Args:
        module:          Data module name
        field:           Numeric column to sum
        condition_field: Column to filter on (optional)
        condition_value: Value to match in condition_field (optional)
    """
    df = load_records_as_dataframe(state, module)
    if condition_field:
        actual_cf = resolve_column(df, condition_field)
        if actual_cf:
            col = df[actual_cf].fillna("").astype(str).str.strip()
            df = df[col.str.lower() == condition_value.strip().lower()]
    actual_field = resolve_column(df, field)
    numbers = get_numeric_column(df, actual_field) if actual_field else pd.Series(dtype=float)
    return {
        "module":          module,
        "field":           field,
        "total_sum":       round(float(numbers.sum()), 4),
        "records_used":    int(numbers.count()),
        "condition_field": condition_field,
        "condition_value": condition_value,
    }


# =============================================================================
# TOOL 3: get_average
# =============================================================================
@tool
def get_average(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
    condition_field: str = "",
    condition_value: str = "",
) -> dict:
    """
    Compute the mean of a numeric field across all records in a module.
    Optionally filter to rows where condition_field equals condition_value
    before averaging.

    Args:
        module:          Data module name
        field:           Numeric column to average
        condition_field: Column to filter on (optional)
        condition_value: Value to match in condition_field (optional)
    """
    df = load_records_as_dataframe(state, module)
    if condition_field:
        actual_cf = resolve_column(df, condition_field)
        if actual_cf:
            col = df[actual_cf].fillna("").astype(str).str.strip()
            df = df[col.str.lower() == condition_value.strip().lower()]
    actual_field = resolve_column(df, field)
    numbers = get_numeric_column(df, actual_field) if actual_field else pd.Series(dtype=float)
    if numbers.empty:
        return {
            "module":          module,
            "field":           field,
            "average":         None,
            "records_used":    0,
            "condition_field": condition_field,
            "condition_value": condition_value,
        }
    return {
        "module":          module,
        "field":           field,
        "average":         round(float(numbers.mean()), 4),
        "records_used":    int(numbers.count()),
        "condition_field": condition_field,
        "condition_value": condition_value,
    }


# =============================================================================
# TOOL 4: get_minimum
# =============================================================================
@tool
def get_minimum(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
    condition_field: str = "",
    condition_value: str = "",
) -> dict:
    """
    Find the minimum value in a numeric field across all records in a module.
    Optionally filter to rows where condition_field equals condition_value first.

    Args:
        module:          Data module name
        field:           Numeric column to find the minimum of
        condition_field: Column to filter on (optional)
        condition_value: Value to match in condition_field (optional)
    """
    df = load_records_as_dataframe(state, module)
    if condition_field:
        actual_cf = resolve_column(df, condition_field)
        if actual_cf:
            col = df[actual_cf].fillna("").astype(str).str.strip()
            df = df[col.str.lower() == condition_value.strip().lower()]
    actual_field = resolve_column(df, field)
    numbers = get_numeric_column(df, actual_field) if actual_field else pd.Series(dtype=float)
    return {
        "module":          module,
        "field":           field,
        "minimum":         float(numbers.min()) if not numbers.empty else None,
        "records_used":    int(numbers.count()),
        "condition_field": condition_field,
        "condition_value": condition_value,
    }


# =============================================================================
# TOOL 5: get_maximum
# =============================================================================
@tool
def get_maximum(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
    condition_field: str = "",
    condition_value: str = "",
) -> dict:
    """
    Find the maximum value in a numeric field across all records in a module.
    Optionally filter to rows where condition_field equals condition_value first.

    Args:
        module:          Data module name
        field:           Numeric column to find the maximum of
        condition_field: Column to filter on (optional)
        condition_value: Value to match in condition_field (optional)
    """
    df = load_records_as_dataframe(state, module)
    if condition_field:
        actual_cf = resolve_column(df, condition_field)
        if actual_cf:
            col = df[actual_cf].fillna("").astype(str).str.strip()
            df = df[col.str.lower() == condition_value.strip().lower()]
    actual_field = resolve_column(df, field)
    numbers = get_numeric_column(df, actual_field) if actual_field else pd.Series(dtype=float)
    return {
        "module":          module,
        "field":           field,
        "maximum":         float(numbers.max()) if not numbers.empty else None,
        "records_used":    int(numbers.count()),
        "condition_field": condition_field,
        "condition_value": condition_value,
    }


# =============================================================================
# TOOL 6: calculate_time_between
# =============================================================================
@tool
def calculate_time_between(
    module: str,
    start_field: str,
    end_field: str,
    state: Annotated[dict, InjectedState()],
) -> dict:
    """
    Calculate elapsed time in minutes between two datetime columns, per record.
    Returns count, average, minimum, and maximum elapsed minutes across all records.
    Use for overall MTTR, response time, or resolution time across the whole dataset.
    To get elapsed time broken down by category, use group_by_and_aggregate instead.

    Args:
        module:      Data module name
        start_field: Column name containing the start datetime
        end_field:   Column name containing the end datetime
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"module": module, "total_records": 0, "stats": {}}

    actual_start = resolve_column(df, start_field)
    actual_end   = resolve_column(df, end_field)

    if actual_start is None or actual_end is None:
        missing = [f for f, a in [(start_field, actual_start), (end_field, actual_end)] if a is None]
        return {"module": module, "error": f"Column(s) not found: {missing}. Available: {list(df.columns)}", "stats": {}}

    df = df.copy()
    df["_start_dt"]     = pd.to_datetime(df[actual_start], dayfirst=True, errors="coerce")
    df["_end_dt"]       = pd.to_datetime(df[actual_end],   dayfirst=True, errors="coerce")
    df["_elapsed_mins"] = (df["_end_dt"] - df["_start_dt"]).dt.total_seconds() / 60

    valid_rows    = df.dropna(subset=["_elapsed_mins"])
    missing_count = len(df) - len(valid_rows)

    stats = {}
    if not valid_rows.empty:
        mins = valid_rows["_elapsed_mins"]
        stats = {
            "count":   int(mins.count()),
            "average": round(float(mins.mean()), 2),
            "minimum": round(float(mins.min()),  2),
            "maximum": round(float(mins.max()),  2),
        }

    return {
        "module":        module,
        "start_field":   start_field,
        "end_field":     end_field,
        "total_records": len(df),
        "calculated":    len(valid_rows),
        "missing_dates": missing_count,
        "stats":         stats,
    }


# =============================================================================
# TOOL 7: group_by_and_count
# =============================================================================
@tool
def group_by_and_count(
    module: str,
    group_field: str,
    state: Annotated[dict, InjectedState()],
    filter_field: str = "",
    filter_value: str = "",
) -> dict:
    """
    Group records by a field and count how many records fall in each group.
    Results are sorted from highest count to lowest.
    Optionally filter rows to only those where filter_field equals filter_value before grouping.

    Args:
        module:       Data module name
        group_field:  Column to group by
        filter_field: Column to filter on before grouping (optional)
        filter_value: Value to match in filter_field; "" matches blank/null rows
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"module": module, "group_field": group_field, "total_records": 0, "groups": []}

    if filter_field:
        actual_filter = resolve_column(df, filter_field)
        if actual_filter:
            col = df[actual_filter].fillna("").astype(str).str.strip()
            if filter_value == "":
                df = df[col == ""]
            else:
                df = df[col.str.lower() == filter_value.lower()]

    actual_group = resolve_column(df, group_field)
    if actual_group is None:
        return {
            "module":      module,
            "group_field": group_field,
            "error":       f"Column '{group_field}' does not exist in '{module}' data. Available columns: {list(df.columns)}",
            "total":       None,
            "groups":      None,
        }

    grouped = (
        df.groupby(actual_group, dropna=False)
          .size()
          .reset_index(name="count")
          .sort_values("count", ascending=False)
    )
    grouped = grouped.rename(columns={actual_group: group_field})

    return {
        "module":        module,
        "group_field":   group_field,
        "filter_field":  filter_field,
        "filter_value":  filter_value,
        "total_records": len(df),
        "unique_groups": len(grouped),
        "groups":        _clean_records(grouped.to_dict(orient="records")),
    }


# =============================================================================
# TOOL 8: get_unique_values
# =============================================================================
@tool
def get_unique_values(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
    filter_field: str = "",
    filter_value: str = "",
) -> dict:
    """
    Return all distinct values in a field across records in a module.
    Optionally filter rows where filter_field equals filter_value before extracting.

    Args:
        module:       Data module name
        field:        Column to extract unique values from
        filter_field: Optional column to filter on before extracting unique values
        filter_value: Value that filter_field must equal (case-insensitive)
    """
    df = load_records_as_dataframe(state, module)
    actual_field = resolve_column(df, field)
    if df.empty or actual_field is None:
        return {"module": module, "field": field, "unique_values": [], "count": 0}

    if filter_field and filter_value:
        actual_filter = resolve_column(df, filter_field)
        if actual_filter is not None:
            df = df[df[actual_filter].astype(str).str.lower() == filter_value.lower()]

    unique_set    = set(df[actual_field].dropna().astype(str).tolist())
    unique_sorted = sorted(unique_set)

    formatted_unique = [{module: module, field: v} for v in unique_sorted]

    return {
        "module":        module,
        "field":         field,
        "filter_field":  filter_field,
        "filter_value":  filter_value,
        "unique_values": formatted_unique,
        "count":         len(unique_sorted),
    }


# =============================================================================
# TOOL 9: join_records
# =============================================================================
@tool
def join_records(
    module_a: str,
    module_b: str,
    join_field: str,
    state: Annotated[dict, InjectedState()],
) -> dict:
    """
    Inner join two modules on a shared key field.
    Returns matched record count and unmatched counts per module.
    Use when a question spans two data sources and asks about their overlap.

    Args:
        module_a:   First data module name
        module_b:   Second data module name
        join_field: Column name present in both modules to join on
    """
    df_a = load_records_as_dataframe(state, module_a)
    df_b = load_records_as_dataframe(state, module_b)

    if df_a.empty or df_b.empty:
        return {
            "module_a":       module_a,
            "module_b":       module_b,
            "join_field":     join_field,
            "error":          "One or both modules returned no records.",
            "matched_count":  0,
            "unmatched_in_a": 0,
            "unmatched_in_b": 0,
            "records_in_a":   len(df_a),
            "records_in_b":   len(df_b),
        }

    actual_a = resolve_column(df_a, join_field)
    actual_b = resolve_column(df_b, join_field)

    missing = [m for m, a in [(module_a, actual_a), (module_b, actual_b)] if a is None]
    if missing:
        return {
            "module_a":       module_a,
            "module_b":       module_b,
            "join_field":     join_field,
            "error":          f"Column '{join_field}' not found in: {missing}",
            "matched_count":  0,
            "unmatched_in_a": 0,
            "unmatched_in_b": 0,
            "records_in_a":   len(df_a),
            "records_in_b":   len(df_b),
        }

    keys_a = set(df_a[actual_a].dropna().astype(str))
    keys_b = set(df_b[actual_b].dropna().astype(str))

    matched_keys = keys_a & keys_b
    only_in_a    = keys_a - keys_b
    only_in_b    = keys_b - keys_a

    df_a_str = df_a.copy()
    df_b_str = df_b.copy()
    df_a_str[actual_a] = df_a_str[actual_a].astype(str)
    df_b_str[actual_b] = df_b_str[actual_b].astype(str)

    if actual_a != actual_b:
        df_b_str = df_b_str.rename(columns={actual_b: actual_a})

    joined = pd.merge(df_a_str, df_b_str, on=actual_a, how="inner")

    return {
        "module_a":       module_a,
        "module_b":       module_b,
        "join_field":     join_field,
        "records_in_a":   len(df_a),
        "records_in_b":   len(df_b),
        "matched_count":  len(joined),
        "unmatched_in_a": len(only_in_a),
        "unmatched_in_b": len(only_in_b),
    }


# =============================================================================
# TOOL 10: do_math
# =============================================================================
@tool
def do_math(
    operation: str,
    a,
    b=0,
) -> dict:
    """
    Perform arithmetic on two numbers.
    Operations: ADD | SUB | MUL | DIV | MOD | POWER | SQRT | ABS
    DIV: a / b  — SQRT and ABS only use a.
    DIV by zero returns null safely. SQRT and ABS use only a.

    a and b can be literal numbers or $step_N.key references resolving to numbers.

    Args:
        operation: ADD | SUB | MUL | DIV | MOD | POWER | SQRT | ABS
        a:         First number (or $step_N.key reference resolved to a number)
        b:         Second number (unused for SQRT and ABS). Default 0.
    """
    def _to_float(v, default=0.0):
        if v is None:
            return default
        try:
            # Handle numpy scalar types and Python strings/ints/floats
            return float(v)
        except (TypeError, ValueError):
            return default

    a = _to_float(a)
    b = _to_float(b)

    op = operation.upper()
    try:
        if   op == "ADD":   result = a + b
        elif op == "SUB":   result = a - b
        elif op == "MUL":   result = a * b
        elif op == "DIV":   result = (a / b) if b != 0 else None
        elif op == "MOD":   result = (a % b) if b != 0 else None
        elif op == "POWER": result = a ** b
        elif op == "SQRT":  result = math.sqrt(a) if a >= 0 else None
        elif op == "ABS":   result = abs(a)
        else:
            return {"error": f"Unknown operation '{op}'. Valid: ADD | SUB | MUL | DIV | MOD | POWER | SQRT | ABS"}
    except Exception as error:
        return {"error": str(error)}

    return {
        "operation": op,
        "a":         a,
        "b":         b,
        "result":    round(result, 6) if isinstance(result, float) else result,
    }


# =============================================================================
# TOOL 11: sort_and_limit
# =============================================================================
@tool
def sort_and_limit(
    data: list,
    sort_by: str = "",
    order: str = "DESC",
    limit: int = 0,
) -> dict:
    """
    Sort a list from a previous step and optionally keep only the top/bottom N items.
    Use after group_by_and_count, group_by_and_aggregate, group_by_time_period,
    calculate_mtbf, or get_unique_values.

    data must be a $step_N.key reference that resolves to a list (e.g. $step_N.groups).
    order DESC = highest first, ASC = lowest first. limit 0 means keep all.

    Args:
        data:    The list to sort — MUST be a $step_N.key ref pointing to a list.
        sort_by: Field name to sort by (for lists of dicts). Leave empty to skip sort.
        order:   "DESC" (highest first) or "ASC" (lowest first). Default: "DESC".
        limit:   Keep only the first N items after sorting. 0 = keep all.
    """
    if not isinstance(data, list):
        return {"error": f"'data' must be a list, got {type(data).__name__}"}

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 0

    if not data:
        return {"sorted_data": [], "total_in": 0, "total_out": 0,
                "sort_by": sort_by, "order": order.upper(), "limit": limit}

    ascending = order.upper() == "ASC"

    try:
        if isinstance(data[0], dict):
            if sort_by:
                df_sort = pd.DataFrame(data)
                if sort_by in df_sort.columns:
                    col = df_sort[sort_by]
                    numeric_col = pd.to_numeric(col, errors="coerce")
                    if numeric_col.notna().sum() == col.notna().sum():
                        df_sort[sort_by] = numeric_col
                    else:
                        df_sort[sort_by] = col.astype(str)
                    df_sort = df_sort.sort_values(sort_by, ascending=ascending, na_position="last")
                sorted_data = _clean_records(df_sort.to_dict(orient="records"))
            else:
                sorted_data = list(data)
        else:
            def _scalar_key(v):
                if v is None:
                    return (1, "")
                try:
                    return (0, f"{float(v):020.6f}")
                except (TypeError, ValueError):
                    return (0, str(v))
            sorted_data = sorted(data, key=_scalar_key, reverse=not ascending)

    except Exception as exc:
        return {"error": f"Sort failed: {exc}"}

    if limit and limit > 0:
        sorted_data = sorted_data[:limit]

    return {
        "sorted_data": sorted_data,
        "total_in":    len(data),
        "total_out":   len(sorted_data),
        "sort_by":     sort_by,
        "order":       order.upper(),
        "limit":       limit,
    }


# =============================================================================
# TOOL 12: group_by_and_aggregate
# =============================================================================
@tool
def group_by_and_aggregate(
    module: str,
    group_field: str,
    agg_field: str,
    operation: str,
    state: Annotated[dict, InjectedState()],
    filter_field: str = "",
    filter_value: str = "",
) -> dict:
    """
    Group records by a field and compute SUM | AVG | MIN | MAX of a numeric
    field per group. Results are sorted highest value first.
    Optionally filter rows before grouping.

    Use for per-category MTTR (avg time per status/location), per-project cost, etc.

    Args:
        module:       Data module name
        group_field:  Column to group by
        agg_field:    Numeric column to aggregate
        operation:    SUM | AVG | MIN | MAX
        filter_field: Column to filter on before grouping (optional)
        filter_value: Value to match in filter_field (optional)
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {
            "module": module, "group_field": group_field, "agg_field": agg_field,
            "operation": operation.upper(), "total_records": 0, "unique_groups": 0, "groups": [],
        }

    if filter_field:
        actual_ff = resolve_column(df, filter_field)
        if actual_ff:
            col = df[actual_ff].fillna("").astype(str).str.strip()
            df = df[col.str.lower() == filter_value.strip().lower()]

    actual_group = resolve_column(df, group_field)
    actual_agg   = resolve_column(df, agg_field)

    if actual_group is None:
        return {"error": f"Column '{group_field}' not found in '{module}'. Available: {list(df.columns)}"}
    if actual_agg is None:
        return {"error": f"Column '{agg_field}' not found in '{module}'. Available: {list(df.columns)}"}

    op = operation.upper()
    agg_fn_map = {"SUM": "sum", "AVG": "mean", "MIN": "min", "MAX": "max"}
    if op not in agg_fn_map:
        return {"error": f"Unknown operation '{op}'. Valid: SUM | AVG | MIN | MAX"}

    df = df.copy()
    df[actual_agg] = pd.to_numeric(df[actual_agg], errors="coerce")

    grouped = (
        df.groupby(actual_group, dropna=False)[actual_agg]
        .agg(agg_fn_map[op])
        .round(4)
        .reset_index()
        .rename(columns={actual_agg: "value", actual_group: group_field})
        .sort_values("value", ascending=False)
    )

    return {
        "module":        module,
        "group_field":   group_field,
        "agg_field":     agg_field,
        "operation":     op,
        "filter_field":  filter_field,
        "filter_value":  filter_value,
        "total_records": int(df[actual_agg].notna().sum()),
        "unique_groups": len(grouped),
        "groups":        _clean_records(grouped.to_dict(orient="records")),
    }


# =============================================================================
# TOOL 13: get_record_fields
# =============================================================================
@tool
def get_record_fields(
    module: str,
    state: Annotated[dict, InjectedState()],
    fields: list | None = None,
) -> dict:
    """
    Return the actual record data from a module.
    Use when the question asks for the details, attributes, or field values
    of specific records — not a count, sum, or aggregate.

    Args:
        module: Data module name.
        fields: Optional list of field names to include. If empty or None, returns all fields.
                Use to return only the columns relevant to the question.
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"module": module, "total": 0, "records": [], "fields_returned": []}

    if isinstance(fields, str):
        fields = [f.strip() for f in fields.split(",") if f.strip()]

    if fields:
        resolved = [resolve_column(df, f) for f in fields]
        selected_cols = [c for c in resolved if c is not None]
        if selected_cols:
            df = df[selected_cols]

    internal_fields = ["user_id", "user_name", "created_at", "updated_at", "_matched_fields"]
    cols_to_drop = [c for c in internal_fields if c in df.columns]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    return {
        "module":          module,
        "total":           len(df),
        "fields_returned": list(df.columns),
        "records":         _clean_records(df.to_dict(orient="records")),
    }


# =============================================================================
# TOOL 14: final_answer_tool
# =============================================================================
@tool
def final_answer_tool(result_ref) -> dict:
    """
    Completion marker. Always the LAST step in the execution queue.
    Signals that all computation steps have been completed successfully.
    result_ref receives the resolved value of the final computed answer.

    When the answer is a single value or list: result_ref = a single $step_N.key
    When the answer has multiple named parts: result_ref = a JSON dict where
      each key is a descriptive label and each value is a $step_N.key reference

    Args:
        result_ref: The final computed answer — any type (number, string, dict, list).
                    Resolved from a $step_N.key reference by the queue runner.
    """
    return {
        "status":      "complete",
        "final_value": result_ref,
    }


# =============================================================================
# TOOL 15: calculate_age_from_now
# =============================================================================
@tool
def calculate_age_from_now(
    module: str,
    date_field: str,
    state: Annotated[dict, InjectedState()],
    group_field: str = "",
    filter_field: str = "",
    filter_value: str = "",
) -> dict:
    """
    Calculate the age in days from a date field to today for each record.
    Use for work order aging, asset age, overdue detection, backlog analysis.

    Returns overall stats (avg/min/max age in days) and optionally a per-group breakdown.

    Args:
        module:       Data module name
        date_field:   Column containing the reference date (creation date, reported date, etc.)
        group_field:  Optional column to group age stats by (e.g. location, category, priority)
        filter_field: Optional column to pre-filter rows before age calculation
        filter_value: Value to match in filter_field
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"module": module, "date_field": date_field, "total_records": 0,
                "avg_age_days": None, "max_age_days": None, "min_age_days": None,
                "ages": [], "groups": []}

    if filter_field:
        actual_ff = resolve_column(df, filter_field)
        if actual_ff:
            col = df[actual_ff].fillna("").astype(str).str.strip()
            df = df[col.str.lower() == filter_value.strip().lower()]

    actual_date = resolve_column(df, date_field)
    if actual_date is None:
        return {"module": module, "date_field": date_field,
                "error": f"Column '{date_field}' not found. Available: {list(df.columns)}"}

    df = df.copy()
    today = pd.Timestamp.now(tz=None).normalize()
    df["_date_parsed"] = pd.to_datetime(df[actual_date], dayfirst=True, errors="coerce")
    df["_age_days"]    = (today - df["_date_parsed"]).dt.days

    valid = df.dropna(subset=["_age_days"])
    ages  = valid["_age_days"].astype(int)

    result = {
        "module":        module,
        "date_field":    date_field,
        "filter_field":  filter_field,
        "filter_value":  filter_value,
        "total_records": len(df),
        "calculated":    len(valid),
        "avg_age_days":  round(float(ages.mean()), 2) if not ages.empty else None,
        "max_age_days":  int(ages.max())              if not ages.empty else None,
        "min_age_days":  int(ages.min())              if not ages.empty else None,
    }

    if group_field:
        actual_group = resolve_column(valid, group_field)
        if actual_group:
            grouped = (
                valid.groupby(actual_group, dropna=False)["_age_days"]
                .agg(["mean", "max", "count"])
                .round(2)
                .reset_index()
                .rename(columns={"mean": "avg_age_days", "max": "max_age_days",
                                 "count": "record_count", actual_group: group_field})
                .sort_values("avg_age_days", ascending=False)
            )
            result["groups"]      = _clean_records(grouped.to_dict(orient="records"))
            result["group_field"] = group_field
        else:
            result["groups"] = []
    else:
        result["groups"] = []

    return result


# =============================================================================
# TOOL 16: group_by_time_period
# =============================================================================
@tool
def group_by_time_period(
    module: str,
    date_field: str,
    state: Annotated[dict, InjectedState()],
    period: str = "month",
    agg_field: str = "",
    operation: str = "COUNT",
    filter_field: str = "",
    filter_value: str = "",
) -> dict:
    """
    Group records by a time period (month / week / quarter / year) from a date column.
    Use for trend analysis, month-over-month changes, workload distribution over time.

    When agg_field is empty, counts records per period (how many WOs per month).
    When agg_field is provided with operation SUM/AVG/MIN/MAX, aggregates that numeric field.

    Args:
        module:       Data module name
        date_field:   Column containing the date to group by
        period:       "month" | "week" | "quarter" | "year"  (default: "month")
        agg_field:    Optional numeric field to aggregate per period (empty = COUNT)
        operation:    COUNT | SUM | AVG | MIN | MAX  (default: COUNT)
        filter_field: Optional column to pre-filter rows
        filter_value: Value to match in filter_field
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"module": module, "date_field": date_field, "period": period,
                "total_records": 0, "operation": operation.upper(), "periods": []}

    if filter_field:
        actual_ff = resolve_column(df, filter_field)
        if actual_ff:
            col = df[actual_ff].fillna("").astype(str).str.strip()
            df = df[col.str.lower() == filter_value.strip().lower()]

    actual_date = resolve_column(df, date_field)
    if actual_date is None:
        return {"module": module, "date_field": date_field,
                "error": f"Column '{date_field}' not found. Available: {list(df.columns)}"}

    df = df.copy()
    df["_dt"] = pd.to_datetime(df[actual_date], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["_dt"])

    period_lower = period.lower()
    freq_map = {"month": "ME", "week": "W", "quarter": "QE", "year": "YE"}
    label_fmt = {"month": "%Y-%m", "week": "%Y-W%W", "quarter": None, "year": "%Y"}

    if period_lower not in freq_map:
        return {"error": f"Invalid period '{period}'. Valid: month | week | quarter | year"}

    # Build period label
    if period_lower == "quarter":
        df["_period"] = df["_dt"].dt.to_period("Q").astype(str)
    else:
        df["_period"] = df["_dt"].dt.strftime(label_fmt[period_lower])

    op = operation.upper()
    agg_fn_map = {"COUNT": "size", "SUM": "sum", "AVG": "mean", "MIN": "min", "MAX": "max"}
    if op not in agg_fn_map:
        return {"error": f"Invalid operation '{op}'. Valid: COUNT | SUM | AVG | MIN | MAX"}

    if op == "COUNT" or not agg_field:
        grouped = (
            df.groupby("_period", sort=True)
              .size()
              .reset_index(name="count")
              .rename(columns={"_period": "period_label"})
        )
        value_key = "count"
    else:
        actual_agg = resolve_column(df, agg_field)
        if actual_agg is None:
            return {"error": f"agg_field '{agg_field}' not found. Available: {list(df.columns)}"}
        df[actual_agg] = pd.to_numeric(df[actual_agg], errors="coerce")
        grouped = (
            df.groupby("_period", sort=True)[actual_agg]
              .agg(agg_fn_map[op])
              .round(4)
              .reset_index()
              .rename(columns={"_period": "period_label", actual_agg: "value"})
        )
        value_key = "value"

    periods_list = _clean_records(grouped.to_dict(orient="records"))

    return {
        "module":        module,
        "date_field":    date_field,
        "period":        period_lower,
        "operation":     op,
        "agg_field":     agg_field,
        "filter_field":  filter_field,
        "filter_value":  filter_value,
        "total_records": len(df),
        "period_count":  len(periods_list),
        "value_key":     value_key,
        "periods":       periods_list,
    }


# =============================================================================
# TOOL 17: calculate_mtbf
# =============================================================================
@tool
def calculate_mtbf(
    module: str,
    asset_field: str,
    failure_date_field: str,
    state: Annotated[dict, InjectedState()],
    filter_field: str = "",
    filter_value: str = "",
) -> dict:
    """
    Calculate Mean Time Between Failures (MTBF) per asset.
    Sorts failure events by date for each asset, then computes the average
    number of days between consecutive failures.

    Use for asset reliability analysis, predictive maintenance prioritization.

    Args:
        module:             Data module name containing failure/work order records
        asset_field:        Column identifying the asset (e.g. AssetTagNo, AssetName)
        failure_date_field: Column containing the failure/event date
        filter_field:       Optional column to pre-filter records (e.g. only breakdowns)
        filter_value:       Value to match in filter_field
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"module": module, "asset_field": asset_field,
                "failure_date_field": failure_date_field,
                "total_records": 0, "overall_avg_mtbf_days": None, "mtbf_by_asset": []}

    if filter_field:
        actual_ff = resolve_column(df, filter_field)
        if actual_ff:
            col = df[actual_ff].fillna("").astype(str).str.strip()
            df = df[col.str.lower() == filter_value.strip().lower()]

    actual_asset = resolve_column(df, asset_field)
    actual_date  = resolve_column(df, failure_date_field)

    if actual_asset is None:
        return {"error": f"asset_field '{asset_field}' not found. Available: {list(df.columns)}"}
    if actual_date is None:
        return {"error": f"failure_date_field '{failure_date_field}' not found. Available: {list(df.columns)}"}

    df = df.copy()
    df["_dt"] = pd.to_datetime(df[actual_date], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["_dt"])
    df = df.sort_values([actual_asset, "_dt"])

    mtbf_rows = []
    for asset_id, group in df.groupby(actual_asset, sort=False):
        dates = group["_dt"].reset_index(drop=True)
        if len(dates) < 2:
            mtbf_rows.append({
                asset_field:       str(asset_id),
                "failure_count":   int(len(dates)),
                "mtbf_days":       None,
            })
            continue
        gaps = dates.diff().dt.days.dropna()
        mtbf_rows.append({
            asset_field:     str(asset_id),
            "failure_count": int(len(dates)),
            "mtbf_days":     round(float(gaps.mean()), 2),
        })

    mtbf_df = pd.DataFrame(mtbf_rows).sort_values("mtbf_days", ascending=True)
    valid_mtbf = [r["mtbf_days"] for r in mtbf_rows if r["mtbf_days"] is not None]
    overall    = round(float(np.mean(valid_mtbf)), 2) if valid_mtbf else None

    return {
        "module":               module,
        "asset_field":          asset_field,
        "failure_date_field":   failure_date_field,
        "filter_field":         filter_field,
        "filter_value":         filter_value,
        "total_records":        len(df),
        "assets_analyzed":      len(mtbf_rows),
        "overall_avg_mtbf_days": overall,
        "mtbf_by_asset":        _clean_records(mtbf_df.to_dict(orient="records")),
    }


# =============================================================================
# TOOL 18: calculate_weighted_score
# =============================================================================
@tool
def calculate_weighted_score(
    module: str,
    score_components: list,
    state: Annotated[dict, InjectedState()],
    group_field: str = "",
    normalize: bool = True,
) -> dict:
    """
    Compute a composite weighted score from multiple numeric fields.
    Use for building performance scoring, vendor ranking, asset health scoring.

    score_components is a list of dicts, each with:
      field:  column name to use (must be numeric)
      weight: relative weight (0.0–1.0). Weights need not sum to 1 — they are normalized.
      invert: true if lower values are better (e.g. breach rate, downtime).
              When invert=true, the field's contribution is (max - value) instead of value.

    When group_field is provided, scores are computed per group (e.g. per building).

    Args:
        module:            Data module name
        score_components:  List of {"field": str, "weight": float, "invert": bool}
        group_field:       Optional column to score per group (e.g. BuildingName)
        normalize:         Normalize each field to 0–100 scale before weighting. Default true.
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"module": module, "total_records": 0, "avg_score": None,
                "scores": [], "components_used": []}

    if not score_components:
        return {"error": "score_components must be a non-empty list of {field, weight, invert}"}

    df = df.copy()
    components_used = []
    weighted_cols   = []

    total_weight = sum(float(c.get("weight", 1)) for c in score_components)
    if total_weight == 0:
        return {"error": "Total weight of all components cannot be zero."}

    for comp in score_components:
        field   = comp.get("field", "")
        weight  = float(comp.get("weight", 1))
        invert  = bool(comp.get("invert", False))

        actual = resolve_column(df, field)
        if actual is None:
            continue

        series = pd.to_numeric(df[actual], errors="coerce")
        if series.dropna().empty:
            continue

        if normalize:
            mn, mx = series.min(), series.max()
            if mx != mn:
                series = (series - mn) / (mx - mn) * 100
            else:
                series = pd.Series([50.0] * len(series), index=series.index)

        if invert:
            series = 100 - series

        col_name = f"_score_{field}"
        df[col_name] = series * (weight / total_weight)
        weighted_cols.append(col_name)
        components_used.append({"field": field, "weight": weight, "invert": invert})

    if not weighted_cols:
        return {"error": "No valid numeric component fields found in the data."}

    df["_composite_score"] = df[weighted_cols].sum(axis=1).round(4)

    if group_field:
        actual_group = resolve_column(df, group_field)
        if actual_group:
            agg = (
                df.groupby(actual_group)["_composite_score"]
                  .mean()
                  .round(4)
                  .reset_index()
                  .rename(columns={actual_group: group_field, "_composite_score": "score"})
                  .sort_values("score", ascending=False)
            )
            scores = _clean_records(agg.to_dict(orient="records"))
        else:
            scores = []
    else:
        scores = []

    overall = df["_composite_score"]
    return {
        "module":           module,
        "group_field":      group_field,
        "components_used":  components_used,
        "total_records":    len(df),
        "avg_score":        round(float(overall.mean()), 4),
        "max_score":        round(float(overall.max()), 4),
        "min_score":        round(float(overall.min()), 4),
        "scores":           scores,
    }


# =============================================================================
# TOOL 19: flag_by_threshold
# =============================================================================
@tool
def flag_by_threshold(
    module: str,
    field: str,
    threshold,
    state: Annotated[dict, InjectedState()],
    operator: str = "gt",
    group_field: str = "",
    label_field: str = "",
    filter_field: str = "",
    filter_value: str = "",
) -> dict:
    """
    Flag records where a numeric field satisfies a threshold condition.
    Use for risk flagging, SLA breach detection, overdue identification.

    operator options: gt (>), lt (<), gte (>=), lte (<=), eq (==)

    Returns: flagged record count, total records, ratio, and optionally
    flagged record labels and a per-group breakdown.

    Args:
        module:       Data module name
        field:        Numeric field to evaluate
        threshold:    Threshold value to compare against
        operator:     gt | lt | gte | lte | eq  (default: "gt")
        group_field:  Optional column to count flagged records per group
        label_field:  Optional column to include in flagged records list (e.g. WO number)
        filter_field: Optional column to pre-filter records before flagging
        filter_value: Value to match in filter_field
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"module": module, "field": field, "threshold": threshold,
                "operator": operator, "flagged_count": 0, "total_records": 0,
                "flag_ratio": 0.0, "flagged_records": [], "groups": []}

    if filter_field:
        actual_ff = resolve_column(df, filter_field)
        if actual_ff:
            col = df[actual_ff].fillna("").astype(str).str.strip()
            df = df[col.str.lower() == filter_value.strip().lower()]

    actual_field = resolve_column(df, field)
    if actual_field is None:
        return {"error": f"Column '{field}' not found. Available: {list(df.columns)}"}

    df = df.copy()
    numeric_col = pd.to_numeric(df[actual_field], errors="coerce")
    df["_numeric"] = numeric_col

    try:
        thr = float(threshold)
    except (TypeError, ValueError):
        return {"error": f"threshold '{threshold}' cannot be converted to a number."}

    op = operator.lower()
    op_map = {
        "gt":  lambda s, t: s > t,
        "lt":  lambda s, t: s < t,
        "gte": lambda s, t: s >= t,
        "lte": lambda s, t: s <= t,
        "eq":  lambda s, t: s == t,
    }
    if op not in op_map:
        return {"error": f"Unknown operator '{op}'. Valid: gt | lt | gte | lte | eq"}

    mask    = op_map[op](df["_numeric"], thr)
    flagged = df[mask]
    total   = len(df)
    n_flag  = len(flagged)

    # Build flagged records list (only identifier + value columns to keep output small)
    flagged_records = []
    if label_field:
        actual_label = resolve_column(flagged, label_field)
        if actual_label:
            for _, row in flagged[[actual_label, actual_field]].iterrows():
                flagged_records.append({
                    label_field: _nan_to_none(row[actual_label]),
                    field:       _nan_to_none(row[actual_field]),
                })
    else:
        flagged_records = _clean_records(flagged.head(50).to_dict(orient="records"))

    # Per-group breakdown
    groups = []
    if group_field:
        actual_group = resolve_column(df, group_field)
        if actual_group:
            group_stats = []
            for grp_name, grp_df in df.groupby(actual_group, sort=False):
                grp_mask  = op_map[op](grp_df["_numeric"], thr)
                grp_flag  = int(grp_mask.sum())
                grp_total = len(grp_df)
                group_stats.append({
                    group_field:     _nan_to_none(grp_name),
                    "flagged_count": grp_flag,
                    "total":         grp_total,
                    "flag_ratio":    round(grp_flag / grp_total, 4) if grp_total else 0.0,
                })
            group_stats.sort(key=lambda r: r["flagged_count"], reverse=True)
            groups = group_stats

    return {
        "module":          module,
        "field":           field,
        "threshold":       thr,
        "operator":        op,
        "filter_field":    filter_field,
        "filter_value":    filter_value,
        "total_records":   total,
        "flagged_count":   n_flag,
        "flag_ratio":      round(n_flag / total, 4) if total else 0.0,
        "flagged_records": flagged_records,
        "group_field":     group_field,
        "groups":          groups,
    }


# =============================================================================
# TOOL 20: calculate_rate_of_change
# =============================================================================
@tool
def calculate_rate_of_change(
    a,
    b,
) -> dict:
    """
    Calculate the percentage change from value b (baseline) to value a (current).
    Formula: ((a - b) / b) * 100
    Use for period-over-period comparison: how much did WO count / cost change?

    a = current period value (resolved from a $step_N.key reference)
    b = previous / baseline period value (resolved from a $step_N.key reference)

    Returns pct_change (positive = increase, negative = decrease) and direction.

    Args:
        a: Current value (number or $step_N.key reference resolving to a number)
        b: Baseline value (number or $step_N.key reference resolving to a number)
    """
    def _to_float(v):
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    fa = _to_float(a)
    fb = _to_float(b)

    if fa is None or fb is None:
        return {
            "a": a, "b": b,
            "pct_change": None,
            "direction":  "unknown",
            "error":      "One or both input values could not be converted to a number.",
        }

    if fb == 0:
        return {
            "a": fa, "b": fb,
            "pct_change": None,
            "direction":  "unknown",
            "error":      "Baseline value (b) is zero — rate of change is undefined.",
        }

    pct = round(((fa - fb) / fb) * 100, 4)
    direction = "up" if pct > 0 else ("down" if pct < 0 else "flat")

    return {
        "a":          fa,
        "b":          fb,
        "pct_change": pct,
        "direction":  direction,
    }


# =============================================================================
# TOOL 21: calculate_percentile
# =============================================================================
@tool
def calculate_percentile(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
    percentiles: list | None = None,
    condition_field: str = "",
    condition_value: str = "",
) -> dict:
    """
    Compute percentile values (P50/P90/P95/P99) of a numeric field.
    Use for SLA benchmarking, outlier detection, and performance distribution analysis.

    percentiles is a list of integers e.g. [50, 90, 95, 99].
    If not provided, defaults to [50, 75, 90, 95, 99].

    Args:
        module:          Data module name
        field:           Numeric field to compute percentiles on
        percentiles:     List of integer percentile values (1–99). Default: [50, 75, 90, 95, 99]
        condition_field: Optional column to filter on before computing
        condition_value: Value to match in condition_field
    """
    df = load_records_as_dataframe(state, module)

    if percentiles is None:
        percentiles = [50, 75, 90, 95, 99]

    # Coerce each percentile to int
    try:
        percentiles = [int(p) for p in percentiles]
    except (TypeError, ValueError):
        return {"error": "percentiles must be a list of integers."}

    if df.empty:
        return {"module": module, "field": field, "records_used": 0,
                "percentile_values": {}, "mean": None, "std_dev": None}

    if condition_field:
        actual_cf = resolve_column(df, condition_field)
        if actual_cf:
            col = df[actual_cf].fillna("").astype(str).str.strip()
            df = df[col.str.lower() == condition_value.strip().lower()]

    actual_field = resolve_column(df, field)
    if actual_field is None:
        return {"error": f"Column '{field}' not found. Available: {list(df.columns)}"}

    series = pd.to_numeric(df[actual_field], errors="coerce").dropna()
    if series.empty:
        return {"module": module, "field": field, "records_used": 0,
                "percentile_values": {}, "mean": None, "std_dev": None}

    pct_values = {}
    for p in percentiles:
        p = max(1, min(99, p))
        pct_values[f"p{p}"] = round(float(np.percentile(series, p)), 4)

    return {
        "module":             module,
        "field":              field,
        "condition_field":    condition_field,
        "condition_value":    condition_value,
        "records_used":       int(len(series)),
        "percentile_values":  pct_values,
        "mean":               round(float(series.mean()), 4),
        "std_dev":            round(float(series.std()), 4),
    }


# =============================================================================
# TOOL 22: forecast_linear
# =============================================================================
@tool
def forecast_linear(
    data: list,
    periods_ahead: int = 3,
    value_key: str = "count",
    label_key: str = "period_label",
) -> dict:
    """
    Fit a simple linear regression on time-series grouped data and forecast
    future periods. Use after group_by_time_period to predict future workload,
    costs, or volume.

    data must be a $step_N.periods reference (a list of period dicts from
    group_by_time_period). Each dict must have a label and a numeric value.

    periods_ahead: how many future periods to forecast (default: 3)
    value_key:     key in each period dict that holds the numeric value (default: "count")
    label_key:     key in each period dict that holds the period label (default: "period_label")

    Args:
        data:          List of period dicts from group_by_time_period (via $step_N.periods)
        periods_ahead: Number of future periods to predict (default: 3)
        value_key:     Name of the numeric value key in each period dict
        label_key:     Name of the period label key in each period dict
    """
    if not isinstance(data, list) or len(data) < 2:
        return {"error": "forecast_linear requires at least 2 data points from group_by_time_period."}

    try:
        periods_ahead = int(periods_ahead)
    except (TypeError, ValueError):
        periods_ahead = 3

    values = []
    for row in data:
        if isinstance(row, dict):
            v = row.get(value_key)
            try:
                values.append(float(v))
            except (TypeError, ValueError):
                values.append(None)

    # Drop None values
    valid_pairs = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(valid_pairs) < 2:
        return {"error": "Not enough valid numeric values to fit a forecast model."}

    x = np.array([p[0] for p in valid_pairs], dtype=float)
    y = np.array([p[1] for p in valid_pairs], dtype=float)

    # Linear regression: y = mx + c
    n    = len(x)
    xm   = x.mean()
    ym   = y.mean()
    ssxx = ((x - xm) ** 2).sum()
    ssxy = ((x - xm) * (y - ym)).sum()

    slope     = ssxy / ssxx if ssxx != 0 else 0.0
    intercept = ym - slope * xm

    # R-squared
    y_pred = slope * x + intercept
    ss_res = ((y - y_pred) ** 2).sum()
    ss_tot = ((y - ym) ** 2).sum()
    r2     = 1 - (ss_res / ss_tot) if ss_tot != 0 else 1.0

    # Generate future period labels (simple sequential suffixes)
    last_label = data[-1].get(label_key, f"period_{len(data)-1}") if data else ""
    forecast_list = []
    last_x = len(data) - 1
    for i in range(1, periods_ahead + 1):
        future_x     = last_x + i
        predicted    = round(float(slope * future_x + intercept), 4)
        forecast_list.append({
            label_key:         f"{last_label}+{i}",
            "predicted_value": predicted,
        })

    return {
        "model_slope":     round(float(slope),     6),
        "model_intercept": round(float(intercept), 6),
        "r_squared":       round(float(r2),        6),
        "periods_ahead":   periods_ahead,
        "value_key":       value_key,
        "data_points":     len(valid_pairs),
        "forecast":        forecast_list,
    }


# =============================================================================
# ALL TOOLS — used by the planner for tool descriptions
# =============================================================================
ALL_TOOLS = [
    count_records,
    sum_values,
    get_average,
    get_minimum,
    get_maximum,
    calculate_time_between,
    group_by_and_count,
    get_unique_values,
    join_records,
    do_math,
    sort_and_limit,
    group_by_and_aggregate,
    get_record_fields,
    final_answer_tool,
    # Phase 3-5 Intelligence Tools
    calculate_age_from_now,
    group_by_time_period,
    calculate_mtbf,
    calculate_weighted_score,
    flag_by_threshold,
    calculate_rate_of_change,
    calculate_percentile,
    forecast_linear,
]
