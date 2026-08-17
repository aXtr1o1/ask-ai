"""
FM Analytics Tools — Registry

Re-exports every tool and assembles ALL_TOOLS for the planner.
Tool implementations live in:

  _helpers.py        — shared internal helpers (not tools)
  tools_basic.py     — Tools 1–12  (count, sum, avg, group, math, records, sort, final_answer)
  tools_advanced.py  — Tools 13–20 (age, MTBF, time-period, threshold, rate,
                                     percentile, forecast, date-compare,
                                     merge-score, duration-add, date-diff)
"""

# ── Basic Tools ────────────────────────────────────────────────────────────────
from app.api.advance.execution_agent.tools_basic import (        # noqa: F401
    count_records,
    sum_values,
    get_average,
    group_by_and_count,
    group_by_and_aggregate,
    join_and_aggregate,
    get_record_fields,
    filter_by_prior_results,
    intersect_record_sets,
    do_math,
    sort_and_limit,
    final_answer_tool,
)

# ── Intelligence Tools ─────────────────────────────────────────────────────────
from app.api.advance.execution_agent.tools_advanced import (     # noqa: F401
    calculate_age_from_now,
    group_by_time_period,
    calculate_mtbf,
    flag_by_threshold,
    calculate_rate_of_change,
    calculate_percentile,
    forecast_linear,
    compare_date_fields,
    merge_and_score,
    add_duration_to_date,
    join_and_filter_by_date_diff,
    calculate_date_difference_stats,
)

# =============================================================================
# ALL_TOOLS — used by the planner prompt for tool descriptions
# =============================================================================
ALL_TOOLS = [
    # Basic Tools
    count_records,
    sum_values,
    get_average,
    group_by_and_count,
    group_by_and_aggregate,
    join_and_aggregate,
    get_record_fields,
    filter_by_prior_results,
    intersect_record_sets,
    do_math,
    sort_and_limit,
    final_answer_tool,
    # Intelligence Tools
    calculate_age_from_now,
    group_by_time_period,
    calculate_mtbf,
    flag_by_threshold,
    calculate_rate_of_change,
    calculate_percentile,
    forecast_linear,
    compare_date_fields,
    merge_and_score,
    add_duration_to_date,
    join_and_filter_by_date_diff,
    calculate_date_difference_stats,
]