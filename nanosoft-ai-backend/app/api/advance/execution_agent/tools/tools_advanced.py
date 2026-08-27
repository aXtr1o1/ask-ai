"""
Intelligence FM Analytics Tools (Tools 10–19)

  10. calculate_age_from_now    → days from a date field to today (WO aging, asset age)
  11. group_by_time_period      → group records by month/week/quarter/year from a date field (trends)
  12. calculate_mtbf            → mean time between failures per asset/group
  13. flag_by_threshold         → mark/count records where a field exceeds a threshold
  14. calculate_rate_of_change  → % change between two numeric values (period-over-period)
  15. calculate_percentile      → P50/P90/P95/P99 of a numeric field (outlier detection)
  16. forecast_linear           → linear regression forecast on grouped time-series data
  17. compare_date_fields       → compare two date columns per record (SLA breach, overdue)
  18. merge_and_score           → combine multiple prior-step group results into a ranked score
  19. add_duration_to_date      → add a duration field to a date field (asset remaining life)
"""
from typing import Annotated, Any

import numpy as np
import pandas as pd
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from app.api.advance.execution_agent.tools.tool_helpers import (
    load_records_as_dataframe,
    resolve_column,
    _apply_conditions,
    _clean_records,
    _nan_to_none,
    _safe_apply,
    _err,
)



# Single configurable cap for all detail-record lists returned by tools


# =============================================================================
# TOOL 10: calculate_age_from_now
# =============================================================================
@tool
def calculate_age_from_now(
    module: str,
    date_field: str,
    state: Annotated[dict, InjectedState()],
    group_fields: list | None = None,
    filters: list | None = None,
) -> dict:
    """
    Calculate the age in days from a date field to today for each record.
    Use for work order aging, asset age, overdue detection, backlog analysis.

    Returns overall stats (avg/min/max age in days) and optionally a per-group breakdown.

    Args:
        module:       Data module name
        date_field:   Column containing the reference date (creation date, reported date, etc.)
        group_fields: Optional list of columns to group age stats by (e.g. ["BuildingName"])
        filters:      Optional list of {"field": str, "value": str} dicts for AND pre-filtering
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"_result_type": "age_distribution",
                "module": module, "date_field": date_field, "filters": filters or [],
                "group_fields": group_fields or [], "total_records": 0,
                "avg_age_days": None, "max_age_days": None, "min_age_days": None,
                "calculated": 0, "groups": []}

    if filters:
        try:
            df = _apply_conditions(df, filters)
        except ValueError as e:
            return {"_result_type": "error", "error": str(e)}

    actual_date = resolve_column(df, date_field)
    if actual_date is None:
        return _err(f"Column '{date_field}' not found. Available: {list(df.columns)}")

    df = df.copy()
    today = pd.Timestamp.now(tz=None).normalize()
    df["_date_parsed"] = pd.to_datetime(df[actual_date], dayfirst=True, errors="coerce")
    df["_age_days"]    = (today - df["_date_parsed"]).dt.days

    valid = df.dropna(subset=["_age_days"])
    ages  = valid["_age_days"].astype(int)

    result = {
        "_result_type":  "age_distribution",
        "module":        module,
        "date_field":    date_field,
        "filters":       filters or [],
        "total_records": len(df),
        "calculated":    len(valid),
        "avg_age_days":  round(float(ages.mean()), 2) if not ages.empty else None,
        "max_age_days":  int(ages.max())              if not ages.empty else None,
        "min_age_days":  int(ages.min())              if not ages.empty else None,
    }

    result["group_fields"] = group_fields or []
    if group_fields:
        resolved_groups = [resolve_column(valid, f) for f in group_fields]
        actual_groups   = [r for r in resolved_groups if r is not None]
        if actual_groups:
            grouped = (
                valid.groupby(actual_groups, dropna=False)["_age_days"]
                     .agg(["mean", "max", "count"])
                     .round(2)
                     .reset_index()
                     .rename(columns={"mean": "avg_age_days", "max": "max_age_days",
                                      "count": "record_count"})
                     .sort_values("avg_age_days", ascending=False)
            )
            rename_map = {actual: req
                          for actual, req in zip(actual_groups, group_fields)
                          if actual != req}
            if rename_map:
                grouped = grouped.rename(columns=rename_map)
            result["groups"] = _clean_records(grouped.to_dict(orient="records"))
        else:
            result["groups"] = []
    else:
        result["groups"] = []

    return result


# =============================================================================
# TOOL 11: group_by_time_period
# =============================================================================
@tool
def group_by_time_period(
    module: str,
    date_field: str,
    state: Annotated[dict, InjectedState()],
    period: str = "month",
    agg_field: str = "",
    operation: str = "COUNT",
    filters: list | None = None,
    group_fields: list | None = None,
) -> dict:
    """
    Group records by a time period (month / week / quarter / year) from a date column.
    Use for trend analysis, month-over-month changes, workload distribution over time.

    When agg_field is empty, counts records per period (how many WOs per month).
    When agg_field is provided with operation SUM/AVG/MIN/MAX, aggregates that numeric field.

    Args:
        module:     Data module name
        date_field: Column containing the date to group by
        period:     "month" | "week" | "quarter" | "year"  (default: "month")
        agg_field:  Optional numeric field to aggregate per period (empty = COUNT)
        operation:  COUNT | SUM | AVG | MIN | MAX  (default: COUNT)
        filters:    Optional list of {"field": str, "value": str} dicts for AND pre-filtering
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"_result_type": "time_series",
                "module": module, "date_field": date_field, "period": period,
                "agg_field": agg_field, "filters": filters or [],
                "total_records": 0, "period_count": 0,
                "value_key": "count" if not agg_field else "value",
                "operation": operation.upper(), "periods": []}

    if filters:
        try:
            df = _apply_conditions(df, filters)
        except ValueError as e:
            return {"_result_type": "error", "error": str(e)}

    actual_date = resolve_column(df, date_field)
    if actual_date is None:
        return _err(f"Column '{date_field}' not found. Available: {list(df.columns)}")

    df = df.copy()
    df["_dt"] = pd.to_datetime(df[actual_date], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["_dt"])

    period_lower = period.lower()
    label_fmt = {"month": "%Y-%m", "week": "%Y-W%W", "quarter": None, "year": "%Y"}

    if period_lower not in label_fmt:
        return _err(f"Invalid period '{period}'. Valid: month | week | quarter | year")

    if period_lower == "quarter":
        df["_period"] = df["_dt"].dt.to_period("Q").astype(str)
    else:
        df["_period"] = df["_dt"].dt.strftime(label_fmt[period_lower])

    op = operation.upper()
    agg_fn_map = {"COUNT": "size", "SUM": "sum", "AVG": "mean", "MIN": "min", "MAX": "max"}
    if op not in agg_fn_map:
        return _err(f"Invalid operation '{op}'. Valid: COUNT | SUM | AVG | MIN | MAX")

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
            return _err(f"agg_field '{agg_field}' not found. Available: {list(df.columns)}")
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
        "_result_type":  "time_series",
        "module":        module,
        "date_field":    date_field,
        "period":        period_lower,
        "operation":     op,
        "agg_field":     agg_field,
        "filters":       filters or [],
        "total_records": len(df),
        "period_count":  len(periods_list),
        "value_key":     value_key,
        "periods":       periods_list,
    }


# =============================================================================
# TOOL 12: calculate_mtbf
# =============================================================================
@tool
def calculate_mtbf(
    module: str,
    asset_field: str,
    failure_date_field: str,
    state: Annotated[dict, InjectedState()],
    filters: list | None = None,
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
        filters:            Optional list of {"field": str, "value": str} dicts for AND pre-filtering
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"_result_type": "mtbf_data",
                "module": module, "asset_field": asset_field,
                "failure_date_field": failure_date_field, "filters": filters or [],
                "total_records": 0, "assets_analyzed": 0,
                "overall_avg_mtbf_days": None, "mtbf_by_asset": []}

    if filters:
        try:
            df = _apply_conditions(df, filters)
        except ValueError as e:
            return {"_result_type": "error", "error": str(e)}

    if df.empty:
        return {"_result_type": "mtbf_data",
                "module": module, "asset_field": asset_field,
                "failure_date_field": failure_date_field, "filters": filters or [],
                "total_records": 0, "assets_analyzed": 0,
                "overall_avg_mtbf_days": None, "mtbf_by_asset": []}

    actual_asset = resolve_column(df, asset_field)
    actual_date  = resolve_column(df, failure_date_field)

    if actual_asset is None:
        return _err(f"asset_field '{asset_field}' not found. Available: {list(df.columns)}")
    if actual_date is None:
        return _err(f"failure_date_field '{failure_date_field}' not found. "
                     f"Available: {list(df.columns)}")

    df = df.copy()
    df["_dt"] = pd.to_datetime(df[actual_date], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["_dt"])
    df = df.sort_values([actual_asset, "_dt"])

    mtbf_rows = []
    for asset_id, group in df.groupby(actual_asset, sort=False):
        dates = group["_dt"].reset_index(drop=True)
        if len(dates) < 2:
            mtbf_rows.append({
                asset_field:     str(asset_id),
                "failure_count": int(len(dates)),
                "mtbf_days":     None,
            })
            continue
        gaps = dates.diff().dt.days.dropna()
        mtbf_rows.append({
            asset_field:     str(asset_id),
            "failure_count": int(len(dates)),
            "mtbf_days":     round(float(gaps.mean()), 2),
        })

    if not mtbf_rows:
        return {"_result_type": "mtbf_data",
                "module": module, "asset_field": asset_field,
                "failure_date_field": failure_date_field, "filters": filters or [],
                "total_records": len(df), "assets_analyzed": 0,
                "overall_avg_mtbf_days": None, "mtbf_by_asset": []}

    mtbf_df    = pd.DataFrame(mtbf_rows).sort_values("mtbf_days", ascending=True)
    valid_mtbf = [r["mtbf_days"] for r in mtbf_rows if r["mtbf_days"] is not None]
    overall    = round(float(np.mean(valid_mtbf)), 2) if valid_mtbf else None

    return {
        "_result_type":          "mtbf_data",
        "module":                module,
        "asset_field":           asset_field,
        "failure_date_field":    failure_date_field,
        "filters":               filters or [],
        "total_records":         len(df),
        "assets_analyzed":       len(mtbf_rows),
        "overall_avg_mtbf_days": overall,
        "mtbf_by_asset":         _clean_records(mtbf_df.to_dict(orient="records")),
    }


# =============================================================================
# TOOL 13: flag_by_threshold
# =============================================================================
@tool
def flag_by_threshold(
    module: str = "",
    field: str = "",
    threshold = 0,
    state: Annotated[dict, InjectedState()] = None,
    operator: str = "gt",
    group_fields: list | None = None,
    label_field: str = "",
    filters: list | None = None,
    data: list | None = None,
    flagged_records: list | None = None,
    records: list | None = None,
    input_data: list | None = None,
    dataset: list | None = None,
) -> dict:
    """
    Flag records where a numeric field satisfies a threshold condition.
    Use for risk flagging, SLA breach detection, overdue identification.
    Also supports categorical string matching with operator='eq'.

    operator options: gt (>), lt (<), gte (>=), lte (<=), eq (==)

    Returns flagged record count, total records, ratio, and optionally
    flagged record labels and a per-group breakdown.

    Args:
        module:       Data module name
        field:        Numeric (or text) field to evaluate
        threshold:    Threshold value — numeric or string (string only works with eq)
        operator:     gt | lt | gte | lte | eq  (default: "gt")
        group_fields: Optional list of columns to count flagged records per group
        label_field:  Optional column to include in flagged records list (e.g. WO number)
        filters:      Optional list of {"field": str, "value": str} dicts for AND pre-filtering
        data:         Optional list of record dicts from a prior step (e.g. $step_N.groups)
    """
    if data is None:
        data = flagged_records or records or input_data or dataset

    # ── Handle LLM passing a resolved list as `module` instead of `data` ───
    if isinstance(module, list):
        data = module
        module = ""

    if data is not None and isinstance(data, list):
        if not data:
            return {"_result_type": "flagged_set",
                    "module": module, "field": field, "threshold": threshold,
                    "operator": operator, "filters": filters or [], "group_fields": group_fields or [],
                    "flagged_count": 0, "total_records": 0,
                    # 0/0 is undefined, not "0% flagged" — see matching note below.
                    "flag_ratio": None, "flagged_records": [], "groups": []}
        df = pd.DataFrame(data)
    else:
        df = load_records_as_dataframe(state, module)

    if df.empty:
        return {"_result_type": "flagged_set",
                "module": module, "field": field, "threshold": threshold,
                "operator": operator, "filters": filters or [], "group_fields": group_fields or [],
                "flagged_count": 0, "total_records": 0,
                # 0/0 is undefined, not "0% flagged" — a real ratio only exists once
                # there are records to evaluate the threshold against.
                "flag_ratio": None, "flagged_records": [], "groups": []}

    if filters:
        try:
            df = _apply_conditions(df, filters)
        except ValueError as e:
            return {"_result_type": "error", "error": str(e)}

    actual_field = resolve_column(df, field)
    if actual_field is None:
        # Fallback: if user/LLM asks to flag by 'count' on a raw module with group_fields,
        # group the module first to produce group record counts, then evaluate threshold.
        if field.lower() in ("count", "value", "total", "records", "") and group_fields:
            resolved_groups = [resolve_column(df, g) for g in group_fields]
            actual_groups = [g for g in resolved_groups if g is not None]
            if actual_groups:
                df = df.groupby(actual_groups, dropna=False).size().reset_index(name="count")
                actual_field = "count"
        if actual_field is None:
            return _err(f"Column '{field}' not found. Available: {list(df.columns)}")

    df = df.copy()

    op = operator.lower()
    try:
        thr_float = float(threshold)
        use_string_compare = False
    except (TypeError, ValueError):
        thr_float = None
        use_string_compare = True

    if use_string_compare:
        if op != "eq":
            return _err(f"operator '{op}' requires a numeric threshold. "
                        f"String threshold '{threshold}' only works with operator 'eq'.")
        str_col = df[actual_field].fillna("").astype(str).str.strip().str.lower()
        mask    = str_col == str(threshold).strip().lower()
        numeric_col = pd.Series([float("nan")] * len(df), index=df.index)
    else:
        numeric_col = pd.to_numeric(df[actual_field], errors="coerce")

    df["_numeric"] = numeric_col

    op_map = {
        "gt":  lambda s, t: s > t,
        "lt":  lambda s, t: s < t,
        "gte": lambda s, t: s >= t,
        "lte": lambda s, t: s <= t,
        "eq":  lambda s, t: s == t,
    }
    if op not in op_map:
        return _err(f"Unknown operator '{op}'. Valid: gt | lt | gte | lte | eq")

    if use_string_compare:
        thr = threshold
    else:
        thr  = thr_float
        mask = op_map[op](df["_numeric"], thr)

    flagged = df[mask]
    total   = len(df)
    n_flag  = len(flagged)

    # Flagged records list — full set, no cap (downstream steps need all records)
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
        flagged_records = _clean_records(flagged.to_dict(orient="records"))

    # Per-group breakdown
    groups = []
    if group_fields:
        resolved_groups = [resolve_column(df, f) for f in group_fields]
        actual_groups   = [r for r in resolved_groups if r is not None]
        if actual_groups:
            group_stats = []
            for grp_keys, grp_df in df.groupby(actual_groups, sort=False):
                if not isinstance(grp_keys, tuple):
                    grp_keys = (grp_keys,)
                if use_string_compare:
                    str_col_grp = grp_df[actual_field].fillna("").astype(str).str.strip().str.lower()
                    grp_mask    = str_col_grp == str(threshold).strip().lower()
                else:
                    grp_mask = op_map[op](grp_df["_numeric"], thr)
                grp_flag  = int(grp_mask.sum())
                grp_total = len(grp_df)
                row = {}
                for i, gf in enumerate(group_fields[:len(actual_groups)]):
                    row[gf] = _nan_to_none(grp_keys[i])
                row["flagged_count"] = grp_flag
                row["total"]         = grp_total
                row["flag_ratio"]    = round(grp_flag / grp_total, 4) if grp_total else 0.0
                group_stats.append(row)
            group_stats.sort(key=lambda r: r["flagged_count"], reverse=True)
            groups = group_stats

    return {
        "_result_type":    "flagged_set",
        "module":          module,
        "field":           field,
        "threshold":       thr,
        "operator":        op,
        "filters":         filters or [],
        "total_records":   total,
        "flagged_count":   n_flag,
        "flag_ratio":      round(n_flag / total, 4) if total else 0.0,
        "flagged_records": flagged_records,
        "group_fields":    group_fields or [],
        "groups":          groups,
    }


# =============================================================================
# TOOL 14: calculate_rate_of_change
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
            "_result_type": "error",
            "a": a, "b": b,
            "pct_change": None,
            "direction":  "unknown",
            "error":      "One or both input values could not be converted to a number.",
        }

    if fb == 0:
        return {
            "_result_type": "error",
            "a": fa, "b": fb,
            "pct_change": None,
            "direction":  "unknown",
            "error":      "Baseline value (b) is zero — rate of change is undefined.",
        }

    pct = round(((fa - fb) / fb) * 100, 4)
    direction = "up" if pct > 0 else ("down" if pct < 0 else "flat")

    return {
        "_result_type": "rate_of_change",
        "a":          fa,
        "b":          fb,
        "pct_change": pct,
        "direction":  direction,
    }


# =============================================================================
# TOOL 15: calculate_percentile
# =============================================================================
@tool
def calculate_percentile(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
    percentiles: list | None = None,
    filters: list | None = None,
) -> dict:
    """
    Compute percentile values (P50/P90/P95/P99) of a numeric field.
    Use for SLA benchmarking, outlier detection, and performance distribution analysis.
    Also returns min, max, mean, and std_dev.

    percentiles is a list of integers e.g. [50, 90, 95, 99].
    If not provided, defaults to [50, 75, 90, 95, 99].

    Args:
        module:      Data module name
        field:       Numeric field to compute percentiles on
        percentiles: List of integer percentile values (1–99). Default: [50, 75, 90, 95, 99]
        filters:     Optional list of {"field": str, "value": str} dicts for AND pre-filtering
    """
    df = load_records_as_dataframe(state, module)

    if percentiles is None:
        percentiles = [50, 75, 90, 95, 99]

    try:
        percentiles = [int(p) for p in percentiles]
    except (TypeError, ValueError):
        return _err("percentiles must be a list of integers.")

    if df.empty:
        return {"_result_type": "percentile_data",
                "module": module, "field": field, "filters": filters or [], "records_used": 0,
                "percentile_values": {}, "mean": None, "std_dev": None,
                "minimum": None, "maximum": None}

    if filters:
        try:
            df = _apply_conditions(df, filters)
        except ValueError as e:
            return {"_result_type": "error", "error": str(e)}

    actual_field = resolve_column(df, field)
    if actual_field is None:
        return _err(f"Column '{field}' not found. Available: {list(df.columns)}")

    series = pd.to_numeric(df[actual_field], errors="coerce").dropna()
    if series.empty:
        return {"_result_type": "percentile_data",
                "module": module, "field": field, "filters": filters or [], "records_used": 0,
                "percentile_values": {}, "mean": None, "std_dev": None,
                "minimum": None, "maximum": None}

    pct_values = {}
    for p in percentiles:
        p = max(1, min(99, p))
        pct_values[f"p{p}"] = round(float(np.percentile(series, p)), 4)

    # Sample std dev (ddof=1, pandas default) is mathematically undefined for a
    # single data point — series.std() silently returns NaN rather than raising,
    # which would otherwise leak a raw NaN into the output instead of a clear None.
    std_dev = round(float(series.std()), 4) if len(series) >= 2 else None

    return {
        "_result_type":      "percentile_data",
        "module":            module,
        "field":             field,
        "filters":           filters or [],
        "records_used":      int(len(series)),
        "percentile_values": pct_values,
        "mean":              round(float(series.mean()), 4),
        "std_dev":           std_dev,
        "minimum":           round(float(series.min()), 4),
        "maximum":           round(float(series.max()), 4),
    }


# =============================================================================
# TOOL 16: forecast_linear
# =============================================================================
def _next_period_labels(last_label: str, n: int) -> list[str]:
    """Generate n real calendar period labels after last_label."""
    import re as _re

    # Year only: "2024"
    if _re.fullmatch(r'\d{4}', last_label):
        year = int(last_label)
        return [str(year + i) for i in range(1, n + 1)]

    # Month: "2024-01"
    m = _re.fullmatch(r'(\d{4})-(\d{2})', last_label)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        labels = []
        for _ in range(n):
            month += 1
            if month > 12:
                month = 1
                year += 1
            labels.append(f"{year}-{month:02d}")
        return labels

    # Week: "2024-W03"
    m = _re.fullmatch(r'(\d{4})-W(\d{1,2})', last_label)
    if m:
        year, week = int(m.group(1)), int(m.group(2))
        labels = []
        for _ in range(n):
            week += 1
            if week > 52:
                week = 1
                year += 1
            labels.append(f"{year}-W{week:02d}")
        return labels

    # Quarter: "2024Q1" or "2024-Q1"
    m = _re.fullmatch(r'(\d{4})[-]?Q(\d)', last_label)
    if m:
        year, q = int(m.group(1)), int(m.group(2))
        labels = []
        for _ in range(n):
            q += 1
            if q > 4:
                q = 1
                year += 1
            labels.append(f"{year}Q{q}")
        return labels

    # Fallback — unknown format
    return [f"forecast+{i}" for i in range(1, n + 1)]


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
        return _err("forecast_linear requires at least 2 data points from group_by_time_period.")

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

    valid_pairs = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(valid_pairs) < 2:
        return _err("Not enough valid numeric values to fit a forecast model.")

    x = np.array([p[0] for p in valid_pairs], dtype=float)
    y = np.array([p[1] for p in valid_pairs], dtype=float)

    xm   = x.mean()
    ym   = y.mean()
    ssxx = ((x - xm) ** 2).sum()
    ssxy = ((x - xm) * (y - ym)).sum()

    slope     = ssxy / ssxx if ssxx != 0 else 0.0
    intercept = ym - slope * xm

    y_pred = slope * x + intercept
    ss_res = ((y - y_pred) ** 2).sum()
    ss_tot = ((y - ym) ** 2).sum()
    r2     = 1 - (ss_res / ss_tot) if ss_tot != 0 else 1.0

    # Future period labels — derive from last known label where possible
    last_label = data[-1].get(label_key, f"period_{len(data)-1}") if data else ""
    future_labels = _next_period_labels(last_label, periods_ahead)
    forecast_list = []
    last_x = len(data) - 1
    for i, lbl in enumerate(future_labels, start=1):
        future_x  = last_x + i
        predicted = round(float(slope * future_x + intercept), 4)
        forecast_list.append({
            label_key:         lbl,
            "predicted_value": predicted,
        })

    return {
        "_result_type":     "forecast",
        "model_slope":     round(float(slope),     6),
        "model_intercept": round(float(intercept), 6),
        "r_squared":       round(float(r2),        6),
        "periods_ahead":   periods_ahead,
        "value_key":       value_key,
        "data_points":     len(valid_pairs),
        "last_known_label": last_label,
        "forecast":        forecast_list,
    }


# =============================================================================
# TOOL 17: compare_date_fields
# =============================================================================
@tool
def compare_date_fields(
    module: str,
    field_a: str,
    field_b: str,
    operator: str,
    state: Annotated[dict, InjectedState()],
    group_fields: list | None = None,
    filters: list | None = None,
) -> dict:
    """
    Compare two date columns per record and flag records where field_a {operator} field_b.
    Use for SLA breach detection, overdue detection, completion vs deadline analysis.

    operator options: gt (field_a > field_b), lt, gte, lte

    Examples:
      SLA breach:  field_a=BDMWOCompletedDate, field_b=SLABDMEndDateTime, operator=gt
      Overdue PPM: field_a=today (use calculate_age_from_now instead), or
                   flag records where WoCompletedDate > expected WoDateTime

    Args:
        module:       Data module name
        field_a:      First date column (e.g. the event that happened)
        field_b:      Second date column (e.g. the deadline or target)
        operator:     gt | lt | gte | lte
        group_fields: Optional list of columns for per-group breakdown
        filters:      Optional list of {"field": str, "value": str} dicts for AND pre-filtering
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"_result_type": "flagged_set",
                "module": module, "field_a": field_a, "field_b": field_b,
                "operator": operator, "filters": filters or [], "group_fields": group_fields or [],
                # 0/0 is undefined, not "0% flagged" — a real ratio only exists once
                # there are records to evaluate the comparison against.
                "flagged_count": 0, "total_records": 0, "flag_ratio": None,
                "valid_pairs": 0, "flagged_records": [], "groups": []}

    if filters:
        try:
            df = _apply_conditions(df, filters)
        except ValueError as e:
            return {"_result_type": "error", "error": str(e)}

    actual_a = resolve_column(df, field_a)
    actual_b = resolve_column(df, field_b)

    if actual_a is None:
        return _err(f"Column '{field_a}' not found. Available: {list(df.columns)}")
    if actual_b is None:
        return _err(f"Column '{field_b}' not found. Available: {list(df.columns)}")

    df = df.copy()
    df["_dt_a"] = pd.to_datetime(df[actual_a], dayfirst=True, errors="coerce")
    df["_dt_b"] = pd.to_datetime(df[actual_b], dayfirst=True, errors="coerce")

    valid = df.dropna(subset=["_dt_a", "_dt_b"])

    op = operator.lower()
    op_map = {
        "gt":  lambda a, b: a > b,
        "lt":  lambda a, b: a < b,
        "gte": lambda a, b: a >= b,
        "lte": lambda a, b: a <= b,
    }
    if op not in op_map:
        return _err(f"Unknown operator '{op}'. Valid: gt | lt | gte | lte")

    mask   = op_map[op](valid["_dt_a"], valid["_dt_b"])
    flagged = valid[mask].copy()
    total   = len(valid)
    n_flag  = len(flagged)

    # ── Flagged records list — full set, no cap (downstream steps need all records)
    flagged["day_diff"] = (flagged["_dt_a"] - flagged["_dt_b"]).dt.days
    drop_cols = {"_dt_a", "_dt_b"}
    keep_cols = [c for c in flagged.columns if c not in drop_cols]
    flagged_records = _clean_records(
        flagged[keep_cols].to_dict(orient="records")
    )

    groups = []
    if group_fields:
        resolved_groups = [resolve_column(df, f) for f in group_fields]
        actual_groups   = [r for r in resolved_groups if r is not None]
        if actual_groups:
            group_stats = []
            for grp_keys, grp_df in valid.groupby(actual_groups, sort=False):
                if not isinstance(grp_keys, tuple):
                    grp_keys = (grp_keys,)
                grp_mask  = op_map[op](grp_df["_dt_a"], grp_df["_dt_b"])
                grp_flag  = int(grp_mask.sum())
                grp_total = len(grp_df)
                row = {}
                for i, gf in enumerate(group_fields[:len(actual_groups)]):
                    row[gf] = _nan_to_none(grp_keys[i])
                row["flagged_count"] = grp_flag
                row["total"]         = grp_total
                row["flag_ratio"]    = round(grp_flag / grp_total, 4) if grp_total else 0.0
                group_stats.append(row)
            group_stats.sort(key=lambda r: r["flagged_count"], reverse=True)
            groups = group_stats

    return {
        "_result_type":    "flagged_set",
        "module":          module,
        "field_a":         field_a,
        "field_b":         field_b,
        "operator":        op,
        "filters":         filters or [],
        "total_records":   len(df),
        "valid_pairs":     total,
        "flagged_count":   n_flag,
        "flag_ratio":      round(n_flag / total, 4) if total else 0.0,
        "flagged_records": flagged_records,
        "group_fields":    group_fields or [],
        "groups":          groups,
    }


# =============================================================================
# TOOL 18: merge_and_score
# =============================================================================
@tool
def merge_and_score(
    datasets: list,
    group_key: str | list,
) -> dict:
    """
    Combine multiple prior-step group results into a single ranked/scored composite.
    Each dataset entry must be a dictionary:
      {
        "label": str,
        "data": list of dicts (from a prior group_by or join_and_aggregate step),
        "weight": float/int (relative importance, default 1.0),
        "value_key": str (name of the metric column to score, default "value"),
        "lower_is_better": bool (default False)
      }

    Note: All step references (e.g. $step_0.groups) are resolved by the queue runner
    before this tool is called — the tool receives plain Python lists, not $step refs.

    Returns a ranked list with composite_score per group.

    Args:
        datasets:  List of dataset dicts (see above)
        group_key: Common grouping field name or list of field names across all datasets
    """
    if not datasets:
        return _err("datasets must be a non-empty list.")
    if not group_key:
        return _err("group_key must be specified.")

    def _extract_dict_val(row, target_key):
        if not isinstance(row, dict):
            return None
        if isinstance(target_key, list):
            vals = []
            for tk in target_key:
                val = _extract_dict_val(row, tk)
                vals.append(val)
            if all(v is None for v in vals):
                return None
            return tuple(vals)

        try:
            if target_key in row:
                return row[target_key]
        except TypeError:
            pass

        if hasattr(target_key, "split"):
            clean_target = target_key.split(".")[-1].strip().lower()
            for k, v in row.items():
                clean_k = k.split(".")[-1].strip().lower()
                if clean_k == clean_target:
                    return v
        return None

    # Collect all group_key values across datasets
    all_keys_map: dict[str, Any] = {}
    for ds in datasets:
        data = ds.get("data", [])
        if isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    kv = _extract_dict_val(row, group_key)
                    if kv is not None:
                        if isinstance(kv, tuple):
                            str_key = str(tuple(str(x) if x is not None else "" for x in kv))
                        else:
                            str_key = str(kv)
                        all_keys_map[str_key] = kv

    all_keys = list(all_keys_map.keys())

    if not all_keys:
        return {
            "_result_type":  "scored_records",
            "group_key":     group_key,
            "datasets_used": [ds.get("label") for ds in datasets],
            "total_groups":  0,
            "ranked":        [],
        }

    total_weight = sum(float(ds.get("weight", 1)) for ds in datasets)
    if total_weight == 0:
        return _err("Total weight of all datasets cannot be zero.")

    # Build lookup: label → {group_key_value_string: numeric_value}
    lookup: dict = {}
    for ds in datasets:
        label     = ds.get("label", "")
        data      = ds.get("data", [])
        value_key = ds.get("value_key", "count")
        vals: dict = {}
        if isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    key_val = _extract_dict_val(row, group_key)
                    num_val = _extract_dict_val(row, value_key)
                    if num_val is None:
                        num_val = row.get("count") or row.get("value")
                    if key_val is not None:
                        if isinstance(key_val, tuple):
                            str_key = str(tuple(str(x) if x is not None else "" for x in key_val))
                        else:
                            str_key = str(key_val)
                        if num_val is None:
                            vals[str_key] = None
                        else:
                            try:
                                vals[str_key] = float(num_val)
                            except (TypeError, ValueError):
                                vals[str_key] = None
        lookup[label] = vals

    # Normalize each dataset to 0–100; invert if lower_is_better.
    normalized: dict = {}
    for ds in datasets:
        label           = ds.get("label", "")
        lower_is_better = bool(ds.get("lower_is_better", False))
        vals = lookup.get(label, {})

        known_vals = [v for v in vals.values() if v is not None]
        mn = min(known_vals) if known_vals else 0.0
        mx = max(known_vals) if known_vals else 0.0

        norm: dict = {}
        for k in all_keys:
            v = vals.get(k)
            if v is None:
                norm[k] = None
            elif mx != mn:
                score = (v - mn) / (mx - mn) * 100
                norm[k] = round(100 - score if lower_is_better else score, 4)
            else:
                norm[k] = 50.0
        normalized[label] = norm

    # Compute composite score per group.
    ranked = []
    for k in all_keys:
        orig_val = all_keys_map[k]
        if isinstance(group_key, list):
            row = {}
            for i, gk in enumerate(group_key):
                row[gk] = orig_val[i] if isinstance(orig_val, tuple) and i < len(orig_val) else None
        else:
            row = {group_key: orig_val}

        composite      = 0.0
        effective_wt   = 0.0
        for ds in datasets:
            label  = ds.get("label", "")
            weight = float(ds.get("weight", 1))
            score  = normalized.get(label, {}).get(k)
            if score is not None:
                row[f"{label}_score"] = round(score, 4)
                composite   += score * weight
                effective_wt += weight
            else:
                row[f"{label}_score"] = None
        row["composite_score"] = (
            round(composite / effective_wt, 4) if effective_wt > 0 else None
        )
        ranked.append(row)

    # composite_score can be None when a group has no data in any dataset.
    ranked.sort(
        key=lambda r: r["composite_score"] if r["composite_score"] is not None else -1,
        reverse=True,
    )

    return {
        "_result_type":  "scored_records",
        "group_key":     group_key,
        "datasets_used": [ds.get("label") for ds in datasets],
        "total_groups":  len(ranked),
        "ranked":        ranked,
    }


# =============================================================================
# TOOL 19: add_duration_to_date
# =============================================================================
@tool
def add_duration_to_date(
    module: str,
    date_field: str,
    duration_field: str,
    state: Annotated[dict, InjectedState()],
    duration_unit: str = "years",
    filters: list | None = None,
) -> dict:
    """
    For each record, add a duration value to a date field to compute an expected end date,
    then calculate days_remaining from today. Negative days_remaining = already expired.

    Use for: asset remaining life (InstalledDate + LifeInYear), contract expiry,
    warranty expiry, expected maintenance schedule.

    duration_unit: "years" | "months" | "days"

    Args:
        module:         Data module name
        date_field:     Column containing the start date (e.g. InstalledDate)
        duration_field: Column containing the duration value (e.g. LifeInYear)
        duration_unit:  Unit of the duration field: years | months | days  (default: years)
        filters:        Optional list of {"field": str, "value": str} dicts for AND pre-filtering
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"_result_type": "record_set",
                "module": module, "date_field": date_field, "duration_field": duration_field,
                "duration_unit": duration_unit.lower() if isinstance(duration_unit, str) else duration_unit,
                "filters": filters or [],
                "total": 0, "expired_count": 0, "records": []}

    if filters:
        try:
            df = _apply_conditions(df, filters)
        except ValueError as e:
            return {"_result_type": "error", "error": str(e)}

    actual_date = resolve_column(df, date_field)
    actual_dur  = resolve_column(df, duration_field)

    if actual_date is None:
        return _err(f"date_field '{date_field}' not found. Available: {list(df.columns)}")
    if actual_dur is None:
        return _err(f"duration_field '{duration_field}' not found. "
                     f"Available: {list(df.columns)}")

    df        = df.copy()
    today     = pd.Timestamp.now(tz=None).normalize()
    unit      = duration_unit.lower()

    df["_start_dt"] = pd.to_datetime(df[actual_date], dayfirst=True, errors="coerce")
    df["_duration"] = pd.to_numeric(df[actual_dur], errors="coerce")

    def _compute_end(row):
        if pd.isna(row["_start_dt"]) or pd.isna(row["_duration"]):
            return None
        dur = float(row["_duration"])
        dt  = row["_start_dt"]
        if unit == "years":
            try:
                return dt.replace(year=dt.year + int(dur))
            except ValueError:
                return dt + pd.DateOffset(years=int(dur))
        elif unit == "months":
            return dt + pd.DateOffset(months=int(dur))
        else:  # days
            return dt + pd.Timedelta(days=dur)

    df["_end_dt"]        = df.apply(_compute_end, axis=1)
    df["_days_remaining"] = df["_end_dt"].apply(
        lambda e: int((e - today).days) if e is not None and pd.notna(e) else None
    )

    # Build clean output records (strip internal _ columns)
    output_records = []
    for _, row in df.iterrows():
        clean = {k: _nan_to_none(v) for k, v in row.items() if not k.startswith("_")}
        end_dt = row["_end_dt"]
        days   = row["_days_remaining"]
        clean["expected_end_date"] = (
            end_dt.strftime("%Y-%m-%d") if end_dt is not None and pd.notna(end_dt) else None
        )
        clean["days_remaining"] = int(days) if pd.notna(days) else None
        output_records.append(clean)

    expired_count = sum(
        1 for r in output_records
        if r.get("days_remaining") is not None and r["days_remaining"] < 0
    )

    return {
        "_result_type":   "record_set",
        "module":         module,
        "date_field":     date_field,
        "duration_field": duration_field,
        "duration_unit":  unit,
        "filters":        filters or [],
        "total":          len(output_records),
        "expired_count":  expired_count,
        "records":        output_records[:200],
    }


# =============================================================================
# TOOL 20: join_and_filter_by_date_diff
# =============================================================================
@tool
def join_and_filter_by_date_diff(
    module_a:      str,
    module_b:      str,
    join_field:    str,
    date_field_a:  str,
    date_field_b:  str,
    operator:      str,
    threshold_days: int,
    state: Annotated[dict, InjectedState()],
    fields:        list | None = None,
    filters_a:     list | None = None,
    filters_b:     list | None = None,
) -> dict:
    """
    Inner-join two modules on a shared key field, compute the day difference between
    a date column from each module, then return records where that difference satisfies
    a threshold condition.

    Use when you need to find events in one module that occurred within / after / before
    N days of a reference event in another module, joined per asset or entity.

    Example: find breakdowns (bdm) that occurred within 7 days after a PPM completion (ppm),
    matched by AssetTagNo.

    operator options:
      within_days  — 0 <= (date_field_a - date_field_b).days <= threshold_days
      after_days   — (date_field_a - date_field_b).days > threshold_days
      before_days  — (date_field_a - date_field_b).days < 0  (date_a is before date_b)
      gt           — day_diff > threshold_days
      lt           — day_diff < threshold_days
      gte          — day_diff >= 0
      lte          — day_diff <= threshold_days

    date_field_a is typically the event to test (e.g. breakdown date from bdm).
    date_field_b is typically the reference event (e.g. PPM completion date from ppm).
    day_diff is computed as (date_a - date_b).days — positive = date_a is later.

    Each returned record includes a computed 'day_diff' field showing the exact gap.

    Args:
        module_a:       First module (the event module, e.g. "bdm")
        module_b:       Second module (the reference module, e.g. "ppm")
        join_field:     Column shared by both modules to join on (e.g. "AssetTagNo")
        date_field_a:   Date column from module_a (the event date, e.g. "ComplainedDateTime")
        date_field_b:   Date column from module_b (the reference date, e.g. "WoCompletedDate")
        operator:       within_days | after_days | before_days | gt | lt | gte | lte
        threshold_days: Day threshold for the comparison (e.g. 7)
        fields:         Optional list of columns to include in output records (empty = all)
        filters_a:      Optional pre-filters for module_a as [{\"field\": str, \"value\": str}]
        filters_b:      Optional pre-filters for module_b as [{\"field\": str, \"value\": str}]
    """
    df_a = load_records_as_dataframe(state, module_a)
    df_b = load_records_as_dataframe(state, module_b)

    if df_a.empty:
        return _err(f"No data found for module '{module_a}'.")
    if df_b.empty:
        return _err(f"No data found for module '{module_b}'.")

    # ── Apply pre-filters ────────────────────────────────────────────────────
    if filters_a:
        try:
            df_a = _apply_conditions(df_a, filters_a)
        except ValueError as e:
            return _err(f"filters_a error: {e}")
    if filters_b:
        try:
            df_b = _apply_conditions(df_b, filters_b)
        except ValueError as e:
            return _err(f"filters_b error: {e}")

    # ── Post-filter empty check ──────────────────────────────────────────────
    if df_a.empty or df_b.empty:
        return {
            "_result_type":   "date_filtered_join",
            "module_a":       module_a,
            "module_b":       module_b,
            "join_field":     join_field,
            "date_field_a":   date_field_a,
            "date_field_b":   date_field_b,
            "operator":       operator,
            "threshold_days": threshold_days,
            "filters_a":      filters_a or [],
            "filters_b":      filters_b or [],
            "total_joined":   0,
            "matched_count":  0,
            "matched_records": [],
        }

    # ── Resolve join field in both modules ───────────────────────────────────
    actual_join_a = resolve_column(df_a, join_field)
    actual_join_b = resolve_column(df_b, join_field)

    if actual_join_a is None:
        return _err(
            f"join_field '{join_field}' not found in '{module_a}'. "
            f"Available: {sorted(df_a.columns.tolist())}"
        )
    if actual_join_b is None:
        return _err(
            f"join_field '{join_field}' not found in '{module_b}'. "
            f"Available: {sorted(df_b.columns.tolist())}"
        )

    # ── Resolve date fields before renaming ─────────────────────────────────
    actual_date_a = resolve_column(df_a, date_field_a)
    actual_date_b = resolve_column(df_b, date_field_b)

    if actual_date_a is None:
        return _err(
            f"date_field_a '{date_field_a}' not found in '{module_a}'. "
            f"Available: {sorted(df_a.columns.tolist())}"
        )
    if actual_date_b is None:
        return _err(
            f"date_field_b '{date_field_b}' not found in '{module_b}'. "
            f"Available: {sorted(df_b.columns.tolist())}"
        )

    # ── Normalise join key types for clean merge ─────────────────────────────
    df_a = df_a.copy()
    df_b = df_b.copy()
    df_a[actual_join_a] = df_a[actual_join_a].fillna("").astype(str).str.strip()
    df_b[actual_join_b] = df_b[actual_join_b].fillna("").astype(str).str.strip()

    # ── Rename overlapping columns (suffix _a / _b) except the join key ──────
    overlap = (set(df_a.columns) & set(df_b.columns)) - {actual_join_a}
    if overlap:
        df_a = df_a.rename(columns={c: f"{c}_a" for c in overlap})
        df_b = df_b.rename(columns={c: f"{c}_b" for c in overlap})
        # Update resolved names after renaming
        if actual_date_a in overlap:
            actual_date_a = f"{actual_date_a}_a"
        if actual_date_b in overlap:
            actual_date_b = f"{actual_date_b}_b"
        actual_join_b_r = actual_join_b if actual_join_b not in overlap else f"{actual_join_b}_b"
    else:
        actual_join_b_r = actual_join_b

    # ── Inner join ───────────────────────────────────────────────────────────
    merged = pd.merge(
        df_a, df_b,
        left_on=actual_join_a, right_on=actual_join_b_r,
        how="inner",
    )

    if merged.empty:
        return {
            "_result_type":   "date_filtered_join",
            "module_a":       module_a,
            "module_b":       module_b,
            "join_field":     join_field,
            "date_field_a":   date_field_a,
            "date_field_b":   date_field_b,
            "operator":       operator,
            "threshold_days": threshold_days,
            "filters_a":      filters_a or [],
            "filters_b":      filters_b or [],
            "total_joined":   0,
            "matched_count":  0,
            "matched_records": [],
        }

    # ── Parse date columns ───────────────────────────────────────────────────
    merged["_dt_a"] = pd.to_datetime(merged[actual_date_a], dayfirst=True, errors="coerce")
    merged["_dt_b"] = pd.to_datetime(merged[actual_date_b], dayfirst=True, errors="coerce")

    valid = merged.dropna(subset=["_dt_a", "_dt_b"]).copy()
    valid["day_diff"] = (valid["_dt_a"] - valid["_dt_b"]).dt.days

    # ── Apply operator filter ────────────────────────────────────────────────
    op = operator.lower()
    try:
        thr = int(threshold_days)
    except (TypeError, ValueError):
        return _err(f"threshold_days must be an integer, got: {threshold_days!r}")

    op_map = {
        "within_days":  lambda d: (d >= 0) & (d <= thr),
        "after_days":   lambda d: d > thr,
        "before_days":  lambda d: d < 0,
        "gt":           lambda d: d > thr,
        "lt":           lambda d: d < thr,
        "gte":          lambda d: d >= 0,
        "lte":          lambda d: d <= thr,
    }
    if op not in op_map:
        return _err(
            f"Unknown operator '{op}'. "
            f"Valid: within_days | after_days | before_days | gt | lt | gte | lte"
        )

    mask    = op_map[op](valid["day_diff"])
    matched = valid[mask]

    # ── Build output records ─────────────────────────────────────────────────
    drop_cols = {"_dt_a", "_dt_b"}
    keep_cols = [c for c in matched.columns if c not in drop_cols]

    if fields:
        # Resolve each requested field name to actual column in merged result
        resolved_fields = []
        for f in fields:
            col = resolve_column(matched, f)
            if col:
                resolved_fields.append(col)
        if resolved_fields:
            # Always include join_field and day_diff
            must_have = {actual_join_a, "day_diff"}
            keep_cols = list(must_have | set(resolved_fields))

    out_df = matched[keep_cols]  # full set — no cap, downstream steps need all records

    records = _clean_records(out_df.to_dict(orient="records"))

    return {
        "_result_type":   "date_filtered_join",
        "module_a":       module_a,
        "module_b":       module_b,
        "join_field":     join_field,
        "date_field_a":   date_field_a,
        "date_field_b":   date_field_b,
        "operator":       op,
        "threshold_days": thr,
        "filters_a":      filters_a or [],
        "filters_b":      filters_b or [],
        "total_joined":   len(valid),
        "matched_count":  len(matched),
        "matched_records": records,
    }


# =============================================================================
# TOOL 22: calculate_date_difference_stats
# =============================================================================
@tool
def calculate_date_difference_stats(
    module: str,
    start_date_field: str,
    end_date_field: str,
    state: Annotated[dict, InjectedState()],
    group_fields: list | None = None,
    filters: list | None = None,
) -> dict:
    """
    Calculate the duration between two date fields (end_date - start_date) in days.
    Returns overall stats (avg/min/max days) and optionally a per-group breakdown.
    Use for Mean Time To Repair (MTTR), resolution TAT, or any duration metric.

    Args:
        module:           Data module name
        start_date_field: Column containing the starting date/time
        end_date_field:   Column containing the ending date/time
        group_fields:     Optional list of columns to group the stats by (e.g. ["ContractName"])
        filters:          Optional list of {"field": str, "value": str} dicts for AND pre-filtering
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {"_result_type": "date_difference_stats",
                "module": module, "start_date_field": start_date_field, "end_date_field": end_date_field,
                "filters": filters or [],
                "total_records": 0, "avg_diff_days": None, "max_diff_days": None, "min_diff_days": None,
                "calculated": 0, "groups": []}

    if filters:
        df, err = _safe_apply(df, filters)
        if err:
            return err

    actual_start = resolve_column(df, start_date_field)
    actual_end   = resolve_column(df, end_date_field)

    if actual_start is None:
        return _err(f"Column '{start_date_field}' not found. Available: {list(df.columns)}")
    if actual_end is None:
        return _err(f"Column '{end_date_field}' not found. Available: {list(df.columns)}")

    df = df.copy()
    df["_start_dt"] = pd.to_datetime(df[actual_start], dayfirst=True, errors="coerce")
    df["_end_dt"]   = pd.to_datetime(df[actual_end], dayfirst=True, errors="coerce")

    # calculate diff in days
    df["_diff_days"] = (df["_end_dt"] - df["_start_dt"]).dt.total_seconds() / 86400.0

    valid = df.dropna(subset=["_diff_days"])
    diffs = valid["_diff_days"]

    result = {
        "_result_type":     "date_difference_stats",
        "module":           module,
        "start_date_field": start_date_field,
        "end_date_field":   end_date_field,
        "filters":          filters or [],
        "total_records":    len(df),
        "calculated":       len(valid),
        "avg_diff_days":    round(float(diffs.mean()), 2) if not diffs.empty else None,
        "max_diff_days":    round(float(diffs.max()), 2)  if not diffs.empty else None,
        "min_diff_days":    round(float(diffs.min()), 2)  if not diffs.empty else None,
    }

    if group_fields:
        resolved_groups = [resolve_column(valid, f) for f in group_fields]
        actual_groups   = [r for r in resolved_groups if r is not None]
        if actual_groups:
            # groupby
            g = valid.groupby(actual_groups, dropna=False)
            group_stats = []
            for name, grp in g:
                if isinstance(name, tuple):
                    group_dict = dict(zip(actual_groups, name))
                else:
                    group_dict = {actual_groups[0]: name}
                    
                g_diffs = grp["_diff_days"]
                group_dict["records"] = len(grp)
                group_dict["avg_diff_days"] = round(float(g_diffs.mean()), 2) if not g_diffs.empty else None
                group_dict["max_diff_days"] = round(float(g_diffs.max()), 2) if not g_diffs.empty else None
                group_dict["min_diff_days"] = round(float(g_diffs.min()), 2) if not g_diffs.empty else None
                group_stats.append(group_dict)
                
            # sort by avg_diff_days desc
            group_stats.sort(key=lambda x: (x["avg_diff_days"] is None, x["avg_diff_days"] and -x["avg_diff_days"]))
            result["groups"] = _clean_records(group_stats)
        else:
            result["groups"] = []
    else:
        result["groups"] = []

    return result
