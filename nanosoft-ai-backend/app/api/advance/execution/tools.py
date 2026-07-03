"""
Execution — FM Analytics Tools (pandas-powered)

Each tool has ONE clear purpose. Tool signatures are unchanged — the agent
calls the same functions. Internally, records are loaded into a pandas
DataFrame which automatically handles:
  - null / None values
  - numbers stored as strings ("0.00")
  - date strings ("19-06-2026 11:21:00")
  - mixed text + numeric columns

Data never reaches the LLM — all tools read from state via InjectedState.
"""
import math
from typing import Annotated

import pandas as pd
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState


# ── Core helper: records → clean DataFrame ─────────────────────────────────
def _to_df(state: dict, module: str) -> pd.DataFrame:
    """
    Load filtered records for a module into a pandas DataFrame.
    Numeric columns are coerced automatically; everything else stays as-is.
    """
    records = state.get("filtered_records", {}).get(module, [])
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    # Coerce each column to numeric where possible (leaves text columns untouched)
    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        # Only replace if at least some values successfully converted
        if converted.notna().sum() > 0:
            df[col] = converted
    return df


def _numeric_series(df: pd.DataFrame, field: str) -> pd.Series:
    """Return a numeric Series for field, coercing and dropping NaN."""
    if field not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[field], errors="coerce").dropna()


def _filter_df(df: pd.DataFrame, condition_field: str, condition_value: str) -> pd.DataFrame:
    """Case-insensitive equality filter on a DataFrame."""
    if not condition_field or not condition_value or condition_field not in df.columns:
        return df
    return df[df[condition_field].astype(str).str.lower() == condition_value.lower()]


def _record_id(row: pd.Series) -> str:
    for key in ("ComplaintNo", "WorkOrder", "AssetTagNo", "RMComplaintNo", "SBRequestNo"):
        if key in row.index and pd.notna(row[key]):
            return str(row[key])
    return "?"


# ══════════════════════════════════════════════════════════════════════════════
# 1. COUNT
# ══════════════════════════════════════════════════════════════════════════════
@tool
def count_records(
    module: str,
    state: Annotated[dict, InjectedState()],
    condition_field: str = "",
    condition_value: str = "",
) -> dict:
    """
    Count how many records exist in a module, optionally filtered by a condition.

    Args:
        module:          bdm | assets | ppm | fa | sb
        condition_field: Column to filter on before counting (e.g. WoStatus)
        condition_value: Value to match (e.g. Open)
    """
    df = _to_df(state, module)
    df = _filter_df(df, condition_field, condition_value)
    return {
        "module":    module,
        "count":     len(df),
        "condition": f"{condition_field}={condition_value}" if condition_field else "none",
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. SUM
# ══════════════════════════════════════════════════════════════════════════════
@tool
def sum_field(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
    condition_field: str = "",
    condition_value: str = "",
) -> dict:
    """
    Sum all numeric values in a field across records.

    Args:
        module:          bdm | assets | ppm | fa | sb
        field:           Numeric column to sum (e.g. SLADuration, PPMPendingPeriod)
        condition_field: Optional filter column
        condition_value: Optional filter value
    """
    df = _filter_df(_to_df(state, module), condition_field, condition_value)
    s = _numeric_series(df, field)
    return {
        "module":       module,
        "field":        field,
        "sum":          round(float(s.sum()), 4),
        "values_found": int(s.count()),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. AVERAGE (MEAN)
# ══════════════════════════════════════════════════════════════════════════════
@tool
def average_field(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
    condition_field: str = "",
    condition_value: str = "",
) -> dict:
    """
    Compute the average (mean) of a numeric field across records.

    Args:
        module:          bdm | assets | ppm | fa | sb
        field:           Numeric column to average (e.g. RMMaintenanceHrs, SLADuration)
        condition_field: Optional filter column
        condition_value: Optional filter value
    """
    df = _filter_df(_to_df(state, module), condition_field, condition_value)
    s = _numeric_series(df, field)
    if s.empty:
        return {"module": module, "field": field, "average": None, "values_found": 0}
    return {
        "module":       module,
        "field":        field,
        "average":      round(float(s.mean()), 4),
        "values_found": int(s.count()),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. MINIMUM
# ══════════════════════════════════════════════════════════════════════════════
@tool
def min_field(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
) -> dict:
    """
    Find the minimum value of a numeric field across records.

    Args:
        module: bdm | assets | ppm | fa | sb
        field:  Numeric column (e.g. PPMPendingPeriod, SLADuration)
    """
    s = _numeric_series(_to_df(state, module), field)
    return {
        "module":       module,
        "field":        field,
        "min":          float(s.min()) if not s.empty else None,
        "values_found": int(s.count()),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. MAXIMUM
# ══════════════════════════════════════════════════════════════════════════════
@tool
def max_field(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
) -> dict:
    """
    Find the maximum value of a numeric field across records.

    Args:
        module: bdm | assets | ppm | fa | sb
        field:  Numeric column (e.g. PPMPendingPeriod, SLADuration)
    """
    s = _numeric_series(_to_df(state, module), field)
    return {
        "module":       module,
        "field":        field,
        "max":          float(s.max()) if not s.empty else None,
        "values_found": int(s.count()),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6. STANDARD DEVIATION
# ══════════════════════════════════════════════════════════════════════════════
@tool
def stddev_field(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
) -> dict:
    """
    Compute the standard deviation of a numeric field across records.

    Args:
        module: bdm | assets | ppm | fa | sb
        field:  Numeric column
    """
    s = _numeric_series(_to_df(state, module), field)
    return {
        "module":       module,
        "field":        field,
        "stddev":       round(float(s.std()), 4) if len(s) > 1 else 0.0,
        "values_found": int(s.count()),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 7. VARIANCE
# ══════════════════════════════════════════════════════════════════════════════
@tool
def variance_field(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
) -> dict:
    """
    Compute the variance of a numeric field across records.

    Args:
        module: bdm | assets | ppm | fa | sb
        field:  Numeric column
    """
    s = _numeric_series(_to_df(state, module), field)
    return {
        "module":       module,
        "field":        field,
        "variance":     round(float(s.var()), 4) if len(s) > 1 else 0.0,
        "values_found": int(s.count()),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 8. ELAPSED TIME  (datetime subtraction → minutes)
# Key FM use: ComplainedDateTime → AnalysisStartTime  (response speed)
# ══════════════════════════════════════════════════════════════════════════════
@tool
def elapsed_minutes(
    module: str,
    start_field: str,
    end_field: str,
    state: Annotated[dict, InjectedState()],
    condition_field: str = "",
    condition_value: str = "",
) -> dict:
    """
    Compute elapsed time in minutes between two datetime fields per record,
    then return count, average, min, max, stddev, variance of those times.

    Args:
        module:          bdm | ppm | fa | sb
        start_field:     Column with start datetime  (e.g. ComplainedDateTime)
        end_field:       Column with end datetime    (e.g. AnalysisStartTime)
        condition_field: Optional pre-filter column
        condition_value: Optional pre-filter value
    """
    df = _filter_df(_to_df(state, module), condition_field, condition_value)
    if df.empty:
        return {"module": module, "total_records": 0, "stats": {}, "per_record": []}

    # Parse both datetime columns (dayfirst=True for DD-MM-YYYY format)
    df = df.copy()
    df["_start"] = pd.to_datetime(df.get(start_field), dayfirst=True, errors="coerce")
    df["_end"]   = pd.to_datetime(df.get(end_field),   dayfirst=True, errors="coerce")
    df["_mins"]  = (df["_end"] - df["_start"]).dt.total_seconds() / 60

    computed   = df.dropna(subset=["_mins"])
    null_count = len(df) - len(computed)

    per_record = []
    for _, row in df.iterrows():
        entry = {"id": _record_id(row)}
        if pd.notna(row["_mins"]):
            entry["elapsed_minutes"] = round(float(row["_mins"]), 2)
        else:
            entry["elapsed_minutes"] = None
            entry["note"] = f"{end_field} missing or unparseable"
        per_record.append(entry)

    mins = computed["_mins"]
    stats = {}
    if not mins.empty:
        stats = {
            "count":    int(mins.count()),
            "average":  round(float(mins.mean()), 2),
            "min":      round(float(mins.min()),  2),
            "max":      round(float(mins.max()),  2),
            "stddev":   round(float(mins.std()),  2) if len(mins) > 1 else 0.0,
            "variance": round(float(mins.var()),  2) if len(mins) > 1 else 0.0,
        }

    return {
        "module":             module,
        "start_field":        start_field,
        "end_field":          end_field,
        "total_records":      len(df),
        "computed_count":     int(mins.count()) if not mins.empty else 0,
        "null_count":         null_count,
        "null_rate_percent":  round(null_count / len(df) * 100, 1),
        "stats":              stats,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 9. GROUP AND COUNT  (group by field → count + rank)
# Key FM use: group by DivisionName + ComplaintNatureName → repeated breakdowns
# ══════════════════════════════════════════════════════════════════════════════
@tool
def group_and_count(
    module: str,
    group_field: str,
    state: Annotated[dict, InjectedState()],
    secondary_field: str = "",
    top_n: int = 10,
) -> dict:
    """
    Group records by a field (and optionally a secondary field), count per group,
    rank descending by count.

    Args:
        module:          bdm | assets | ppm | fa | sb
        group_field:     Primary column to group by   (e.g. DivisionName)
        secondary_field: Optional second column       (e.g. ComplaintNatureName)
        top_n:           How many top groups to return
    """
    df = _to_df(state, module)
    if df.empty or group_field not in df.columns:
        return {"module": module, "group_field": group_field, "total_records": 0, "ranked": []}

    group_cols = [group_field] + ([secondary_field] if secondary_field and secondary_field in df.columns else [])
    grouped    = df.groupby(group_cols, dropna=False).size().reset_index(name="count")
    grouped    = grouped.sort_values("count", ascending=False).head(top_n)

    ranked = grouped.to_dict(orient="records")

    return {
        "module":         module,
        "group_field":    group_field,
        "secondary_field":secondary_field or None,
        "total_records":  len(df),
        "unique_groups":  len(grouped),
        "ranked":         ranked,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 10. ARITHMETIC  (add / sub / mul / div / mod / power / sqrt / abs)
# Use for: rate calculations, weighted scores, formula sub-steps
# ══════════════════════════════════════════════════════════════════════════════
@tool
def arithmetic(
    operation: str,
    a: float,
    b: float = 0,
) -> dict:
    """
    Execute an arithmetic operation on two numbers.

    Args:
        operation: ADD | SUB | MUL | DIV | MOD | POWER | SQRT | ABS
        a:         First number
        b:         Second number (not needed for SQRT / ABS)
    """
    op = operation.upper()
    try:
        if op == "ADD":    r = a + b
        elif op == "SUB":  r = a - b
        elif op == "MUL":  r = a * b
        elif op == "DIV":  r = (a / b) if b != 0 else None
        elif op == "MOD":  r = (a % b) if b != 0 else None
        elif op == "POWER":r = a ** b
        elif op == "SQRT": r = math.sqrt(a) if a >= 0 else None
        elif op == "ABS":  r = abs(a)
        else:              return {"error": f"Unknown operation: {op}"}
    except Exception as exc:
        return {"error": str(exc)}
    return {
        "operation": op,
        "a": a, "b": b,
        "result": round(r, 6) if isinstance(r, float) else r,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 11. LOGARITHM / EXPONENTIAL
# Use for: growth-rate analysis, log-scale computations
# ══════════════════════════════════════════════════════════════════════════════
@tool
def logarithm(
    operation: str,
    value: float,
    base: float = 10,
) -> dict:
    """
    Execute a logarithmic or exponential operation.

    Args:
        operation: LOG | LN | LOG10 | EXP | POWER
        value:     Input number
        base:      Log base (default 10) or power exponent
    """
    op = operation.upper()
    try:
        if op == "LOG":    r = math.log(value, base)
        elif op == "LN":   r = math.log(value)
        elif op == "LOG10":r = math.log10(value)
        elif op == "EXP":  r = math.exp(value)
        elif op == "POWER":r = value ** base
        else:              return {"error": f"Unknown operation: {op}"}
    except Exception as exc:
        return {"error": str(exc)}
    return {"operation": op, "value": value, "base": base, "result": round(r, 8)}


# ── Exported tool list ────────────────────────────────────────────────────
ALL_TOOLS = [
    count_records,
    sum_field,
    average_field,
    min_field,
    max_field,
    stddev_field,
    variance_field,
    elapsed_minutes,
    group_and_count,
    arithmetic,
    logarithm,
]
