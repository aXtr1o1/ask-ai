"""
Execution Agent — Tool Metadata

Four exports live here:

  TOOL_OUTPUT_KEYS
      Guaranteed return keys of each tool on success.
      Used by _validate_queue and to generate the prompt's Tool API Reference.

  REQUIRED_ARGS
      Minimum arguments each tool must receive.
      Used by _validate_queue and to generate the prompt's Tool API Reference.

  OPTIONAL_ARGS
      Additional optional arguments each tool accepts.
      Used only for prompt generation — not validated at runtime.

  EXECUTION_REASONING_CONTEXT
      Plain-text dependency-reasoning block injected into the Planner prompt.
      Documents the exact output state of every tool so the LLM can reason
      about data availability across steps.

All three registries feed build_tool_api_block(), which generates the Tool API
Reference section injected into the Planner prompt. This means the prompt never
needs to be updated when a tool signature changes — only this file does.

Keep all three in sync with the actual tool implementations in tools.py.
"""


# =============================================================================
# TOOL OUTPUT KEYS
# Keys each tool is guaranteed to return on a successful call.
# =============================================================================
TOOL_OUTPUT_KEYS: dict[str, set[str]] = {
    # ── Basic Tools ─────────────────────────────────────────────────────────────
    "count_records":          {"count", "module", "condition_field", "condition_value",
                               "conditions"},
    "sum_values":             {"total_sum", "records_used", "module", "field", "filters"},
    "get_average":            {"average", "records_used", "module", "field", "filters"},
    "group_by_and_count":     {"groups", "total_records", "unique_groups",
                               "module", "group_fields", "filters",
                               "count", "total"},
    "group_by_and_aggregate": {"groups", "total_records", "unique_groups",
                               "module", "group_fields", "agg_field", "operation", "filters",
                               "count", "total", "value"},
    "join_and_aggregate":     {"groups", "matched_count", "unique_groups", "total_records",
                               "module_a", "module_b", "join_field",
                               "group_fields", "agg_field", "operation"},
    "get_record_fields":      {"module", "total", "fields_returned", "records", "filters"},
    "filter_by_prior_results": {"module", "match_field", "total", "matched",
                                "fields_returned", "records"},
    "intersect_record_sets":  {"match_field", "matched_values", "count"},
    "do_math":                {"result", "operation", "a", "b"},
    "sort_and_limit":         {"sorted_data", "total_in", "total_out",
                               "sort_by", "order", "limit"},
    "final_answer_tool":      {"status", "final_value"},
    # ── Intelligence Tools ───────────────────────────────────────────────────
    "calculate_age_from_now": {"avg_age_days", "max_age_days", "min_age_days",
                               "total_records", "calculated", "groups",
                               "module", "date_field", "group_fields", "filters"},
    "group_by_time_period":   {"periods", "total_records", "period_count",
                               "value_key", "module", "date_field", "period",
                               "operation", "agg_field", "filters"},
    "calculate_mtbf":         {"mtbf_by_asset", "overall_avg_mtbf_days",
                               "assets_analyzed", "total_records",
                               "module", "asset_field", "failure_date_field", "filters"},
    "flag_by_threshold":      {"flagged_count", "total_records", "flag_ratio",
                               "flagged_records", "groups",
                               "module", "field", "threshold", "operator",
                               "group_fields", "filters"},
    "calculate_rate_of_change": {"pct_change", "direction", "a", "b"},
    "calculate_percentile":   {"percentile_values", "mean", "std_dev", "minimum", "maximum",
                               "records_used", "module", "field", "filters"},
    "forecast_linear":        {"forecast", "model_slope", "model_intercept",
                               "r_squared", "periods_ahead", "data_points",
                               "value_key", "last_known_label"},
    "compare_date_fields":    {"flagged_count", "total_records", "flag_ratio",
                               "valid_pairs", "flagged_records", "groups",
                               "module", "field_a", "field_b", "operator",
                               "group_fields", "filters"},
    "merge_and_score":        {"ranked", "group_key", "datasets_used", "total_groups"},
    "add_duration_to_date":   {"records", "total", "expired_count",
                               "module", "date_field", "duration_field",
                               "duration_unit", "filters"},
    "join_and_filter_by_date_diff": {"matched_records", "matched_count", "total_joined",
                                     "module_a", "module_b", "join_field",
                                     "date_field_a", "date_field_b",
                                     "operator", "threshold_days",
                                     "filters_a", "filters_b"},
    "calculate_date_difference_stats": {"module", "start_date_field", "end_date_field", "filters",
                                        "total_records", "calculated", "avg_diff_days",
                                        "max_diff_days", "min_diff_days", "groups"},
}


# TOOL LIST OUTPUT SCHEMA
TOOL_LIST_OUTPUT_SCHEMA: dict[str, dict[str, dict]] = {
    "group_by_and_count":     {"groups": {"group_arg": "group_fields", "extra": ["count"]}},
    "group_by_and_aggregate": {"groups": {"group_arg": "group_fields", "extra": ["value"]}},
    "join_and_aggregate":     {"groups": {"group_arg": "group_fields", "extra": ["value"]}},
    "calculate_age_from_now": {"groups": {"group_arg": "group_fields",
                                          "extra": ["avg_age_days", "max_age_days", "record_count"]}},
    "flag_by_threshold": {
        "groups":          {"group_arg": "group_fields",
                            "extra": ["flagged_count", "total", "flag_ratio"]},
        "flagged_records": {"label_and_scalar": ("label_field", "field")},
    },
    "compare_date_fields": {
        "groups":          {"group_arg": "group_fields",
                            "extra": ["flagged_count", "total", "flag_ratio"]},
        "flagged_records": {"module_arg": "module", "extra": ["day_diff"]},
    },
    "calculate_date_difference_stats": {
        "groups": {"group_arg": "group_fields",
                  "extra": ["records", "avg_diff_days", "max_diff_days", "min_diff_days"]},
    },
    "group_by_time_period": {
        "periods": {"fixed": ["period_label", "count", "value"]},
    },
    "calculate_mtbf": {
        "mtbf_by_asset": {"scalar_arg": "asset_field", "extra": ["failure_count", "mtbf_days"]},
    },
    "forecast_linear": {
        "forecast": {"scalar_arg": "label_key", "default": "period_label", "extra": ["predicted_value"]},
    },
    "get_record_fields":       {"records": {"list_arg": "fields"}},
    "filter_by_prior_results": {"records": {"list_arg": "fields"}},
    "join_and_filter_by_date_diff": {
        "matched_records": {"list_arg": "fields", "always": ["day_diff"]},
    },
    "add_duration_to_date": {
        "records": {"module_arg": "module", "extra": ["expected_end_date", "days_remaining"]},
    },
    "sort_and_limit": {
        "sorted_data": {"passthrough_arg": "data"},
    },
    "merge_and_score": {
        "ranked": {"dynamic_merge_score": True},
    },
}


# =============================================================================
# REQUIRED ARGS
# The minimum arguments each tool must receive for _validate_queue to pass.
# =============================================================================
REQUIRED_ARGS: dict[str, list[str]] = {
    # ── Basic Tools ─────────────────────────────────────────────────────────────
    "count_records":             ["module"],
    "sum_values":                ["module", "field"],
    "get_average":               ["module", "field"],
    "group_by_and_count":        ["module", "group_fields"],
    "group_by_and_aggregate":    ["module", "group_fields", "agg_field", "operation"],
    "join_and_aggregate":        ["module_a", "module_b", "join_field",
                                  "group_fields", "agg_field", "operation"],
    "get_record_fields":         ["module"],
    "filter_by_prior_results":   ["module", "match_field", "match_values"],
    "intersect_record_sets":     ["datasets", "match_field"],
    "sort_and_limit":            ["data"],
    "do_math":                   ["operation", "a"],
    "final_answer_tool":         ["result_ref"],
    # ── Intelligence Tools ───────────────────────────────────────────────────
    "calculate_age_from_now":    ["module", "date_field"],
    "group_by_time_period":      ["module", "date_field"],
    "calculate_mtbf":            ["module", "asset_field", "failure_date_field"],
    "flag_by_threshold":         ["module", "field", "threshold"],
    "calculate_rate_of_change":  ["a", "b"],
    "calculate_percentile":      ["module", "field"],
    "forecast_linear":           ["data"],
    "compare_date_fields":       ["module", "field_a", "field_b", "operator"],
    "merge_and_score":           ["datasets", "group_key"],
    "add_duration_to_date":      ["module", "date_field", "duration_field"],
    "join_and_filter_by_date_diff": ["module_a", "module_b", "join_field",
                                     "date_field_a", "date_field_b",
                                     "operator", "threshold_days"],
    "calculate_date_difference_stats": ["module", "start_date_field", "end_date_field"],
}


# =============================================================================
# OPTIONAL ARGS
# Additional optional arguments each tool accepts (for prompt generation only).
# =============================================================================
OPTIONAL_ARGS: dict[str, list[str]] = {
    # ── Basic Tools ─────────────────────────────────────────────────────────────
    "count_records":             ["condition_field", "condition_value", "conditions"],
    "sum_values":                ["filters"],
    "get_average":               ["filters"],
    "group_by_and_count":        ["filters"],
    "group_by_and_aggregate":    ["filters", "data"],
    "join_and_aggregate":        ["filters_a", "filters_b"],
    "get_record_fields":         ["fields", "filters", "limit"],
    "filter_by_prior_results":   ["fields", "limit", "filters"],
    "intersect_record_sets":     [],
    "do_math":                   ["b"],
    "sort_and_limit":            ["sort_by", "order", "limit"],
    "final_answer_tool":         [],
    # ── Intelligence Tools ───────────────────────────────────────────────────
    "calculate_age_from_now":    ["group_fields", "filters"],
    "group_by_time_period":      ["period", "agg_field", "operation", "filters"],
    "calculate_mtbf":            ["filters"],
    "flag_by_threshold":         ["operator", "group_fields", "label_field", "filters", "data"],
    "calculate_rate_of_change":  [],
    "calculate_percentile":      ["percentiles", "filters"],
    "forecast_linear":           ["periods_ahead", "value_key", "label_key"],
    "compare_date_fields":       ["group_fields", "filters"],
    "merge_and_score":           [],
    "add_duration_to_date":      ["duration_unit", "filters"],
    "join_and_filter_by_date_diff": ["fields", "filters_a", "filters_b"],
    "calculate_date_difference_stats": ["group_fields", "filters"],
}


# =============================================================================
# BUILD TOOL API BLOCK
# Generates the Tool API Reference section injected into the Planner prompt.
# Format per tool:
#   tool_name
#     Required : arg1, arg2
#     Optional : arg3, arg4
#     Returns  : key1, key2, key3
# =============================================================================
_DASH = "─" * 59

def build_tool_api_block() -> str:
    """Generate the complete Tool API Reference from the three registries."""
    lines = [
        "━" * 59,
        "TOOL API REFERENCE",
        "━" * 59,
        "",
        "BASIC TOOLS",
        _DASH,
        "",
    ]

    basic = [
        "count_records", "sum_values", "get_average",
        "group_by_and_count", "group_by_and_aggregate", "join_and_aggregate",
        "get_record_fields", "filter_by_prior_results", "intersect_record_sets",
        "do_math", "sort_and_limit", "final_answer_tool",
    ]
    intelligence = [
        "calculate_age_from_now", "group_by_time_period", "calculate_mtbf",
        "flag_by_threshold", "calculate_rate_of_change", "calculate_percentile",
        "forecast_linear", "compare_date_fields", "merge_and_score",
        "add_duration_to_date", "join_and_filter_by_date_diff",
        "calculate_date_difference_stats",
    ]

    def _describe_list_fields(spec: dict) -> str:
        """Render, generically, which fields a list-valued output actually
        carries — <argname> stands for "whatever value this step's own arg
        of that name holds", never a hardcoded field name.
        """
        if "fixed" in spec:
            return ", ".join(spec["fixed"])
        if "group_arg" in spec:
            base = f"<{spec['group_arg']}>"
            extra = spec.get("extra", [])
            return f"{base} + {', '.join(extra)}" if extra else base
        if "scalar_arg" in spec:
            base = f"<{spec['scalar_arg']}>"
            extra = spec.get("extra", [])
            return f"{base} + {', '.join(extra)}" if extra else base
        if "list_arg" in spec:
            base = f"exactly <{spec['list_arg']}>"
            always = spec.get("always", [])
            base = f"{base} + {', '.join(always)}" if always else base
            return f"{base} (every column of the source when left empty — not enumerable in advance)"
        if "module_arg" in spec:
            base = f"every field of <{spec['module_arg']}>"
            extra = spec.get("extra", [])
            return f"{base} + {', '.join(extra)}" if extra else base
        if "label_and_scalar" in spec:
            label_arg, scalar_arg = spec["label_and_scalar"]
            return (f"<{label_arg}>, <{scalar_arg}> when {label_arg} is given — "
                    f"otherwise every field of the source (not enumerable in advance)")
        if "passthrough_arg" in spec:
            return f"exactly the fields already present on whatever <{spec['passthrough_arg']}> points to"
        if spec.get("dynamic_merge_score"):
            return "<group_key> + one '<dataset label>_score' field per dataset + composite_score"
        return "(varies)"

    def _tool_block(name: str) -> list[str]:
        req = REQUIRED_ARGS.get(name, [])
        opt = OPTIONAL_ARGS.get(name, [])
        ret = sorted(TOOL_OUTPUT_KEYS.get(name, set()))
        block = [f"{name}"]
        if req:
            block.append(f"  Required : {', '.join(req)}")
        if opt:
            block.append(f"  Optional : {', '.join(opt)}")
        if ret:
            block.append(f"  Returns  : {', '.join(ret)}")
        for out_key, spec in TOOL_LIST_OUTPUT_SCHEMA.get(name, {}).items():
            block.append(f"  {out_key} fields : {_describe_list_fields(spec)}")
        block.append("")
        return block

    for name in basic:
        lines.extend(_tool_block(name))

    lines += ["", "INTELLIGENCE TOOLS", _DASH, ""]
    for name in intelligence:
        lines.extend(_tool_block(name))

    return "\n".join(lines)


# =============================================================================
# EXECUTION_REASONING_CONTEXT
# Plain-text dependency-reasoning block injected into the Planner prompt.
# Kept here so tool_meta.py is the single source of truth for all
# tool-level knowledge: metadata, API reference, and execution semantics.
# =============================================================================
EXECUTION_REASONING_CONTEXT = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXECUTION LOGIC & DEPENDENCY REASONING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Treat the execution queue as a dependency chain. Before finalising the queue,
validate every step against these rules. If any rule is violated, revise the
plan until all rules pass.

─────────────────────────────────────────────
1. DATA STATE AFTER EACH TOOL
─────────────────────────────────────────────
Every tool that transforms data changes the available column set and/or value
set for all subsequent steps. You MUST reason about the resulting data state,
not the original module structure. Below is the exact output state per tool.

BASIC TOOLS — output state

• count_records:
  Returns a single number in key "count". No columns or records survive.
  Reference as $step_N.count.

• sum_values:
  Returns a single number in key "total_sum". No columns or records survive.
  Reference as $step_N.total_sum.

• get_average:
  Returns a single number in key "average". No columns or records survive.
  Reference as $step_N.average.

• group_by_and_count:
  Returns "groups" — a list of dicts. Each dict contains only the specified
  group_fields columns plus a "count" key representing the count. Only the
  group_fields columns and "count" are available downstream. All other original
  module columns are dropped.
  Reference as $step_N.groups or $step_N.groups[i].count — never $step_N.groups[i].value.

• group_by_and_aggregate:
  Returns "groups" — a list of dicts. Each dict contains only the specified
  group_fields columns plus a "value" key representing the aggregated result.
  Only the group_fields columns and "value" are available downstream.
  Valid operations: SUM | AVG | MIN | MAX | COUNT | COUNT_DISTINCT.
  Never invent operations or use custom aggregation codes.
  By default reads directly from module. When group_fields or agg_field name a
  field that only exists on a prior step's own output (not on the original
  module), pass that step's list through the optional data argument instead —
  module is still required alongside it.
  Reference as $step_N.groups.

• join_and_aggregate:
  Inner-joins two modules on join_field, then groups and aggregates. The merged
  result is a FLAT table — column names are plain strings (e.g. "<field_name>").
  If both modules share a column name other than the join key, suffixes (_a / _b)
  are added automatically. Do NOT use "<module_name>.<field_name>" dotted syntax
  in group_fields or agg_field — only the plain flat column name is valid.
  Returns "groups" (list of dicts with group_fields + value).
  Reference as $step_N.groups.

• get_record_fields:
  Returns "records" — a list of dicts containing only the columns listed in the
  fields arg. Columns NOT in fields are dropped entirely.
  Reference as $step_N.records. Total count is in $step_N.total.

• filter_by_prior_results:
  Filters a module where match_field appears in a prior step's list.
  Returns "records" — only the columns in the fields arg survive.
  Reference as $step_N.records. Total count is in $step_N.total.

• intersect_record_sets:
  Returns "matched_values" (list of shared values across prior-step lists) and
  "count". Does NOT return records — only the intersection of values.
  Reference as $step_N.matched_values.

• do_math:
  Returns a single number in key "result". Operations: ADD | SUB | MUL | DIV |
  MOD | POWER | SQRT | ABS. Never write raw math in result_ref — use do_math.
  Reference as $step_N.result.

• sort_and_limit:
  Sorts and optionally limits a list from a prior step. Input "data" MUST be a
  $step_N.key reference to a list — never a module name or raw value.
  Returns "sorted_data". limit=0 keeps all records.
  Reference as $step_N.sorted_data.

• final_answer_tool:
  Always the LAST step. result_ref is its only argument — a single
  $step_N.key reference, or a dict of {label: $step_N.key} pairs.
  Never pass raw math or literal values inside result_ref.

INTELLIGENCE TOOLS — output state

• calculate_age_from_now:
  Returns overall stats: avg_age_days, max_age_days, min_age_days,
  total_records, calculated. Optionally returns "groups" (per-group breakdown).
  Internal computed columns are never exposed as output keys.
  Reference as $step_N.avg_age_days or $step_N.groups.

• calculate_date_difference_stats:
  Computes (end_date - start_date) in days per record. Returns avg_diff_days,
  max_diff_days, min_diff_days, total_records, calculated, and optionally
  "groups" (per-group breakdown if group_fields provided).
  Use for elapsed duration metrics (e.g. turnaround times, failure-to-resolution times).
  Do NOT use group_by_and_aggregate with custom operations — use this tool instead.
  Reference as $step_N.avg_diff_days or $step_N.groups.

• group_by_time_period:
  Groups records by time period (month | week | quarter | year). Returns
  "periods" — a list of dicts each with "period_label" and "count" or "value".
  Only period_label and count/value remain — no other original columns.
  This is the required and only valid input source for forecast_linear.
  Reference as $step_N.periods.

• calculate_mtbf:
  Returns "mtbf_by_asset" (list of per-asset dicts: asset, mtbf_days,
  failure_count) and "overall_avg_mtbf_days", "assets_analyzed", "total_records".
  Reference as $step_N.mtbf_by_asset or $step_N.overall_avg_mtbf_days.

• flag_by_threshold:
  Returns "flagged_records" (list of matching records with their original fields),
  "flagged_count", "total_records", "flag_ratio", and optionally "groups".
  Reference as $step_N.flagged_records or $step_N.flagged_count.

• calculate_rate_of_change:
  Returns "pct_change" (float) and "direction" (up | down | flat).
  Inputs a and b must be plain numbers or $step_N.key references to numbers.
  Reference as $step_N.pct_change or $step_N.direction.

• calculate_percentile:
  Returns "percentile_values" (dict), "mean", "std_dev", "minimum", "maximum",
  "records_used". Reference as $step_N.percentile_values or $step_N.mean.

• forecast_linear:
  Input "data" MUST be a $step_N.periods reference from group_by_time_period.
  No other list source is valid. value_key must match the column name in each
  period dict (either "count" or "value").
  Returns "forecast" (list of predicted future period dicts), "model_slope",
  "model_intercept", "r_squared". Reference as $step_N.forecast.

• compare_date_fields:
  Returns "flagged_records" (records where field_a OP field_b is true),
  "flagged_count", "flag_ratio", "valid_pairs", and optionally "groups".
  Computed internal datetime columns are not exposed.
  Reference as $step_N.flagged_count or $step_N.flagged_records.

• merge_and_score:
  Combines multiple prior-step group result lists into a composite ranked score.
  Each dataset entry needs: label, data ($step_N.key referencing a list),
  weight, value_key, lower_is_better. Returns "ranked" (sorted composite list)
  and "total_groups". Reference as $step_N.ranked.

• add_duration_to_date:
  Adds a duration_field to a date_field per record and computes days_remaining.
  Returns "records" (enriched with expected_end_date and days_remaining), "total",
  "expired_count" (days_remaining < 0). Reference as $step_N.records.

• join_and_filter_by_date_diff:
  Inner-joins two modules, computes day diff between one date from each module,
  filters records where that diff satisfies a threshold. The merged result is a
  FLAT table — do NOT use "<module_name>.<field_name>" dotted syntax in any arg.
  Returns "matched_records", "matched_count", "total_joined".
  Reference as $step_N.matched_records or $step_N.matched_count.

─────────────────────────────────────────────
2. $step_N REFERENCE VALIDITY
─────────────────────────────────────────────
• A step can only reference steps with a lower index (defined earlier).
• The key after $step_N must be listed in that tool's "Returns" in the
  Tool API Reference. Never reference a key that is not in Returns.
• When chaining steps, trace the data path:
    (a) What does step N output?
    (b) Which exact key do I need?
    (c) Does the next tool accept that structure as input?
  If any link is broken, revise the plan.

─────────────────────────────────────────────
3. JOIN KEY VALIDATION
─────────────────────────────────────────────
• Before planning a join, confirm the join_field exists in BOTH modules
  using the schema provided.
• If no shared key exists between the two modules, do not plan a join —
  use single-module tools or a different approach.

─────────────────────────────────────────────
4. EMPTY / MISSING RESULT HANDLING
─────────────────────────────────────────────
• If a step can legally produce an empty result (no records match the
  filter), a downstream step that depends on it may also fail. Prefer
  plans where missing data does not cascade into a total failure.
• Do not construct a plan where a known-optional module (one that may
  have no records) is a required upstream dependency for every branch.

─────────────────────────────────────────────
5. TOOL ARGUMENT TYPES
─────────────────────────────────────────────
• group_fields must always be a JSON array even for a single field:
    CORRECT: group_fields: ["<field_name>"]
    WRONG:   group_fields: "<field_name>"
• filters must always be a JSON array of {"field": str, "value": str} objects.
• operation must be one of the exact strings listed in the tool description.
  Never invent custom operation codes or attempt aggregation functions that
  are not explicitly supported by the respective tool's description.

─────────────────────────────────────────────
6. A STEP'S ARGUMENTS ARE EXACTLY WHAT ITS TOOL LISTS
─────────────────────────────────────────────
Each tool's Required and Optional lines in the Tool API Reference above are the
complete set of arguments that tool accepts — not a subset, not a starting
point. Two failure directions follow from this, and both are equally fatal to
the step:
  - Missing one of the Required arguments — checked whether or not the value
    seems implied by an earlier step, a filter, or data already passed through
    another arg.
  - Including an argument that isn't in that tool's own Required or Optional
    list at all — an argument that belongs to a different tool, even one used
    elsewhere in the same plan for a related purpose, is not recognized here
    just because the two tools appear together.
A step that fails either way is rejected before the queue runs at all — that
step never executes, and neither does anything after it.

─────────────────────────────────────────────
7. COMPUTED FIELDS EXIST ONLY WHERE THEY WERE COMPUTED
─────────────────────────────────────────────
Some tools add new fields to their own output records that were never part of
the original module — e.g. add_duration_to_date adds "days_remaining" and
"expected_end_date". A field like this exists only in the "records" (or
similar list key) of the step that produced it, never in the original module
data. Reading a module directly cannot see it there, so filtering, grouping,
or aggregating on it that way fails with "field not found" — check the
specific tool's own Optional list in the Tool API Reference above for a
"data" argument: where one exists, passing that step's own output list
through it is what keeps a computed field reachable once the step that
created it has run. Not every tool has this argument — go by what that
tool's own Required/Optional lists actually contain, not by what a similar
tool elsewhere in the reference accepts.

─────────────────────────────────────────────
8. THE PLAN IS PRODUCED ONCE
─────────────────────────────────────────────
You are called exactly once per question. Once the queue leaves you, execution
runs on its own with no further reasoning from you in the loop — nothing left
out of the plan gets added afterward, and nothing noticed partway through
execution gets corrected. A question can ask for more than one distinct thing
at once: a raw figure together with a rate, percentage, or share derived from
it; a value together with a comparison against something else; a result
together with a further calculation built on it. Each of those is a separate
thing the plan has to produce — not one thing with several ways of phrasing it.

─────────────────────────────────────────────
9. EACH STEP'S SCOPE IS ITS OWN
─────────────────────────────────────────────
A step reads directly from the original module data and applies only the
filters/group_fields/conditions given in that step. There is no shared,
running scope carried across the plan — a filter applied in one step has no
effect on what a later step sees when that later step reads from the same
module.

─────────────────────────────────────────────
10. A STEP'S OWN OUTPUT LIST MAY CARRY FEWER FIELDS THAN ITS SOURCE
─────────────────────────────────────────────
A field on the module a step reads from is not automatically part of that
step's own output — a narrowing tool's output is only its own group/key
fields plus the metric it computed, nothing else the source had. The Tool
API Reference above states exactly which fields each list output carries,
derived from that step's own args. When a later step reads a prior step's
list through a "data"-style argument, every field name it supplies must be
one this specific list actually carries — not assumed from the original
module. A field lost this way is still reachable: by matching records in a
module against a list of values carried over from a prior step; see the
tool described for that purpose above.

─────────────────────────────────────────────
11. THE SHORTEST VALID PLAN IS THE CORRECT ONE
─────────────────────────────────────────────
Once a step has produced a required metric or value, it stays available for
the rest of the plan through its own $step_N reference. Recomputing it again
— whether by rereading the original module or by any other path — does not
make the plan more thorough; it only adds a chain that has to be gotten right
a second time for no benefit. The correct plan is the shortest one that fully
answers the question: every step in it exists because something later in the
plan genuinely depends on it, not because a value could be produced again a
different way.
"""
