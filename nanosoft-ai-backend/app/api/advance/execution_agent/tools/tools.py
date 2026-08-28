"""
FM Analytics Tools — Registry

Re-exports every tool. queue_runner.py imports directly from here to build
TOOL_REGISTRY. Tool implementations live in:

  tool_helpers.py     — shared internal helpers (not tools)
  tools_basic.py     — Tools 1–12  (count, sum, avg, group, math, records, sort, final_answer)
  tools_advanced.py  — Tools 13–20 (age, MTBF, time-period, threshold, rate,
                                     percentile, forecast, date-compare,
                                     merge-score, duration-add, date-diff)
"""

# ── Basic Tools ────────────────────────────────────────────────────────────────
from app.api.advance.execution_agent.tools.tools_basic import (        # noqa: F401
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
    combine_grouped_values,
    sort_and_limit,
    final_answer_tool,
)

# ── Intelligence Tools ─────────────────────────────────────────────────────────
from app.api.advance.execution_agent.tools.tools_advanced import (     # noqa: F401
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