"""
FM Analytics Tools

The data passed to these tools is ALREADY filtered by the retrieval step.
The tools only need to perform the requested operation on the data they receive.
No additional filtering inside tools — operations only.

Tools:
  1. count_records          → count all records in a module
  2. sum_values             → sum a numeric field
  3. get_average            → mean of a numeric field
  4. get_minimum            → minimum value of a numeric field
  5. get_maximum            → maximum value of a numeric field
  6. calculate_time_between → elapsed minutes between two datetime fields
  7. group_by_and_count     → group by a field and count per group
  8. get_unique_values      → list all distinct values in a field
  9. join_records           → match records from two modules on a shared key field
 10. do_math                → arithmetic: ADD | SUB | MUL | DIV | MOD | POWER | SQRT | ABS
"""
import math
from typing import Annotated

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
    'module' is one of: bdm, ppm, fa, assets, sb
    Columns that contain numbers stored as strings are automatically converted.

    Called by: all tools
    """
    records = state.get("filtered_records", {}).get(module, [])
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().sum() > 0:
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



#for the question how the data is beinf sned to the tool ..state: Annotated[dict, InjectedState()], this is the unput argument where the data is 
#being send as  the argument ok .. 

# =============================================================================
# TOOL 1: count_records
# =============================================================================
@tool
def count_records(
    module: str,
    state: Annotated[dict, InjectedState()],
    condition_field: str = "",
    condition_value: str = "",
    condition_field2: str = "",
    condition_value2: str = "",
) -> dict:
    """
    Count records in a module.
    Optionally filter to only rows where a field equals a specific value.
    Pass condition_value="" to count rows where the field is blank or null.
    Leave condition_field empty to count all records.
    Use condition_field2 + condition_value2 to apply a second simultaneous filter.

    Args:
        module:           Data module name
        condition_field:  First column to filter on (optional)
        condition_value:  Value to match in condition_field; "" matches blank/null
        condition_field2: Second column to filter on (optional, applied after first)
        condition_value2: Value to match in condition_field2; "" matches blank/null
    """
    df = load_records_as_dataframe(state, module)
    if condition_field and condition_field in df.columns:
        col = df[condition_field].fillna("").astype(str).str.strip()
        if condition_value == "":
            df = df[col == ""]
        else:
            df = df[col.str.lower() == condition_value.lower()]
    if condition_field2 and condition_field2 in df.columns:
        col2 = df[condition_field2].fillna("").astype(str).str.strip()
        if condition_value2 == "":
            df = df[col2 == ""]
        else:
            df = df[col2.str.lower() == condition_value2.lower()]
    return {
        "module":           module,
        "count":            len(df),
        "condition_field":  condition_field,
        "condition_value":  condition_value,
        "condition_field2": condition_field2,
        "condition_value2": condition_value2,
    }


# =============================================================================
# TOOL 2: sum_values
# =============================================================================
@tool
def sum_values(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
) -> dict:
    """
    Sum all values in a numeric field across all records in a module.

    Args:
        module: Data module name
        field:  Numeric column to sum
    """
    numbers = get_numeric_column(load_records_as_dataframe(state, module), field)
    return {
        "module":       module,
        "field":        field,
        "total_sum":    round(float(numbers.sum()), 4),
        "records_used": int(numbers.count()),
    }


# =============================================================================
# TOOL 3: get_average
# =============================================================================
@tool
def get_average(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
) -> dict:
    """
    Compute the mean of a numeric field across all records in a module.

    Args:
        module: Data module name
        field:  Numeric column to average
    """
    numbers = get_numeric_column(load_records_as_dataframe(state, module), field)
    if numbers.empty:
        return {"module": module, "field": field, "average": None, "records_used": 0}
    return {
        "module":       module,
        "field":        field,
        "average":      round(float(numbers.mean()), 4),
        "records_used": int(numbers.count()),
    }


# =============================================================================
# TOOL 4: get_minimum
# =============================================================================
@tool
def get_minimum(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
) -> dict:
    """
    Find the minimum value in a numeric field across all records in a module.

    Args:
        module: Data module name
        field:  Numeric column to find the minimum of
    """
    numbers = get_numeric_column(load_records_as_dataframe(state, module), field)
    return {
        "module":       module,
        "field":        field,
        "minimum":      float(numbers.min()) if not numbers.empty else None,
        "records_used": int(numbers.count()),
    }


# =============================================================================
# TOOL 5: get_maximum
# =============================================================================
@tool
def get_maximum(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()]
) -> dict:
    """
    Find the maximum value in a numeric field across all records in a module.

    Args:
        module: Data module name
        field:  Numeric column to find the maximum of
    """
    numbers = get_numeric_column(load_records_as_dataframe(state, module), field)
    return {
        "module":       module,
        "field":        field,
        "maximum":      float(numbers.max()) if not numbers.empty else None,
        "records_used": int(numbers.count()),
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
    Returns count, average, minimum, and maximum elapsed minutes.

    Args:
        module:      Data module name
        start_field: Column name containing the start datetime
        end_field:   Column name containing the end datetime
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"module": module, "total_records": 0, "stats": {}}

    df = df.copy()
    df["_start_dt"]     = pd.to_datetime(df.get(start_field), dayfirst=True, errors="coerce")
    df["_end_dt"]       = pd.to_datetime(df.get(end_field),   dayfirst=True, errors="coerce")
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
    secondary_field: str = "",
    top_n: int = 10,
) -> dict:
    """
    Group records by a field and count how many records fall in each group.
    Results are ranked from highest count to lowest.
    Optionally pre-filter rows before grouping using filter_field + filter_value.
    Pass filter_value="" to filter for rows where filter_field is blank or null.
    Leave filter_field empty to group all records.

    Args:
        module:          Data module name
        group_field:     Column to group by
        filter_field:    Column to pre-filter on before grouping (optional)
        filter_value:    Value to match in filter_field; "" matches blank/null
        secondary_field: Second column for nested grouping (optional)
        top_n:           Max number of groups to return (default 10)
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"module": module, "group_field": group_field, "total_records": 0, "ranked": []}

    # Apply optional pre-filter before grouping
    if filter_field and filter_field in df.columns:
        col = df[filter_field].fillna("").astype(str).str.strip()
        if filter_value == "":
            df = df[col == ""]
        else:
            df = df[col.str.lower() == filter_value.lower()]

    if group_field not in df.columns:
        return {
            "module":      module,
            "group_field": group_field,
            "error":       f"Column '{group_field}' does not exist in '{module}' data.",
            "ranked":      [],
        }

    use_secondary = secondary_field and secondary_field in df.columns
    group_columns = [group_field] + ([secondary_field] if use_secondary else [])

    grouped = (
        df.groupby(group_columns, dropna=False)
          .size()
          .reset_index(name="count")
          .sort_values("count", ascending=False)
          .head(top_n)
    )

    # Replace NaN with None so the output is always valid JSON
    # (NaN appears when a group field has null values — not valid in JSON)
    import math
    ranked_raw = grouped.to_dict(orient="records")
    ranked_clean = [
        {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.items()}
        for row in ranked_raw
    ]

    return {
        "module":        module,
        "group_field":   group_field,
        "total_records": len(df),
        "unique_groups": len(grouped),
        "ranked":        ranked_clean,
    }


# =============================================================================
# TOOL 8: get_unique_values
# =============================================================================
@tool
def get_unique_values(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
) -> dict:
    """
    Return all distinct values in a field across all records in a module.

    Args:
        module: Data module name
        field:  Column to extract unique values from
    """
    df = load_records_as_dataframe(state, module)
    if df.empty or field not in df.columns:
        return {"module": module, "field": field, "unique_values": [], "count": 0}

    unique_set    = set(df[field].dropna().astype(str).tolist())
    unique_sorted = sorted(unique_set)

    return {
        "module":        module,
        "field":         field,
        "unique_values": unique_sorted,
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

    Args:
        module_a:   First data module name
        module_b:   Second data module name
        join_field: Column name present in both modules to join on
    """
    df_a = load_records_as_dataframe(state, module_a)
    df_b = load_records_as_dataframe(state, module_b)

    if df_a.empty or df_b.empty:
        return {
            "module_a":     module_a,
            "module_b":     module_b,
            "join_field":   join_field,
            "error":        "One or both modules returned no records.",
            "matched_count": 0,
        }

    if join_field not in df_a.columns or join_field not in df_b.columns:
        missing = [m for m, df in [(module_a, df_a), (module_b, df_b)] if join_field not in df.columns]
        return {
            "module_a":     module_a,
            "module_b":     module_b,
            "join_field":   join_field,
            "error":        f"Column '{join_field}' not found in: {missing}",
            "matched_count": 0,
        }

    keys_a = set(df_a[join_field].dropna().astype(str))
    keys_b = set(df_b[join_field].dropna().astype(str))

    matched_keys = keys_a & keys_b     # set intersection — present in both modules
    only_in_a    = keys_a - keys_b     # only in module_a
    only_in_b    = keys_b - keys_a     # only in module_b

    df_a_str = df_a.copy()
    df_b_str = df_b.copy()
    df_a_str[join_field] = df_a_str[join_field].astype(str)
    df_b_str[join_field] = df_b_str[join_field].astype(str)

    joined = pd.merge(df_a_str, df_b_str, on=join_field, how="inner")

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
    a: float,
    b: float = 0,
) -> dict:
    """
    Perform arithmetic on two numbers.
    Operations: ADD | SUB | MUL | DIV | MOD | POWER | SQRT | ABS
    DIV: a / b  — SQRT and ABS only use a.

    Args:
        operation: ADD | SUB | MUL | DIV | MOD | POWER | SQRT | ABS
        a:         First number
        b:         Second number (unused for SQRT and ABS)
    """
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
# ALL TOOLS — imported by agent.py
# The LLM reads each tool's docstring to decide which one to call.
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
]
