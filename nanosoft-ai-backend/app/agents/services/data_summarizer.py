"""
app/agents/services/data_summarizer.py
---------------------------------------
Smart data preparation for the Execution Agent.

PROBLEM THIS SOLVES:
  The Retrieval Agent can return 11,000+ raw records from the DB.
  Two naive approaches both fail:
    X  Truncate to 100 records  ->  model says "100 tasks" when there are 11,000  (WRONG count)
    X  Send all 11,000 rows     ->  token limit exceeded, API error

SOLUTION:
  - If total records <= SMALL_THRESHOLD (500) -> pass records as-is (fits in LLM context)
  - If total records >  SMALL_THRESHOLD       -> Python pre-aggregates into a compact
      statistical summary (group-by counts, numeric stats) PLUS a small representative sample.

  The LLM then writes a FULLY DETAILED and CORRECT answer from the summary
  because it has accurate counts/groups, not a truncated slice.

HOW FIELD CLASSIFICATION WORKS (fully data-driven, zero hardcoding):

  Instead of hardcoding field name keywords like "id", "uuid", "name" etc.
  (which breaks on real DB fields like "ppm_reference" or "contractor_code"),
  this module looks at the ACTUAL DATA VALUES of each field and decides:

    1. Is the field numeric?
         -> Look at what fraction of values are numbers.
         -> If >= 50% are numeric -> treat as numeric -> compute min/max/avg/sum.

    2. Is the field categorical (low cardinality)?
         -> Compute: unique_values / total_records  = uniqueness_ratio
         -> If ratio <  CARDINALITY_RATIO_THRESHOLD (5%) -> group-by it.
            e.g. "status" has 3 unique values out of 11,000 records = 0.03% -> group it
         -> If ratio >= CARDINALITY_RATIO_THRESHOLD          -> skip it.
            e.g. "task_id" has 11,000 unique values out of 11,000 = 100%  -> skip it

  WHY ratio-based (not a fixed count like 50):
    A fixed number like 50 makes no sense across different dataset sizes.
    50 unique values is 8% of 600 records  (fine to group)
    50 unique values is 0.5% of 11,000 records  (could still group)
    But a ratio of 5% is correct at ANY scale.

WHY PURE PYTHON (no LLM call here):
  Aggregation is deterministic math - counting, grouping, averaging.
  Using an LLM for this step would add latency and hallucination risk.
  Python is accurate and takes < 1ms for 11,000 records.

CALLED FROM:
  app/agents/execution_agent.py
  Replaces the naive p_list[:MAX_RECORDS] cap block.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("data_summarizer")


# ---- Thresholds (all data-driven, none are arbitrary name-based rules) -------

# Records below this count are passed to the LLM as-is without aggregation.
# After Filtering Agent, each record has ~3-8 fields.
# 500 records x 6 fields x ~15 chars = ~45,000 chars = ~11,000 tokens -- safe.
SMALL_THRESHOLD = 500

# When aggregating large datasets, keep this many raw records as a sample.
# WHY keep a sample: the LLM can cite concrete examples even when the full
# list is replaced by a summary. 20 records = ~600 tokens.
SAMPLE_SIZE = 20

# A field is considered "high cardinality" (skip group-by) when:
#   unique_values / total_records  >= this ratio.
#
# WHY 5% ratio instead of a fixed count like 50:
#   - For 600 records:    5% threshold = 30 unique values max -> group-by
#   - For 11,000 records: 5% threshold = 550 unique values max -> group-by
#   - For 11,000 records: "task_id" has 11,000 unique values = 100% -> skip
#   - For 11,000 records: "status" has 3 unique values = 0.03% -> group
#
# This is self-calibrating: it works correctly at any dataset size.
# No hardcoded keywords, no fixed counts -- purely based on actual data.
CARDINALITY_RATIO_THRESHOLD = 0.05  # 5%

# A field is treated as numeric when at least this fraction of its values
# are actual numbers (int or float). 50% allows for some nulls/mixed values.
NUMERIC_RATIO_THRESHOLD = 0.50  # 50%


# ---- Public API --------------------------------------------------------------

def smart_prepare(
    retrieval_results: List[Dict[str, Any]],
    understood_intent: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Main entry point -- called by execution_agent.py.

    Iterates over each retrieval step result and applies smart preparation:
      - Small datasets (<= SMALL_THRESHOLD records) -> passed through unchanged.
      - Large datasets (>  SMALL_THRESHOLD records) -> p_list replaced with a
        compact aggregated summary + SAMPLE_SIZE representative raw records.

    Args:
        retrieval_results:  Filtered retrieval results from state["filtered_results"].
        understood_intent:  Intent dict (reserved for future intent-aware aggregation).

    Returns:
        List of result dicts ready for JSON-serialisation into the LLM prompt.
        Large p_lists are replaced by compact summaries the LLM can reason over
        completely and accurately.
    """
    intent   = understood_intent or {}
    prepared = []
    for result in retrieval_results:
        prepared.append(_prepare_one_step(result, intent))
    return prepared


# ---- Per-step processing -----------------------------------------------------

def _prepare_one_step(
    result: Dict[str, Any],
    intent: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process a single retrieval result step.

    Handles both data shapes the pipeline produces:
      Shape A:  data = {"p_count": int, "p_list": [...records...]}
      Shape B:  data = [...records...]  (plain list)
    """
    new_result = dict(result)
    data       = result.get("data")

    # -- Shape A: data is a dict with p_count + p_list -------------------------
    if isinstance(data, dict):
        p_list = data.get("p_list") or []

        if isinstance(p_list, list) and len(p_list) > SMALL_THRESHOLD:
            new_data = {k: v for k, v in data.items() if k != "p_list"}
            summary  = _aggregate(p_list)
            sample   = p_list[:SAMPLE_SIZE]

            new_data["_note"] = (
                f"This dataset has {len(p_list):,} records -- too large to send raw to the LLM. "
                f"Python pre-aggregated the full list below for 100% accuracy. "
                f"A sample of {len(sample)} records is also provided as concrete examples."
            )
            new_data["_aggregated"]    = True
            new_data["_total_records"] = len(p_list)
            new_data["_summary"]       = summary
            new_data["p_list_sample"]  = sample
            new_result["data"]         = new_data

            logger.info(
                "|| [DataSummarizer] step=%s | %d records -> aggregated summary + %d-record sample",
                result.get("step_id", "?"), len(p_list), len(sample),
            )
        else:
            logger.info(
                "|| [DataSummarizer] step=%s | %d records <= threshold=%d -> pass-through",
                result.get("step_id", "?"),
                len(p_list) if isinstance(p_list, list) else 0,
                SMALL_THRESHOLD,
            )

    # -- Shape B: data is a plain list -----------------------------------------
    elif isinstance(data, list) and len(data) > SMALL_THRESHOLD:
        summary = _aggregate(data)
        sample  = data[:SAMPLE_SIZE]
        new_result["data"] = {
            "_note": (
                f"This dataset has {len(data):,} records -- too large to send raw to the LLM. "
                f"Python pre-aggregated the full list below for 100% accuracy. "
                f"A sample of {len(sample)} records is also provided as concrete examples."
            ),
            "_aggregated":    True,
            "_total_records": len(data),
            "_summary":       summary,
            "sample":         sample,
        }
        logger.info(
            "|| [DataSummarizer] step=%s | %d records (list) -> aggregated",
            result.get("step_id", "?"), len(data),
        )

    return new_result


# ---- Core aggregation engine (fully data-driven) -----------------------------

def _aggregate(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute a compact statistical summary from a list of records.

    For each field, this function looks at the ACTUAL DATA VALUES
    (not the field name) to decide what kind of field it is:

    Step 1 -- Numeric check:
      Count how many values in this field are numbers (int/float).
      If >= NUMERIC_RATIO_THRESHOLD (50%) of values are numeric
         -> treat as a numeric field -> compute min, max, avg, sum.

    Step 2 -- Cardinality check:
      Compute uniqueness_ratio = unique_values / total_records
      If uniqueness_ratio <  CARDINALITY_RATIO_THRESHOLD (5%)
         -> low cardinality -> this is a categorical field -> group-by counts
      If uniqueness_ratio >= CARDINALITY_RATIO_THRESHOLD (5%)
         -> high cardinality -> this is an identifier/free-text field -> skip

    WHY this is better than hardcoded keyword lists:
      A field called "ppm_reference" would be skipped by a keyword rule ("ref").
      But if it has only 5 unique values in 11,000 records (0.05%), this
      data-driven approach correctly identifies it as categorical and groups it.

      A field called "building_zone" would NOT be in any keyword list.
      But if it has 8,000 unique values out of 11,000 (73%), this approach
      correctly identifies it as high-cardinality and skips it.

    Returns:
      {
        "total_records": 11000,
        "group_by": {
            "status":    {"Overdue": 847, "Completed": 7823, "In Progress": 1330},
            "priority":  {"Critical": 120, "High": 400, "Normal": 9480},
            "building":  {"Block A": 3200, "Block B": 4100, "Block C": 3700},
        },
        "numeric_stats": {
            "days_overdue": {"min": 1, "max": 143, "avg": 28.4, "sum": 24066, "count_non_null": 847},
            "cost":         {"min": 0.0, "max": 5200.0, "avg": 312.5, "sum": 3437500.0, "count_non_null": 11000},
        }
      }
    """
    if not records:
        return {"total_records": 0}

    total = len(records)

    # Single pass: collect all values per field
    field_values: Dict[str, List[Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        for field, value in record.items():
            if field not in field_values:
                field_values[field] = []
            field_values[field].append(value)

    group_by:      Dict[str, Dict[str, int]]   = {}
    numeric_stats: Dict[str, Dict[str, float]] = {}

    for field, values in field_values.items():

        # ---- Step 1: Numeric detection (by actual values, not field name) ----
        numeric_vals = [
            v for v in values
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v is not None
        ]
        if numeric_vals and (len(numeric_vals) / total) >= NUMERIC_RATIO_THRESHOLD:
            numeric_stats[field] = {
                "min":            round(min(numeric_vals), 2),
                "max":            round(max(numeric_vals), 2),
                "avg":            round(sum(numeric_vals) / len(numeric_vals), 2),
                "sum":            round(sum(numeric_vals), 2),
                "count_non_null": len(numeric_vals),
            }
            continue

        # ---- Step 2: Cardinality check (by actual data, not field name) ------
        non_null_vals = [
            str(v).strip()
            for v in values
            if v is not None and str(v).strip() not in ("", "None", "null", "NULL")
        ]
        if not non_null_vals:
            continue

        unique_count      = len(set(non_null_vals))
        uniqueness_ratio  = unique_count / total   # e.g. 3/11000 = 0.0003 for "status"

        if uniqueness_ratio >= CARDINALITY_RATIO_THRESHOLD:
            # High cardinality -- identifier or free-text field, skip it
            # Examples: task_id (100%), technician_name (80%), notes (99%)
            logger.debug(
                "|| [DataSummarizer] field='%s' skipped: uniqueness=%.1f%% >= threshold=%.1f%%",
                field, uniqueness_ratio * 100, CARDINALITY_RATIO_THRESHOLD * 100,
            )
            continue

        # Low cardinality -- categorical field, compute group-by counts
        # Examples: status (0.03%), priority (0.05%), building (0.1%)
        counts: Dict[str, int] = {}
        for v in non_null_vals:
            counts[v] = counts.get(v, 0) + 1

        # Sort by count descending (most common first)
        group_by[field] = dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    summary: Dict[str, Any] = {"total_records": total}
    if group_by:
        summary["group_by"] = group_by
    if numeric_stats:
        summary["numeric_stats"] = numeric_stats

    return summary
