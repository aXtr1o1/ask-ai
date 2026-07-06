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
) -> dict:
    """
    Count how many records exist in a module.
    The data is already filtered — this counts all records in the filtered dataset.

    Use this when the question asks: how many, total count, number of records.

    Args:
        module: Data module to count from (bdm | ppm | fa | assets | sb)
    """
    df = load_records_as_dataframe(state, module)
    return {
        "module": module,
        "count":  len(df),
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
    Add up all numeric values in a field across all records in a module.
    The data is already filtered — this sums all values in the filtered dataset.

    Use this when the question asks: total, sum, accumulated value of a field.

    Args:
        module: Data module (bdm | ppm | fa | assets | sb)
        field:  Numeric column name to sum
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
    Compute the average (mean) of a numeric field across all records in a module.
    The data is already filtered — this averages all values in the filtered dataset.

    Use this when the question asks: average, mean, typical value of a field.

    Args:
        module: Data module (bdm | ppm | fa | assets | sb)
        field:  Numeric column name to average
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
    Find the smallest (minimum) value in a numeric field across all records.
    The data is already filtered.

    Use this when the question asks: minimum, lowest, shortest, least.

    Args:
        module: Data module (bdm | ppm | fa | assets | sb)
        field:  Numeric column name to find the minimum of
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
    Find the largest (maximum) value in a numeric field across all records.
    The data is already filtered.

    Use this when the question asks: maximum, highest, longest, most.

    Args:
        module: Data module (bdm | ppm | fa | assets | sb)
        field:  Numeric column name to find the maximum of
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
#
# Role in FM analytics:
#   Measures how much time passed between two date/time fields per record.
#   Used for SLA tracking, response speed, overdue duration, maintenance windows.
#   Returns average, minimum, maximum elapsed minutes across all records.
# =============================================================================
@tool
def calculate_time_between(
    module: str,
    start_field: str,
    end_field: str,
    state: Annotated[dict, InjectedState()],
) -> dict:
    """
    Calculate elapsed time in minutes between two datetime fields, per record.
    Returns summary statistics: count, average, minimum, maximum elapsed minutes.
    The data is already filtered.

    Use this when the question asks: how long did it take, response time,
    SLA breach, duration between two events, overdue period.

    Args:
        module:      Data module (bdm | ppm | fa | sb)
        start_field: Column name with the start datetime
        end_field:   Column name with the end datetime
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
    secondary_field: str = "",
    top_n: int = 10,
) -> dict:
    """
    Group all records by a field and count how many records fall in each group.
    Results are ranked from highest count to lowest.
    The data is already filtered.

    Use this when the question asks: breakdown by, distribution across,
    which category has the most, count per group.

    Args:
        module:          Data module (bdm | ppm | fa | assets | sb)
        group_field:     Column name to group by
        secondary_field: Optional second column name for nested grouping
        top_n:           Number of top groups to return (default: 10)
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"module": module, "group_field": group_field, "total_records": 0, "ranked": []}

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
    Return all distinct (unique) values that exist in a field across all records.
    Uses a set internally to remove duplicates.
    The data is already filtered.

    Use this when the question asks: what are all the possible values,
    list all categories, which statuses exist, distinct items in a field.

    Args:
        module: Data module (bdm | ppm | fa | assets | sb)
        field:  Column name to extract unique values from
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
#
# Role in FM analytics:
#   Cross-module analysis requires matching records from two different modules
#   on a shared key field (inner join). Returns matched pairs and counts.
#   Unmatched records from each module are also counted for completeness.
# =============================================================================
@tool
def join_records(
    module_a: str,
    module_b: str,
    join_field: str,
    state: Annotated[dict, InjectedState()],
) -> dict:
    """
    Join records from two modules on a shared key field (inner join).
    Returns the count of matched records and the unmatched counts per module.
    Both datasets are already filtered before joining.

    Use this when the question requires cross-module analysis:
    matching work orders across bdm and ppm, linking assets to complaints,
    finding records that exist in one module but not another.

    Args:
        module_a:   First data module (bdm | ppm | fa | assets | sb)
        module_b:   Second data module (bdm | ppm | fa | assets | sb)
        join_field: Column name that exists in both modules to join on
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
    Perform an arithmetic operation on two numbers.
    Use this to calculate rates, percentages, ratios, or combine results from other tools.

    Operations:
      ADD   → a + b
      SUB   → a - b
      MUL   → a * b
      DIV   → a / b  (use for rates and percentages)
      MOD   → a % b  (remainder after division)
      POWER → a ^ b
      SQRT  → square root of a (b not used)
      ABS   → absolute value of a (b not used)

    Args:
        operation: ADD | SUB | MUL | DIV | MOD | POWER | SQRT | ABS
        a:         First number
        b:         Second number (not required for SQRT and ABS)
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
