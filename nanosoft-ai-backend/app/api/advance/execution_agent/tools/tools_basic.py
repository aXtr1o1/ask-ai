"""
Basic FM Analytics Tools (Tools 1–10)

  1.  count_records          → count all records or records matching condition(s)
  2.  sum_values             → sum a numeric field
  3.  get_average            → mean of a numeric field
  4.  group_by_and_count     → group by one or more fields and count per group
  5.  group_by_and_aggregate → SUM | AVG | MIN | MAX of a numeric field per group
  6.  join_and_aggregate     → inner-join two modules on shared key + aggregate per group
  7.  get_record_fields      → return actual record data — specific fields or all fields
  8.  do_math                → arithmetic: ADD | SUB | MUL | DIV | MOD | POWER | SQRT | ABS
  9.  sort_and_limit         → sort a list from a prior step and optionally keep top/bottom N
  10. final_answer_tool      → marks queue complete, MUST be the last step
"""
import math
from typing import Annotated

import pandas as pd
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from app.api.advance.execution_agent.tools.tool_helpers import (
    load_records_as_dataframe,
    get_numeric_column,
    resolve_column,
    _apply_conditions,
    _clean_records,
    _is_unresolved_ref,
    _err,
    _insufficient,
    _safe_apply,
    _sparsity_note,
)

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
        [{"field": "WoStatus", "value": "Open"}, {"field": "PriorityName", "value": "High"}]
        All conditions are applied with AND logic.

    Returns an error if any field name cannot be found in the module data or if
    an unresolved $step_N reference is detected.

    Args:
        module:          Data module name
        condition_field: Column to filter on (single condition, optional)
        condition_value: Value to match in condition_field; "" matches blank/null
        conditions:      List of {"field": str, "value": str} dicts for AND filtering
    """
    df = load_records_as_dataframe(state, module)

    if conditions:
        df, err = _safe_apply(df, conditions)
        if err:
            return err
        return {
            "_result_type": "single_number",
            "module": module,
            "count": len(df),
            "conditions": conditions,
        }

    if condition_field:
        if _is_unresolved_ref(condition_field):
            return _err(f"condition_field is an unresolved reference: '{condition_field}'")
        if _is_unresolved_ref(condition_value):
            return _err(f"condition_value is an unresolved reference: '{condition_value}'")
        actual_field = resolve_column(df, condition_field)
        if actual_field is None:
            return _err(
                f"condition_field '{condition_field}' not found in '{module}'. "
                f"Available columns: {sorted(df.columns.tolist())}"
            )
        col = df[actual_field].fillna("").astype(str).str.strip()
        if condition_value == "":
            df = df[col == ""]
        else:
            df = df[col.str.lower() == condition_value.lower()]

    return {
        "_result_type":    "single_number",
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
    filters: list | None = None,
) -> dict:
    """
    Sum all values in a numeric field across all records in a module.
    Optionally filter rows before summing using multi-condition AND logic.

    Args:
        module:  Data module name
        field:   Numeric column to sum
        filters: Optional list of {"field": str, "value": str} dicts for AND pre-filtering
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        # No matching records at all — a sum has nothing to add up, so this is
        # "not computed" (None), not "computed as zero" (0). A real 0 total only
        # exists once actual records with real values are found and summed.
        return {
            "_result_type": "single_number",
            "module": module, "field": field, "filters": filters or [],
            "total_sum": None, "records_used": 0,
            "_note": f"No records found in '{module}' matching the given filters — cannot compute a sum.",
        }

    if filters:
        df, err = _safe_apply(df, filters)
        if err:
            return err

    actual_field = resolve_column(df, field)
    if actual_field is None:
        return _err(
            f"Field '{field}' not found in '{module}'. "
            f"Available: {sorted(df.columns.tolist())}"
        )

    numbers = get_numeric_column(df, actual_field)
    if numbers.empty:
        return _insufficient(f"Field '{field}' in '{module}' contains no usable numeric values.")

    result = {
        "_result_type": "single_number",
        "module":       module,
        "field":        field,
        "filters":      filters or [],
        "total_sum":    round(float(numbers.sum()), 4),
        "records_used": int(numbers.count()),
    }
    note = _sparsity_note(df, actual_field, field)
    if note:
        result["_data_quality_note"] = note
    return result


# =============================================================================
# TOOL 3: get_average
# =============================================================================
@tool
def get_average(
    module: str,
    field: str,
    state: Annotated[dict, InjectedState()],
    filters: list | None = None,
) -> dict:
    """
    Compute the mean of a numeric field across all records in a module.
    Optionally filter rows before averaging using multi-condition AND logic.

    Args:
        module:  Data module name
        field:   Numeric column to average
        filters: Optional list of {"field": str, "value": str} dicts for AND pre-filtering
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {
            "_result_type": "single_number",
            "module": module, "field": field, "filters": filters or [],
            "average": None, "records_used": 0,
        }

    if filters:
        df, err = _safe_apply(df, filters)
        if err:
            return err

    actual_field = resolve_column(df, field)
    if actual_field is None:
        return _err(
            f"Field '{field}' not found in '{module}'. "
            f"Available: {sorted(df.columns.tolist())}"
        )

    numbers = get_numeric_column(df, actual_field)
    if numbers.empty:
        return _insufficient(f"Field '{field}' in '{module}' contains no usable numeric values after filtering.")

    result = {
        "_result_type": "single_number",
        "module":       module,
        "field":        field,
        "filters":      filters or [],
        "average":      round(float(numbers.mean()), 4),
        "records_used": int(numbers.count()),
    }
    note = _sparsity_note(df, actual_field, field)
    if note:
        result["_data_quality_note"] = note
    return result


# =============================================================================
# TOOL 4: group_by_and_count
# =============================================================================
@tool
def group_by_and_count(
    module: str,
    group_fields: list,
    state: Annotated[dict, InjectedState()],
    filters: list | None = None,
) -> dict:
    """
    Group records by one or more categorical fields and count per group.
    Results sorted highest count first.
    Optionally filter rows before grouping using multi-condition AND logic.

    Args:
        module:       Data module name
        group_fields: List of columns to group by.
                      Single field: ["BuildingName"]
                      Multi-field:  ["BuildingName", "DisciplineName"]
        filters:      Optional list of {"field": str, "value": str} dicts for AND pre-filtering
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {
            "_result_type": "grouped_data",
            "module": module, "group_fields": group_fields, "filters": filters or [],
            "total_records": 0, "count": 0, "unique_groups": 0, "groups": [],
        }

    if not group_fields:
        return _err("group_fields must be a non-empty list.")

    if filters:
        df, err = _safe_apply(df, filters)
        if err:
            return err

    resolved = [resolve_column(df, f) for f in group_fields]
    actual_cols = [r for r in resolved if r is not None]
    if not actual_cols:
        return _err(
            f"None of group_fields {group_fields} found in '{module}'. "
            f"Available: {sorted(df.columns.tolist())}"
        )

    grouped = (
        df.groupby(actual_cols, dropna=False)
          .size()
          .reset_index(name="count")
          .sort_values("count", ascending=False)
    )
    rename_map = {actual: requested
                  for actual, requested in zip(actual_cols, group_fields)
                  if actual != requested}
    if rename_map:
        grouped = grouped.rename(columns=rename_map)

    result = {
        "_result_type":  "grouped_data",
        "module":        module,
        "group_fields":  group_fields,
        "filters":       filters or [],
        "total_records": len(df),
        "count":         len(df),
        "unique_groups": len(grouped),
        "groups":        _clean_records(grouped.to_dict(orient="records")),
    }
    # A group_fields column that's mostly blank produces a technically-correct
    # but practically useless leaderboard (e.g. grouping breakdowns by AssetTagNo
    # when most work orders were never linked to an asset at data-entry time).
    notes = [n for n in (_sparsity_note(df, col, requested)
                         for col, requested in zip(actual_cols, group_fields)) if n]
    if notes:
        result["_data_quality_note"] = " ".join(notes)
    return result


# =============================================================================
# TOOL 5: group_by_and_aggregate
# =============================================================================
@tool
def group_by_and_aggregate(
    module: str,
    group_fields: list,
    agg_field: str,
    operation: str,
    state: Annotated[dict, InjectedState()],
    filters: list | None = None,
    data: list | None = None,
) -> dict:
    """
    Group records by one or more fields and compute SUM | AVG | MIN | MAX of a
    numeric field per group. Results sorted highest value first.
    Optionally filter rows before grouping using multi-condition AND logic.

    By default reads directly from module. Pass data (a prior step's own
    output list, e.g. $step_N.records) instead when the field being grouped
    or aggregated only exists on that step's output and not on the original
    module — data takes priority over module when both are given.

    Args:
        module:       Data module name
        group_fields: List of columns to group by. e.g. ["BuildingName"] or
                      ["BuildingName", "DisciplineName"]
        agg_field:    Numeric column to aggregate
        operation:    SUM | AVG | MIN | MAX
        filters:      Optional list of {"field": str, "value": str} dicts for AND pre-filtering
        data:         Optional list of record dicts from a prior step (e.g. $step_N.records)
    """
    # An LLM occasionally resolves a $step_N reference into `module` itself
    # instead of `data` — treat a list landing in `module` the same way
    # flag_by_threshold does, rather than failing on a type mismatch.
    if isinstance(module, list):
        data, module = module, ""

    if data is not None and isinstance(data, list) and data:
        df = pd.DataFrame(data)
    else:
        df = load_records_as_dataframe(state, module)

    module_label = module or "the prior step's data"

    if df.empty:
        return {
            "_result_type": "grouped_data",
            "module": module, "group_fields": group_fields, "agg_field": agg_field,
            "operation": operation.upper(), "filters": filters or [], "total_records": 0,
            "count": 0, "unique_groups": 0, "groups": [],
        }

    if not group_fields:
        return _err("group_fields must be a non-empty list.")

    if filters:
        df, err = _safe_apply(df, filters)
        if err:
            return err

    resolved_groups = [resolve_column(df, f) for f in group_fields]
    actual_group_cols = [r for r in resolved_groups if r is not None]
    if not actual_group_cols:
        return _err(
            f"None of group_fields {group_fields} found in '{module_label}'. "
            f"Available: {sorted(df.columns.tolist())}"
        )

    op = operation.upper()
    valid_ops = {"SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT"}
    if op not in valid_ops:
        return _err(f"Unknown operation '{op}'. Valid: SUM | AVG | MIN | MAX | COUNT | COUNT_DISTINCT")

    df = df.copy()
    if op == "COUNT" or not agg_field:
        valid_count = len(df)
        grouped = (
            df.groupby(actual_group_cols, dropna=False)
              .size()
              .reset_index(name="value")
              .sort_values("value", ascending=False)
        )
    elif op == "COUNT_DISTINCT":
        actual_agg = resolve_column(df, agg_field)
        if actual_agg is None:
            return _err(
                f"agg_field '{agg_field}' not found in '{module_label}'. "
                f"Available: {sorted(df.columns.tolist())}"
            )
        df[actual_agg] = df[actual_agg].fillna("").astype(str).str.strip()
        valid_count = len(df)
        grouped = (
            df.groupby(actual_group_cols, dropna=False)[actual_agg]
              .nunique()
              .reset_index()
              .rename(columns={actual_agg: "value"})
              .sort_values("value", ascending=False)
        )
    else:
        actual_agg = resolve_column(df, agg_field)
        if actual_agg is None:
            return _err(
                f"agg_field '{agg_field}' not found in '{module_label}'. "
                f"Available: {sorted(df.columns.tolist())}"
            )
        df[actual_agg] = pd.to_numeric(df[actual_agg], errors="coerce")
        valid_count = int(df[actual_agg].notna().sum())
        if valid_count == 0:
            return _insufficient(
                f"agg_field '{agg_field}' in '{module_label}' contains no usable numeric values. "
                f"Cannot compute {op}."
            )
        agg_fn_map = {"SUM": "sum", "AVG": "mean", "MIN": "min", "MAX": "max"}
        grouped = (
            df.groupby(actual_group_cols, dropna=False)[actual_agg]
              .agg(agg_fn_map[op])
              .round(4)
              .reset_index()
              .rename(columns={actual_agg: "value"})
              .sort_values("value", ascending=False, na_position="last")
        )
    rename_map = {actual: requested
                  for actual, requested in zip(actual_group_cols, group_fields)
                  if actual != requested}
    if rename_map:
        grouped = grouped.rename(columns=rename_map)

    result = {
        "_result_type":  "grouped_data",
        "module":        module,
        "group_fields":  group_fields,
        "agg_field":     agg_field,
        "operation":     op,
        "filters":       filters or [],
        "total_records": valid_count,
        "count":         valid_count,
        "unique_groups": len(grouped),
        "groups":        _clean_records(grouped.to_dict(orient="records")),
    }
    # Sparsity caveat only applies to real aggregates over a numeric field —
    # COUNT/COUNT_DISTINCT measure presence itself, so sparsity is the answer, not a caveat.
    if op not in ("COUNT", "COUNT_DISTINCT") and agg_field:
        actual_agg_col = resolve_column(df, agg_field)
        if actual_agg_col:
            note = _sparsity_note(df, actual_agg_col, agg_field)
            if note:
                result["_data_quality_note"] = note
    return result


# =============================================================================
# TOOL 6: join_and_aggregate
# =============================================================================
@tool
def join_and_aggregate(
    module_a: str,
    module_b: str,
    join_field: str,
    group_fields: list,
    agg_field: str,
    operation: str,
    state: Annotated[dict, InjectedState()],
    filters_a: list | None = None,
    filters_b: list | None = None,
) -> dict:
    """
    Inner-join two modules on a shared key field, then group by one or more fields
    and compute SUM | AVG | MIN | MAX | COUNT of a numeric field from the joined result.

    Use when the grouping dimension is in module_a and the metric is in module_b,
    or when you need cross-module analysis that a single module cannot answer.

    group_fields and agg_field refer to columns present in either module after joining.
    For COUNT leave agg_field as "" and operation as "COUNT".

    Args:
        module_a:     First module (left side of join)
        module_b:     Second module (right side of join)
        join_field:   Column name shared by both modules to join on
        group_fields: List of columns to group by in the joined result
        agg_field:    Numeric column to aggregate (empty string for COUNT)
        operation:    SUM | AVG | MIN | MAX | COUNT
        filters_a:    Optional pre-filters applied to module_a before joining
        filters_b:    Optional pre-filters applied to module_b before joining
    """
    df_a = load_records_as_dataframe(state, module_a)
    df_b = load_records_as_dataframe(state, module_b)

    if df_a.empty:
        return _err(f"No data found for module '{module_a}'.")
    if df_b.empty:
        return _err(f"No data found for module '{module_b}'.")

    if not group_fields:
        return _err("group_fields must be a non-empty list.")
    if filters_a:
        df_a, err = _safe_apply(df_a, filters_a)
        if err:
            return err

    if filters_b:
        df_b, err = _safe_apply(df_b, filters_b)
        if err:
            return err

    # Post-filter empty check
    if df_a.empty or df_b.empty:
        return {
            "_result_type":  "grouped_data",
            "module_a":      module_a,
            "module_b":      module_b,
            "join_field":    join_field,
            "group_fields":  group_fields,
            "agg_field":     agg_field,
            "operation":     operation.upper() if isinstance(operation, str) else operation,
            "matched_count": 0,
            "unique_groups": 0,
            "total_records": 0,
            "groups":        [],
        }

    actual_join_a = resolve_column(df_a, join_field)
    actual_join_b = resolve_column(df_b, join_field)

    if actual_join_a is None or actual_join_b is None:
        # Fallback: find common join columns present in both module_a and module_b
        for candidate in ("AssetTagNo", "BuildingName", "SpotName", "LocalityName"):
            cand_a = resolve_column(df_a, candidate)
            cand_b = resolve_column(df_b, candidate)
            if cand_a is not None and cand_b is not None:
                actual_join_a = cand_a
                actual_join_b = cand_b
                break

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

    # Standardise join key types for clean merge
    df_a = df_a.copy()
    df_b = df_b.copy()
    df_a[actual_join_a] = df_a[actual_join_a].fillna("").astype(str).str.strip()
    df_b[actual_join_b] = df_b[actual_join_b].fillna("").astype(str).str.strip()

    # Resolve column name conflicts (suffix _a / _b for duplicates except join key)
    overlap = (set(df_a.columns) & set(df_b.columns)) - {actual_join_a}
    if overlap:
        df_a = df_a.rename(columns={c: f"{c}_a" for c in overlap})
        df_b = df_b.rename(columns={c: f"{c}_b" for c in overlap})
        actual_join_b_r = actual_join_b if actual_join_b not in overlap else f"{actual_join_b}_b"
    else:
        actual_join_b_r = actual_join_b

    merged = pd.merge(df_a, df_b,
                      left_on=actual_join_a, right_on=actual_join_b_r,
                      how="inner")

    if merged.empty:
        return {
            "_result_type":  "grouped_data",
            "module_a":      module_a,
            "module_b":      module_b,
            "join_field":    join_field,
            "group_fields":  group_fields,
            "agg_field":     agg_field,
            "operation":     operation.upper() if isinstance(operation, str) else operation,
            "matched_count": 0,
            "unique_groups": 0,
            "total_records": 0,
            "groups":        [],
        }

    op = operation.upper()
    valid_ops = {"SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT"}
    if op not in valid_ops:
        return _err(f"Unknown operation '{op}'. Valid: SUM | AVG | MIN | MAX | COUNT | COUNT_DISTINCT")

    resolved_groups = [resolve_column(merged, f) for f in group_fields]
    missing = [group_fields[i] for i, r in enumerate(resolved_groups) if r is None]
    if missing:
        return _err(
            f"group_fields {missing} not found in joined result. "
            f"Available: {sorted(merged.columns.tolist())}"
        )

    actual_group_cols = [r for r in resolved_groups if r is not None]

    if op == "COUNT" or not agg_field:
        grouped = (
            merged.groupby(actual_group_cols, dropna=False)
                  .size()
                  .reset_index(name="value")
                  .sort_values("value", ascending=False)
        )
    elif op == "COUNT_DISTINCT":
        actual_agg = resolve_column(merged, agg_field)
        if actual_agg is None:
            return _err(
                f"agg_field '{agg_field}' not found in joined result. "
                f"Available: {sorted(merged.columns.tolist())}"
            )
        merged[actual_agg] = merged[actual_agg].fillna("").astype(str).str.strip()
        grouped = (
            merged.groupby(actual_group_cols, dropna=False)[actual_agg]
                  .nunique()
                  .reset_index()
                  .rename(columns={actual_agg: "value"})
                  .sort_values("value", ascending=False)
        )
    else:
        actual_agg = resolve_column(merged, agg_field)
        if actual_agg is None:
            return _err(
                f"agg_field '{agg_field}' not found in joined result. "
                f"Available: {sorted(merged.columns.tolist())}"
            )
        merged[actual_agg] = pd.to_numeric(merged[actual_agg], errors="coerce")
        if merged[actual_agg].notna().sum() == 0:
            return _insufficient(
                f"agg_field '{agg_field}' in the joined result contains no usable numeric values."
            )
        agg_fn_map = {"SUM": "sum", "AVG": "mean", "MIN": "min", "MAX": "max"}
        grouped = (
            merged.groupby(actual_group_cols, dropna=False)[actual_agg]
                  .agg(agg_fn_map[op])
                  .round(4)
                  .reset_index()
                  .rename(columns={actual_agg: "value"})
                  .sort_values("value", ascending=False, na_position="last")
        )

    rename_map = {actual: requested
                  for actual, requested in zip(actual_group_cols, group_fields)
                  if actual != requested}
    if rename_map:
        grouped = grouped.rename(columns=rename_map)

    result = {
        "_result_type":  "grouped_data",
        "module_a":      module_a,
        "module_b":      module_b,
        "join_field":    join_field,
        "group_fields":  group_fields,
        "agg_field":     agg_field,
        "operation":     op,
        "matched_count": len(merged),
        "unique_groups": len(grouped),
        "total_records": len(merged),
        "groups":        _clean_records(grouped.to_dict(orient="records")),
    }
    if op not in ("COUNT", "COUNT_DISTINCT") and agg_field:
        actual_agg_col = resolve_column(merged, agg_field)
        if actual_agg_col:
            note = _sparsity_note(merged, actual_agg_col, agg_field)
            if note:
                result["_data_quality_note"] = note
    return result


# =============================================================================
# TOOL 7: get_record_fields
# =============================================================================
@tool
def get_record_fields(
    module: str,
    state: Annotated[dict, InjectedState()],
    fields: list | None = None,
    filters: list | None = None,
    limit: int = 0,
) -> dict:
    """
    Return the actual record data from a module.
    Use when the question asks for the details, attributes, or field values
    of specific records — not a count, sum, or aggregate.

    Args:
        module:  Data module name.
        fields:  Optional list of field names to include. If empty or None, returns all fields.
                 Use to return only the columns relevant to the question.
        filters: Optional list of {"field": str, "value": str} dicts for AND pre-filtering.
        limit:   Maximum number of records to return (default: 0 for no limit).
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {
            "_result_type": "record_set",
            "module": module, "filters": filters or [],
            "total": 0, "records": [], "fields_returned": [],
        }

    if filters:
        df, err = _safe_apply(df, filters)
        if err:
            # Fallback: if a filter field is missing from pre-fetched df (e.g. Analysis Agent omitted it from SQL SELECT),
            # re-fetch module data live via get_filtered_records to get the full record set.
            try:
                from app.api.advance.retrieval.retrieval import get_filtered_records
                mod_filters = {f['field']: f['value'] for f in filters if isinstance(f, dict) and 'field' in f and 'value' in f}
                api_res = get_filtered_records(
                    modules=[module],
                    filter_fields={module: {}},
                    filter_values={},
                    module_filter_values={module: mod_filters},
                    limit=limit
                )
                if api_res and api_res.get(module):
                    df_live = pd.DataFrame(api_res[module])
                    df_retry, err_retry = _safe_apply(df_live, filters)
                    if not err_retry:
                        df = df_retry
                        err = None
            except Exception as exc:
                import logging
                logging.getLogger("tools_basic").warning(f"Live fetch fallback failed in get_record_fields: {exc}")
        if err:
            return err

    if isinstance(fields, str):
        fields = [f.strip() for f in fields.split(",") if f.strip()]

    data_quality_notes: list[str] = []
    if fields:
        # Strict: reject any requested fields that cannot be resolved
        resolved_map = {f: resolve_column(df, f) for f in fields}
        invalid_fields = [f for f, col in resolved_map.items() if col is None]
        if invalid_fields:
            return _err(
                f"Requested field(s) {invalid_fields} not found in '{module}'. "
                f"Available: {sorted(df.columns.tolist())}"
            )
        # Flag any explicitly requested field that's mostly blank in the matched
        # rows — the records are still returned as-is, but the caller (and the
        # final answer) should not treat that field as a reliable identifier.
        for requested_name, actual_col in resolved_map.items():
            note = _sparsity_note(df, actual_col, requested_name)
            if note:
                data_quality_notes.append(note)
        df = df[[col for col in resolved_map.values()]]

    internal_fields = ["user_id", "user_name", "created_at", "updated_at", "_matched_fields"]
    cols_to_drop = [c for c in internal_fields if c in df.columns]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 0
    if limit > 0:
        df = df.head(limit)

    result = {
        "_result_type":    "record_set",
        "module":          module,
        "filters":         filters or [],
        "total":           len(df),
        "fields_returned": list(df.columns),
        "records":         _clean_records(df.to_dict(orient="records")),
    }
    if data_quality_notes:
        result["_data_quality_note"] = " ".join(data_quality_notes)
    return result


# =============================================================================
# TOOL 7b: filter_by_prior_results
# =============================================================================
@tool
def filter_by_prior_results(
    module: str,
    match_field: str,
    match_values: list,
    state: Annotated[dict, InjectedState()],
    fields: list | None = None,
    limit: int = 0,
    filters: list | None = None,
) -> dict:
    """
    Filter a module's records to only those where match_field's value appears
    in match_values (a list from a prior step).

    Use when you need to cross-reference results from one step against another
    module. For example: get asset details for AssetTagNos that were flagged
    by flag_by_threshold in a prior step.

    match_values should be a $step_N reference that resolves to a list,
    e.g. $step_1.flagged_records  or  $step_2.groups

    If match_values is a list of dicts, the tool extracts match_field values
    from each dict automatically.

    Args:
        module:       Target data module name (e.g. "assets")
        match_field:  Column in target module to match against (e.g. "AssetTagNo")
        match_values: List of values or list of dicts from a prior step
        fields:       Optional list of column names to return. Empty = all columns.
        limit:        Maximum number of records to return (default: 0 for no limit).
        filters:      Optional list of {"field": str, "value": str} dicts for AND pre-filtering
    """
    df = load_records_as_dataframe(state, module)
    if df.empty:
        return {
            "_result_type": "record_set",
            "module": module, "match_field": match_field,
            "total": 0, "matched": 0, "records": [], "fields_returned": [],
        }

    if filters:
        df, err = _safe_apply(df, filters)
        if err:
            return err

    if not match_values:
        return {
            "_result_type": "record_set",
            "module": module, "match_field": match_field,
            "total": len(df), "matched": 0, "records": [], "fields_returned": [],
        }

    clean_target = match_field.split(".")[-1].strip().lower()
    # If match_values is a list of dicts, extract the match_field value from each
    if isinstance(match_values, list) and len(match_values) > 0 and isinstance(match_values[0], dict):
        extracted = set()
        for row in match_values:
            for k, v in row.items():
                clean_k = k.split(".")[-1].strip().lower()
                if (clean_k == clean_target or clean_k.startswith(clean_target) or clean_target.startswith(clean_k)) and v is not None and str(v).strip():
                    extracted.add(str(v).strip().lower())
                    break
        values_set = extracted
    elif isinstance(match_values, list):
        values_set = {str(v).strip().lower() for v in match_values if v is not None}
    else:
        values_set = {str(match_values).strip().lower()}

    if not values_set:
        return {
            "_result_type": "record_set",
            "module": module, "match_field": match_field,
            "total": len(df), "matched": 0, "records": [], "fields_returned": [],
        }

    actual_col = resolve_column(df, match_field)
    if actual_col is None:
        return _err(
            f"match_field '{match_field}' not found in '{module}'. "
            f"Available: {sorted(df.columns.tolist())}"
        )

    col_lower = df[actual_col].fillna("").astype(str).str.strip().str.lower()
    df_filtered = df[col_lower.isin(values_set)]

    found_values = set(df_filtered[actual_col].fillna("").astype(str).str.strip().str.lower())
    
    if found_values != values_set:
        # We missed some matches in memory, likely due to DB limit truncation.
        # Fallback to a live targeted API fetch.
        try:
            from app.api.advance.retrieval.retrieval import get_filtered_records
            import pandas as pd
            
            mod_filters = {f['field']: f['value'] for f in (filters or [])}
            api_res = get_filtered_records(
                modules=[module],
                filter_fields={module: {}},
                filter_values={match_field: list(values_set)},
                module_filter_values={module: mod_filters},
                limit=limit
            )
            if api_res and api_res.get(module):
                df_live = pd.DataFrame(api_res[module])
                live_col = resolve_column(df_live, match_field)
                if live_col:
                    col_lower_live = df_live[live_col].fillna("").astype(str).str.strip().str.lower()
                    df_live = df_live[col_lower_live.isin(values_set)]
                df = df_live
            else:
                df = df_filtered
        except Exception as e:
            import logging
            logging.getLogger("tools_basic").warning(f"Live fetch failed in filter_by_prior_results: {e}")
            df = df_filtered
    else:
        df = df_filtered

    if isinstance(fields, str):
        fields = [f.strip() for f in fields.split(",") if f.strip()]

    if fields:
        resolved_map = {f: resolve_column(df, f) for f in fields}
        invalid_fields = [f for f, col in resolved_map.items() if col is None]
        if invalid_fields:
            return _err(
                f"Requested field(s) {invalid_fields} not found in '{module}'. "
                f"Available: {sorted(df.columns.tolist())}"
            )
        df = df[[col for col in resolved_map.values()]]

    internal_fields = ["user_id", "user_name", "created_at", "updated_at", "_matched_fields"]
    cols_to_drop = [c for c in internal_fields if c in df.columns]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 0   # unparseable limit → no cap, return all matched records
    if limit > 0:
        df = df.head(limit)

    return {
        "_result_type":    "record_set",
        "module":          module,
        "match_field":     match_field,
        "total":           len(df),
        "matched":         len(df),
        "fields_returned": list(df.columns),
        "records":         _clean_records(df.to_dict(orient="records")),
    }


# =============================================================================
# TOOL 7c: intersect_record_sets
# =============================================================================
@tool
def intersect_record_sets(
    datasets: list,
    match_field: str,
) -> dict:
    """
    Find common values of match_field across multiple list datasets from prior steps.

    Use when a question requires satisfying MULTIPLE criteria across different modules/steps.
    For example: find equipment/assets present in BOTH $step_1.flagged_records (BDM > 3)
    AND $step_2.flagged_records (FA > 2).

    Args:
        datasets:    List of $step_N references to lists of dicts or lists of values.
        match_field: Column name to intersect on (e.g. "AssetTagNo").

    Returns:
        matched_values: List of string values present in ALL datasets.
        count:          Number of intersected unique values.
    """
    if not datasets or not isinstance(datasets, list):
        return {
            "_result_type": "record_set",
            "match_field": match_field,
            "matched_values": [],
            "count": 0,
        }

    clean_target = match_field.split(".")[-1].strip().lower()
    sets_to_intersect = []
    original_format = {}
    for d in datasets:
        if not d or not isinstance(d, list):
            continue
        curr_set = set()
        if len(d) > 0 and isinstance(d[0], dict):
            for row in d:
                matched_val = None
                for k, v in row.items():
                    clean_k = k.split(".")[-1].strip().lower()
                    if clean_k == clean_target or clean_k.startswith(clean_target) or clean_target.startswith(clean_k):
                        if v is not None and str(v).strip():
                            matched_val = str(v).strip()
                            break
                if matched_val is not None:
                    norm = " ".join(matched_val.lower().split())
                    curr_set.add(norm)
                    if norm not in original_format:
                        original_format[norm] = matched_val
        else:
            for item in d:
                if item is not None and str(item).strip():
                    val = str(item).strip()
                    norm = " ".join(val.lower().split())
                    curr_set.add(norm)
                    if norm not in original_format:
                        original_format[norm] = val
        sets_to_intersect.append(curr_set)

    if not sets_to_intersect:
        return {
            "_result_type": "record_set",
            "match_field": match_field,
            "matched_values": [],
            "count": 0,
        }

    # Intersect all sets
    intersection = sets_to_intersect[0]
    for s in sets_to_intersect[1:]:
        intersection = intersection.intersection(s)

    matched_list = [original_format[k] for k in sorted(list(intersection)) if k in original_format]
    return {
        "_result_type": "record_set",
        "match_field": match_field,
        "matched_values": matched_list,
        "count": len(matched_list),
    }



# =============================================================================
# TOOL 8: do_math
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
    DIV by zero returns null safely. SQRT and ABS use only a.

    a and b must be resolved numbers. Do NOT pass unresolved $step_N references.
    However, a and b CAN be nested operation dicts with keys {operator, a, b}
    for inline chained math (e.g. {"operator": "DIV", "a": 636, "b": 1537}).

    Args:
        operation: ADD | SUB | MUL | DIV | MOD | POWER | SQRT | ABS
        a:         First number or nested operation dict.
        b:         Second number or nested operation dict. Default 0.
    """
    # Strict unresolved reference check
    if _is_unresolved_ref(a):
        return _err(f"Argument 'a' is an unresolved reference: '{a}'. The queue runner must resolve $step_N refs before calling do_math.")
    if _is_unresolved_ref(b):
        return _err(f"Argument 'b' is an unresolved reference: '{b}'. The queue runner must resolve $step_N refs before calling do_math.")

    def _resolve_nested(v, name: str):
        """If v is a nested operation dict like {'operator': 'DIV', 'a': 636, 'b': 1537},
        evaluate it recursively and return the scalar result."""
        if not isinstance(v, dict):
            return v, None
        op_key = v.get("operator") or v.get("operation")
        if not op_key:
            return None, _err(f"Argument '{name}' is a dict but has no 'operator'/'operation' key: {v!r}")
        fn = getattr(do_math, "func", do_math)
        nested = fn(operation=op_key, a=v.get("a", 0), b=v.get("b", 0))
        if nested.get("_result_type") == "error":
            return None, nested
        result = nested.get("result")
        if result is None:
            return None, _err(f"Nested operation for '{name}' returned None (possible DIV by zero).")
        return result, None

    a, a_nested_err = _resolve_nested(a, "a")
    if a_nested_err:
        return a_nested_err
    b, b_nested_err = _resolve_nested(b, "b")
    if b_nested_err:
        return b_nested_err

    # Strict numeric conversion — no silent 0.0 fallback
    def _to_float(v, name: str):
        if v is None:
            return None, None
        try:
            return float(v), None
        except (TypeError, ValueError):
            return None, _err(f"Argument '{name}' cannot be converted to a number: {v!r}")

    a_val, a_err = _to_float(a, "a")
    if a_err:
        return a_err

    b_val, b_err = _to_float(b, "b")
    if b_err:
        return b_err

    if a_val is None:
        return {
            "_result_type": "single_number",
            "operation":    operation.upper() if isinstance(operation, str) else str(operation),
            "a":            None,
            "b":            b_val,
            "result":       None,
            "_note":        "Argument 'a' is None — cannot perform arithmetic. Result set to None.",
        }

    op = operation.upper()

    # Validate BEFORE computing: for every operation that has real inputs but no
    # valid real-number result, say so explicitly instead of quietly returning a
    # bare `result: None` (or, for POWER, a `complex` object that would otherwise
    # crash later at JSON serialization — far from where the real problem is).
    _undefined_reason = None
    if op in ("DIV", "MOD") and b_val == 0:
        _undefined_reason = f"{op} by zero is undefined — cannot compute."
    elif op == "SQRT" and a_val < 0:
        _undefined_reason = "SQRT of a negative number has no real-number result — cannot compute."
    elif op == "POWER" and a_val < 0 and not float(b_val).is_integer():
        _undefined_reason = ("POWER of a negative base with a fractional exponent has no "
                              "real-number result — cannot compute.")

    if _undefined_reason:
        return {
            "_result_type": "single_number",
            "operation":    op,
            "a":            a_val,
            "b":            b_val,
            "result":       None,
            "_note":        _undefined_reason,
        }

    try:
        if   op == "ADD":   result = a_val + b_val
        elif op == "SUB":   result = a_val - b_val
        elif op == "MUL":   result = a_val * b_val
        elif op == "DIV":   result = a_val / b_val
        elif op == "MOD":   result = a_val % b_val
        elif op == "POWER": result = a_val ** b_val
        elif op == "SQRT":  result = math.sqrt(a_val)
        elif op == "ABS":   result = abs(a_val)
        else:
            return _err(f"Unknown operation '{op}'. Valid: ADD SUB MUL DIV MOD POWER SQRT ABS")
    except Exception as exc:
        return _err(str(exc))

    return {
        "_result_type": "single_number",
        "operation":    op,
        "a":            a_val,
        "b":            b_val,
        "result":       round(result, 6) if isinstance(result, float) else result,
    }


# =============================================================================
# TOOL 9: sort_and_limit
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
    calculate_mtbf, merge_and_score, or similar tools that return lists.

    data must be a $step_N.key reference that resolves to a list.
    order DESC = highest first, ASC = lowest first. limit 0 means keep all.

    Args:
        data:    The list to sort — MUST be a $step_N.key ref pointing to a list.
        sort_by: Field name to sort by (for lists of dicts). Leave empty to skip sort.
        order:   "DESC" (highest first) or "ASC" (lowest first). Default: "DESC".
        limit:   Keep only the first N items after sorting. 0 = keep all.
    """
    if _is_unresolved_ref(data):
        return _err(f"'data' is an unresolved reference: '{data}'.")
    if not isinstance(data, list):
        return _err(f"'data' must be a list, got {type(data).__name__}")

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 0

    if not data:
        return {
            "_result_type": "ranked_list",
            "sorted_data": [], "total_in": 0, "total_out": 0,
            "sort_by": sort_by, "order": order.upper(), "limit": limit,
        }

    ascending = order.upper() == "ASC"

    try:
        if isinstance(data[0], dict):
            if sort_by:
                df_sort = pd.DataFrame(data)
                if sort_by not in df_sort.columns:
                    return _err(
                        f"sort_by field '{sort_by}' not found in list items. "
                        f"Available keys: {sorted(df_sort.columns.tolist())}"
                    )
                col = df_sort[sort_by]
                numeric_col = pd.to_numeric(col, errors="coerce")
                # Only use numeric sort if ALL non-null values parsed successfully
                if numeric_col.notna().sum() == col.notna().sum():
                    df_sort[sort_by] = numeric_col
                df_sort = df_sort.sort_values(sort_by, ascending=ascending, na_position="last")
                sorted_data = _clean_records(df_sort.to_dict(orient="records"))
            else:
                sorted_data = list(data)
        else:
            # Scalar list — sort numerics as floats, strings as strings, never mix
            is_numeric = all(
                isinstance(v, (int, float)) or
                (isinstance(v, str) and v.replace(".", "", 1).lstrip("-").isdigit())
                for v in data if v is not None
            )
            if is_numeric:
                def _num_key(v):
                    return (1, 0.0) if v is None else (0, float(v))
                sorted_data = sorted(data, key=_num_key, reverse=not ascending)
            else:
                def _str_key(v):
                    return (1, "") if v is None else (0, str(v).lower())
                sorted_data = sorted(data, key=_str_key, reverse=not ascending)

    except Exception as exc:
        return _err(f"Sort failed: {exc}")

    if limit and limit > 0:
        sorted_data = sorted_data[:limit]

    return {
        "_result_type": "ranked_list",
        "sorted_data":  sorted_data,
        "total_in":     len(data),
        "total_out":    len(sorted_data),
        "sort_by":      sort_by,
        "order":        order.upper(),
        "limit":        limit,
    }


# =============================================================================
# TOOL 10: final_answer_tool
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
    # Guard: if result_ref is still an unresolved reference, execution failed
    def _contains_unresolved(val) -> bool:
        if _is_unresolved_ref(val):
            return True
        if isinstance(val, dict):
            return any(_contains_unresolved(v) for v in val.values())
        if isinstance(val, list):
            return any(_contains_unresolved(v) for v in val)
        return False

    if _contains_unresolved(result_ref):
        return _err(
            f"final_answer_tool received an unresolved reference: {result_ref!r}. "
            f"One or more execution steps failed to produce a result."
        )

    return {
        "_result_type": "final_answer",
        "status":       "complete",
        "final_value":  result_ref,
    }