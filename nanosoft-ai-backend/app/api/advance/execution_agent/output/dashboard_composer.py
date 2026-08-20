"""
Dashboard Composer — pure Python, no LLM, no hardcoded field names.

Converts the raw `final_answer` produced by the Execution Agent into a
structured list of typed presentation components that the frontend can
render dynamically without knowing anything about the domain.

No field names are hardcoded here.  All decisions are based on the actual
runtime VALUE TYPES inside `final_answer`.

Public API
----------
  compose(final_answer, shape_descriptor=None) -> list[dict]

Component types emitted
-----------------------
  {
    "type":     "kpi",
    "title":    str,        # humanised label
    "value":    str,        # formatted display value
    "raw":      Any,        # raw Python value for client-side logic
    "subtitle": str | None
  }

  {
    "type":         "dashboard_summary",
    "title":        str,
    "category_key": str,
    "metric_key":   str,
    "total_value":  float | int,
    "data":         list[dict]
  }

  {
    "type":         "record_cards",
    "title":        str,
    "data":         list[dict]
  }

  {
    "type":    "time_series_chart",
    "title":   str,
    "x_key":   str,         # field containing the date / period string
    "y_keys":  list[str],   # one or more numeric fields to plot as series
    "data":    list[dict]
  }

  {
    "type":    "table",
    "title":   str,
    "columns": list[str],   # derived from actual dict keys at runtime
    "rows":    list[list]   # each row is a list of serialised cell values
  }

  {
    "type":  "text",
    "value": str            # plain informational message or bullet list
  }
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("advance.dashboard_composer")


# ===========================================================================
# PRIMITIVE TYPE HELPERS  (value-type only, zero field-name knowledge)
# ===========================================================================

def _is_numeric(v: Any) -> bool:
    """True for int/float but NOT bool (bools are ints in Python)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)
def _is_currency(vals: list[float]) -> bool:
    """
    Detect currency by value pattern alone — no field name needed.
    Rules:
      1. All values must be >= 0
      2. All values when rounded to 2 decimal places equal themselves
         i.e. round(v, 2) == v for every value
      3. At least one value > 0 (not all zeros)
      4. Column has at least 2 rows to confirm pattern
    """
    if len(vals) < 2:
        return False
    if not all(v >= 0 for v in vals):
        return False
    if not all(round(v, 2) == v for v in vals):
        return False
    if not any(v > 0 for v in vals):
        return False
    if all(float(v) == int(v) for v in vals):
        return False
    return True


def _is_ratio_column(vals: list[float]) -> bool:
    """
    All values strictly between 0.0 and 1.0 inclusive.
    This is a 0-to-1 ratio — display as XX.X%
    Must have at least 2 values to confirm it is not coincidence.
    """
    if len(vals) < 2:
        return False
    return all(0.0 <= v <= 1.0 for v in vals)


def _is_percent_column(vals: list[float]) -> bool:
    """
    All values between 0 and 100 inclusive AND at least one value > 1.0
    (to distinguish from 0-1 ratios — handles max==1.0 edge case cleanly).
    This is a 0-to-100 percentage — display as-is with % suffix.
    Must have at least 2 values.
    """
    if len(vals) < 2:
        return False
    if not all(0.0 <= v <= 100.0 for v in vals):
        return False
    if all(0.0 <= v <= 1.0 for v in vals):
        return False
    if not any(v > 1.0 for v in vals):
        return False
    return True


def _is_scalar(v: Any) -> bool:
    """True for values that can meaningfully be displayed as a single token."""
    return isinstance(v, (int, float, str, bool)) and not isinstance(v, type(None))


def _is_private(key: str) -> bool:
    """Keys starting with '_' are internal metadata — skip them."""
    return key.startswith("_")


# ---------------------------------------------------------------------------
# Date/period detection — purely pattern-based, no field-name knowledge
# ---------------------------------------------------------------------------
_DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),          # 2024-01-15
    re.compile(r"^\d{4}-\d{2}$"),                  # 2024-01
    re.compile(r"^\d{4}-W\d{1,2}$"),               # 2024-W03
    re.compile(r"^Q[1-4]-\d{4}$"),                 # Q1-2024
    re.compile(r"^\d{4}-Q[1-4]$"),                 # 2024-Q1
    re.compile(r"^\d{4}$"),                         # 2024  (year only)
    re.compile(r"^[A-Za-z]{3}-\d{4}$"),            # Jan-2024
    re.compile(r"^\d{4}/\d{2}$"),                   # 2024/01
]


def _looks_like_date(value: str) -> bool:
    """Return True if the string value resembles a date, period, or timestamp."""
    if not isinstance(value, str):
        return False
    s = value.strip()
    return any(p.match(s) for p in _DATE_PATTERNS)


# ===========================================================================
# RECORD-LIST ANALYSIS  (operates on list[dict])
# ===========================================================================

def _find_string_keys(record: dict) -> list[str]:
    """Return keys whose value is a non-empty string (potential labels/categories)."""
    return [
        k for k, v in record.items()
        if isinstance(v, str) and v.strip() and not _is_private(k)
    ]


def _find_numeric_keys(record: dict) -> list[str]:
    """Return keys whose value is a numeric (potential metrics)."""
    return [
        k for k, v in record.items()
        if _is_numeric(v) and not _is_private(k)
    ]


def _find_date_key(records: list[dict]) -> str | None:
    """Return the first key whose string value looks like a date/period, or None."""
    if not records:
        return None
    sample_rows = records[:min(30, len(records))]
    for k in (k for k in records[0] if not _is_private(k)):
        if any(isinstance(r.get(k), str) and _looks_like_date(r.get(k, "")) 
               for r in sample_rows):
            return k
    return None


def _all_dicts(lst: list) -> bool:
    return bool(lst) and all(isinstance(item, dict) for item in lst)


def _normalise_list(lst: list) -> list[dict]:
    """
    Flatten mixed lists and coerce nested values for safe display.
    Nested dicts/lists are serialised to compact JSON strings.
    """
    import json
    clean = []
    for item in lst:
        if isinstance(item, dict):
            row = {}
            for k, v in item.items():
                if _is_private(k):
                    continue
                if isinstance(v, (dict, list)):
                    try:
                        row[k] = json.dumps(v, default=str)
                    except Exception:
                        row[k] = str(v)
                elif v is None:
                    row[k] = ""
                else:
                    row[k] = v
            if row:
                clean.append(row)
            else:
                logger.debug("_normalise_list: skipped empty row")
    return clean



# ===========================================================================
# VALUE FORMATTERS  (no domain knowledge)
# ===========================================================================

def _humanise_key(key: str) -> str:
    """Convert snake_case / camelCase keys to human-readable Title Case labels."""
    # Insert space before uppercase letters in camelCase
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)
    # Replace underscores/hyphens with spaces
    s = s.replace("_", " ").replace("-", " ")
    # Title-case each word
    return " ".join(w.capitalize() for w in s.split())


def _format_value(
    v: Any,
    key: str | None = None,
    is_currency: bool = False,
    is_ratio: bool = False,
    is_percent: bool = False,
) -> str:
    """Format a scalar value for display."""
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"

    if isinstance(v, (int, float)):
        if is_currency:
            return f"${float(v):,.2f}"
        if is_ratio and isinstance(v, float):
            return f"{v * 100:.1f}%"
        if is_percent and isinstance(v, float):
            return f"{v:.1f}%"
        if isinstance(v, float):
            if abs(v) >= 1_000:
                return f"{v:,.2f}".rstrip("0").rstrip(".")
            return f"{v:.4f}".rstrip("0").rstrip(".")
        if isinstance(v, int):
            return f"{v:,}"

    return str(v)


def _serialise_cell(
    v: Any,
    key: str | None = None,
    is_currency: bool = False,
    is_ratio: bool = False,
    is_percent: bool = False,
) -> str:
    """Convert any value to a string for a table cell."""
    import json
    if v is None or v == "":
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, (dict, list)):
        try:
            return json.dumps(v, default=str)
        except Exception:
            return str(v)
    return _format_value(v, key=key, is_currency=is_currency, is_ratio=is_ratio, is_percent=is_percent)


# ===========================================================================
# COMPONENT BUILDERS
# ===========================================================================

def _kpi(
    title: str,
    value: Any,
    subtitle: str | None = None,
    sparkline: list[float] | None = None,
    delta: float | None = None,
    delta_label: str = "vs prev",
    is_currency: bool = False,
    is_ratio: bool = False,
    is_percent: bool = False,
) -> dict:
    return {
        "type":        "kpi",
        "title":       title,
        "value":       _format_value(value, is_currency=is_currency, is_ratio=is_ratio, is_percent=is_percent),
        "raw":         value,
        "subtitle":    subtitle,
        "sparkline":   sparkline,
        "delta":       delta,
        "delta_label": delta_label,
    }
def _gauge_chart(title: str, value: float, unit: str = "%") -> dict:
    return {
        "type":  "gauge_chart",
        "title": title,
        "value": value,
        "unit":  unit,
    }


def _scatter_chart(title: str, x_key: str, y_key: str, label_key: str | None, data: list[dict]) -> dict:
    return {
        "type":      "scatter_chart",
        "title":     title,
        "x_key":     x_key,
        "y_key":     y_key,
        "label_key": label_key,
        "data":      data,
    }



def _dashboard_summary(title: str, category_key: str, metric_key: str, data: list[dict]) -> dict:
    nums = [row[metric_key] for row in data if metric_key in row and _is_numeric(row[metric_key])]
    total_val = sum(nums) if nums else 0
    return {
        "type":         "dashboard_summary",
        "title":        title,
        "category_key": category_key,
        "metric_key":   metric_key,
        "total_value":  total_val,
        "data":         data
    }


def _donut_chart(title: str, category_key: str, metric_key: str, data: list[dict]) -> dict:
    """Small categorical distribution: rendered as donut/pie with legend (≤12 categories)."""
    nums = [row[metric_key] for row in data if metric_key in row and _is_numeric(row[metric_key])]
    total_val = sum(nums) if nums else 0
    return {
        "type":         "donut_chart",
        "title":        title,
        "category_key": category_key,
        "metric_key":   metric_key,
        "total_value":  total_val,
        "data":         data,
    }


def _bar_chart(title: str, x_key: str, y_key: str, data: list[dict]) -> dict:
    """Simple single-metric category breakdown: horizontal bar chart."""
    return {
        "type":  "bar_chart",
        "title": title,
        "x_key": x_key,
        "y_key": y_key,
        "data":  data,
    }


def _grouped_bar_chart(title: str, category_key: str, metric_keys: list[str], data: list[dict]) -> dict:
    """Multiple numeric metrics per category: clustered horizontal bars."""
    return {
        "type":         "grouped_bar_chart",
        "title":        title,
        "category_key": category_key,
        "metric_keys":  metric_keys,
        "data":         data,
    }


def _area_chart(title: str, x_key: str, y_keys: list[str], data: list[dict]) -> dict:
    """Time series with gradient area fill — best for multi-metric trends."""
    return {
        "type":   "area_chart",
        "title":  title,
        "x_key":  x_key,
        "y_keys": y_keys,
        "data":   data,
    }


def _time_series_chart(title: str, x_key: str, y_keys: list[str], data: list[dict]) -> dict:
    return {
        "type":   "time_series_chart",
        "title":  title,
        "x_key":  x_key,
        "y_keys": y_keys,
        "data":   data,
    }


def _table(
    title: str,
    records: list[dict],
    note: str | None = None,
    currency_keys: set[str] | None = None,
    ratio_keys: set[str] | None = None,
    percent_keys: set[str] | None = None,
) -> dict:
    if not records:
        return {"type": "text", "value": ""}
    currency_keys = currency_keys or set()
    ratio_keys    = ratio_keys    or set()
    percent_keys  = percent_keys  or set()
    columns = list(records[0].keys())
    rows = [
        [
            _serialise_cell(
                row.get(c),
                key=c,
                is_currency=(c in currency_keys),
                is_ratio=(c in ratio_keys),
                is_percent=(c in percent_keys),
            )
            for c in columns
        ]
        for row in records
    ]
    result: dict = {
        "type":    "table",
        "title":   title,
        "columns": columns,
        "rows":    rows,
    }
    if note is not None:
        result["note"] = note
    return result


def _record_cards(title: str, data: list[dict]) -> dict:
    return {
        "type":  "record_cards",
        "title": title,
        "data":  data,
    }


def _text(value: str) -> dict:
    return {"type": "text", "value": value}


# ===========================================================================
# LIST-OF-DICTS COMPOSITION
# ===========================================================================

def _scan_column_types(
    records: list[dict],
    numeric_keys: list[str],
) -> tuple[set[str], set[str], set[str]]:
    """
    Scan each numeric column across all records and classify it as:
      - currency_keys  : matches _is_currency()
      - ratio_keys     : matches _is_ratio_column()
      - percent_keys   : matches _is_percent_column()

    Returns (currency_keys, ratio_keys, percent_keys).
    """
    currency_keys: set[str] = set()
    ratio_keys: set[str] = set()
    percent_keys: set[str] = set()

    for k in numeric_keys:
        col_vals = [float(r[k]) for r in records if _is_numeric(r.get(k))]
        if not col_vals:
            continue
        if _is_currency(col_vals):
            currency_keys.add(k)
        elif _is_ratio_column(col_vals):
            ratio_keys.add(k)
        elif _is_percent_column(col_vals):
            percent_keys.add(k)

    return currency_keys, ratio_keys, percent_keys


def _is_redundant_scalar_kpi(title: str, raw_value: Any, list_components: list[dict]) -> bool:
    """
    A scalar KPI is redundant if its raw value exactly equals the total
    number of records in any list component already being rendered.
    """
    if not _is_numeric(raw_value):
        return False
    for comp in list_components:
        if comp.get("type") in ("dashboard_summary", "record_cards", "table"):
            data = comp.get("data") or comp.get("rows") or []
            if int(raw_value) == len(data):
                return True
        if comp.get("type") == "dashboard_summary":
            if int(raw_value) == int(comp.get("total_value", -1)):
                return True
    return False


def _find_low_cardinality_key(records: list[dict]) -> tuple[str | None, list[str]]:
    """
    Scan all string columns for one whose unique values form a low-cardinality set
    (2–12 unique values AND repeated across many records — typical for status/type fields).
    Also detects boolean columns (True/False) as low-cardinality.
    Returns (best_key, sorted_unique_values) or (None, []).
    """
    if len(records) < 3:
        return None, []
    sample = records[0]
    # BUG 4.1 FIX — detect boolean columns before string scan
    bool_keys = [
        k for k in sample
        if not _is_private(k)
        and all(isinstance(r.get(k), bool) for r in records[:10] if r.get(k) is not None)
    ]
    if bool_keys:
        return bool_keys[0], ["True", "False"]
    str_keys = _find_string_keys(sample)
    best_key: str | None = None
    best_score = float("inf")
    for k in str_keys:
        if _looks_like_date(sample.get(k, "")):
            continue
        all_vals = [str(r.get(k, "")).strip() for r in records if r.get(k)]
        unique_vals = set(v for v in all_vals if v)
        n_unique = len(unique_vals)
        # Low cardinality: 2–12 unique values, covering at least 60% of records
        if 2 <= n_unique <= 12 and len(all_vals) >= len(records) * 0.6:
            # Prefer smaller cardinality (more chart-friendly)
            if n_unique < best_score:
                best_score = n_unique
                best_key   = k
    if best_key is None:
        return None, []
    unique_sorted = sorted(set(str(r.get(best_key, "")).strip() for r in records if r.get(best_key)))
    return best_key, unique_sorted


def _compose_list_of_dicts(
    records: list[dict],
    title_hint: str = "",
    resolved_format: str | None = None,
) -> list[dict]:
    """
    Determine the best representation for a non-empty list of dicts.
    Produces a FULL PAGE of analytics — multiple components per query.
    Priority: time-series → donut/grouped-bar → bar → distribution KPIs → table.
    """
    if not records:
        return []

    sample       = records[0]
    numeric_keys = _find_numeric_keys(sample)

    # fallback: scan more rows to catch numeric keys
    # that are null in the first row
    if not numeric_keys:
        for row in records[1:min(10, len(records))]:
            found = _find_numeric_keys(row)
            if found:
                numeric_keys = found
                break

    # ── Scan column types across all records (pure value-type, no field names) ─
    currency_keys, ratio_keys, percent_keys = _scan_column_types(records, numeric_keys)

    # 1. Single Record lookup: always render as record_cards
    if len(records) == 1:
        str_k = _find_string_keys(sample)
        if numeric_keys and not str_k and len(sample) == 1:
            logger.info("[DashboardComposer] → empty (single count metric redundant)")
            return []
        return [_record_cards(title_hint or "Details", _normalise_list(records))]

    str_keys     = _find_string_keys(sample)
    date_key     = _find_date_key(records)
    has_string   = bool(str_keys)
    has_numeric  = bool(numeric_keys)

    # ── SCATTER CHART ────────────────────────────────────────────────────────
    is_scatter = False
    if resolved_format in ("scatter", "scatter_chart"):
        is_scatter = True
    elif date_key is None and len(numeric_keys) == 2 and len(str_keys) <= 1 and len(records) > 30:
        is_scatter = True

    if is_scatter and len(numeric_keys) >= 2:
        x_key = numeric_keys[0]
        y_key = numeric_keys[1]
        label_key = str_keys[0] if str_keys else None
        chart_title = title_hint or f"{_humanise_key(y_key)} vs {_humanise_key(x_key)}"
        logger.info("[DashboardComposer] → scatter_chart (x=%s, y=%s, label=%s, n=%d)", x_key, y_key, label_key, len(records))
        return [_scatter_chart(chart_title, x_key, y_key, label_key, records)]

    # ── TIME SERIES ──────────────────────────────────────────────────────────
    # date column + numeric columns → KPI summary + area/line chart
    if date_key is not None and has_numeric and len(records) >= 2:
        chart_title = title_hint or "Trend Over Time"
        components: list[dict] = []
        for metric in numeric_keys[:2]:
            vals = [row[metric] for row in records if metric in row and _is_numeric(row[metric])]
            if vals:
                h = _humanise_key(metric)
                spark_vals = [float(v) for v in vals if v is not None]
                delta = None
                if len(numeric_keys) == 1:
                    vals_clean = [float(v) for v in vals if v is not None]
                    if len(vals_clean) >= 2:
                        prev_val = vals_clean[-2]
                        last_val = vals_clean[-1]
                        if prev_val != 0:
                            delta = round(((last_val - prev_val) / prev_val) * 100, 1)
                        else:
                            delta = 0.0
                is_cur = metric in currency_keys
                is_rat = metric in ratio_keys
                is_pct = metric in percent_keys
                components.append(_kpi(f"Total {h}", sum(vals), sparkline=spark_vals, delta=delta, is_currency=is_cur, is_ratio=is_rat, is_percent=is_pct))
                non_null_vals = [v for v in vals if v is not None]
                avg_val = round(sum(non_null_vals) / len(non_null_vals), 2) if non_null_vals else 0
                components.append(_kpi(f"Avg {h}", avg_val, sparkline=spark_vals, delta=None, is_currency=is_cur, is_ratio=is_rat, is_percent=is_pct))
                components.append(_kpi(f"Peak {h}", max(vals), sparkline=spark_vals, delta=None, is_currency=is_cur, is_ratio=is_rat, is_percent=is_pct))
        if len(numeric_keys) >= 2:
            components.append(_area_chart(chart_title, date_key, numeric_keys, records))
        else:
            components.append(_time_series_chart(chart_title, date_key, numeric_keys, records))
        logger.info("[DashboardComposer] → time_series (date=%s, n_metrics=%d)", date_key, len(numeric_keys))
        return components

    # ── PRE-AGGREGATED GROUPED DATA ───────────────────────────────────────────
    # Detected by: EXACTLY ONE string column (the grouping key) + numeric columns, no date.
    # This handles both simple {status, count} AND multi-metric performance reports
    # with many score columns (BUILDINGNAME, ASSETCOUNT_SCORE, BDMCOUNT_SCORE, ...).
    # Total column count is NOT used — a report can have many numeric metrics.
    # If there are 2+ string columns it's more likely a raw record set.
    if has_numeric and date_key is None and len(str_keys) == 1:
        cat_key = next(
            (k for k in str_keys if not _looks_like_date(sample.get(k, ""))),
            str_keys[0],
        )
        n = len(records)
        chart_title = title_hint or f"By {_humanise_key(cat_key)}"
        components = []

        if len(numeric_keys) >= 2:
            # Multi-metric: KPI totals + grouped bar + optional donut
            for metric in numeric_keys[:6]:
                vals = [r[metric] for r in records if metric in r and _is_numeric(r[metric])]
                if vals:
                    spark_vals = [float(v) for v in vals if v is not None]
                    components.append(_kpi(f"Total {_humanise_key(metric)}", sum(vals), sparkline=spark_vals, is_currency=(metric in currency_keys), is_ratio=(metric in ratio_keys), is_percent=(metric in percent_keys)))
            top20 = sorted(records, key=lambda r: sum(r.get(k, 0) or 0 for k in numeric_keys), reverse=True)[:20]
            components.append(_grouped_bar_chart(chart_title, cat_key, numeric_keys, top20))
            if n <= 12:
                components.append(_donut_chart(f"Distribution — {_humanise_key(numeric_keys[0])}", cat_key, numeric_keys[0], records))
            logger.info("[DashboardComposer] → multi-metric grouped_bar (cat=%s, metrics=%d, n=%d)", cat_key, len(numeric_keys), n)
            return components

        # Single metric
        primary = numeric_keys[0]
        is_cur = primary in currency_keys
        is_rat = primary in ratio_keys
        is_pct = primary in percent_keys
        if n <= 8:
            # Small: KPI per category + donut
            for row in sorted(records, key=lambda r: r.get(primary, 0) or 0, reverse=True):
                val = row.get(primary)
                if val is not None:
                    components.append(_kpi(str(row.get(cat_key, "?")), val, is_currency=is_cur, is_ratio=is_rat, is_percent=is_pct))
            components.append(_donut_chart(chart_title, cat_key, primary, records))
            logger.info("[DashboardComposer] → KPI cards + donut (cat=%s, n=%d)", cat_key, n)
        elif n <= 20:
            # Medium: donut + horizontal bar (side by side on frontend)
            total = sum(r.get(primary, 0) or 0 for r in records)
            spark_vals = [float(r.get(primary, 0) or 0) for r in records]
            components.append(_kpi(f"Total {_humanise_key(primary)}", total, sparkline=spark_vals, is_currency=is_cur, is_ratio=is_rat, is_percent=is_pct))
            components.append(_kpi("Categories", n))
            components.append(_donut_chart(f"{chart_title} (Distribution)", cat_key, primary, records))
            components.append(_bar_chart(f"{chart_title} (Breakdown)", cat_key, primary, records))
            logger.info("[DashboardComposer] → donut + bar (cat=%s, n=%d)", cat_key, n)
        else:
            # Large: horizontal bar with stats sidebar
            total = sum(r.get(primary, 0) or 0 for r in records)
            spark_vals = [float(r.get(primary, 0) or 0) for r in records]
            components.append(_kpi(f"Total {_humanise_key(primary)}", total, sparkline=spark_vals, is_currency=is_cur, is_ratio=is_rat, is_percent=is_pct))
            components.append(_kpi("Categories", n))
            components.append(_dashboard_summary(chart_title, cat_key, primary, records))
            logger.info("[DashboardComposer] → dashboard_summary (cat=%s, n=%d)", cat_key, n)
        return components

    # ── RAW MULTI-COLUMN RECORDS ─────────────────────────────────────────────
    # Real entity records (many columns). Find low-cardinality col → distribution.
    components_prefix: list[dict] = []
    lc_key, lc_vals = _find_low_cardinality_key(records)
    if lc_key:
        from collections import Counter
        counts = Counter(str(r.get(lc_key, "")).strip() for r in records if r.get(lc_key))
        dist_title = title_hint or f"By {_humanise_key(lc_key)}"
        grouped = [{"category": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]
        n_unique = len(lc_vals)
        if n_unique <= 6:
            for val, cnt in sorted(counts.items(), key=lambda x: -x[1]):
                components_prefix.append(_kpi(val, cnt))
            components_prefix.append(_donut_chart(dist_title, "category", "count", grouped))
            logger.info("[DashboardComposer] → KPI cards + donut (key=%s, n=%d)", lc_key, n_unique)
        else:
            components_prefix.append(_dashboard_summary(dist_title, "category", "count", grouped))
            logger.info("[DashboardComposer] → dashboard_summary distribution (key=%s, n=%d)", lc_key, n_unique)

    # ── Fallback: small → record_cards, large → table ────────────────────────
    bool_comps = []
    if len(records) > 1:
        bool_keys = [
            k for k in sample
            if not _is_private(k) and all(isinstance(r.get(k), bool) for r in records if r.get(k) is not None)
        ]
        for bk in bool_keys[:2]:
            yes_count = sum(1 for r in records if r.get(bk) is True)
            no_count = sum(1 for r in records if r.get(bk) is False)
            if yes_count > 0 or no_count > 0:
                donut_data = [
                    {"label": "Yes", "count": yes_count},
                    {"label": "No", "count": no_count}
                ]
                bool_comps.append(_donut_chart(
                    title=f"Split of {_humanise_key(bk)}",
                    category_key="label",
                    metric_key="count",
                    data=donut_data
                ))

    if len(records) <= 10:
        return components_prefix + bool_comps + [_record_cards(title_hint or "Details", _normalise_list(records))]
    return components_prefix + bool_comps + [
        _table(
            title_hint or "Details",
            _normalise_list(records),
            note=f"{len(records)} total records",
            currency_keys=currency_keys,
            ratio_keys=ratio_keys,
            percent_keys=percent_keys,
        )
    ]


# ===========================================================================
# SCALAR-LIST COMPOSITION
# ===========================================================================

def _compose_scalar_list(lst: list) -> list[dict]:
    """Render a list of scalar values as a human-readable text component."""
    filtered = [str(v) for v in lst if v is not None and str(v).strip()]
    if not filtered:
        return [_text("No values returned.")]
    if len(filtered) == 1:
        return [_kpi("Result", filtered[0])]
    bullet_text = "\n".join(f"• {v}" for v in filtered)
    return [_text(bullet_text)]


# ===========================================================================
# DICT COMPOSITION
# ===========================================================================

def _compose_dict(d: dict, resolved_format: str | None = None) -> list[dict]:
    """
    Handle a dict final_answer.
    Two sub-cases:
      A) All values are scalars → N KPI cards (one per key)
      B) Contains an embedded list-of-dicts → KPI cards for scalars + chart/table for list
    """
    # Partition into scalar values and list values
    scalar_items: dict[str, Any] = {}
    list_items:   dict[str, list] = {}

    for k, v in d.items():
        if _is_private(k):
            continue
        if _is_scalar(v):
            scalar_items[k] = v
        elif isinstance(v, list) and v:
            list_items[k] = v

    components: list[dict] = []

    # KPI cards for every scalar key — pure value-type classification
    for k, v in scalar_items.items():
        if _is_numeric(v) and isinstance(v, float) and 0.0 <= float(v) <= 1.0:
            # BUG 1.2 FIX — guard against value already being a percentage (>1)
            raw = float(v)
            gauge_val = round(raw * 100, 1) if raw <= 1.0 else round(raw, 1)
            components.append(_gauge_chart(_humanise_key(k), gauge_val))
        else:
            components.append(_kpi(_humanise_key(k), v))

    # Chart/table for up to 3 non-empty embedded lists
    if list_items:
        list_keys_processed = 0
        for key, lst in list_items.items():
            if list_keys_processed >= 3:
                break
            if not lst:
                continue
            if _all_dicts(lst):
                list_comps = _compose_list_of_dicts(
                    _normalise_list(lst),
                    title_hint=_humanise_key(key),
                    resolved_format=resolved_format,
                )
                if list_comps:
                    # Drop scalar KPIs whose value equals the record count (structural dedup)
                    components = [
                        c for c in components
                        if c["type"] != "kpi"
                        or not _is_redundant_scalar_kpi(c["title"], c.get("raw"), list_comps)
                    ]
                components.extend(list_comps)
                list_keys_processed += 1
            else:
                components.extend(_compose_scalar_list(lst))
                list_keys_processed += 1

    return components


# ===========================================================================
# PUBLIC API
# ===========================================================================

def compose(
    final_answer:     Any,
    shape_descriptor: dict | None = None,
    resolved_format:  str | None = None,
) -> list[dict]:
    """
    Convert a raw `final_answer` into a typed presentation component list.

    All decisions are purely value-type based — no field names hardcoded,
    no LLM, no arbitrary thresholds beyond display caps.

    Args:
        final_answer:     The raw value produced by the Execution Agent's
                          final_answer_tool.  May be any Python type.
        shape_descriptor: Optional dict from ShapeResolver with keys
                          {"shape": str, "reason": str}.  Used for logging
                          only — all component decisions are made independently.
        resolved_format:  Optional resolved format string (e.g. TABLE | GRAPH)
                          to align layout components.

    Returns:
        A list of typed component dicts.  The list is always non-empty.
        Possible types: "kpi", "dashboard_summary", "record_cards", "time_series_chart", "table", "text".
    """
    shape = (shape_descriptor or {}).get("shape", "unknown")
    logger.info("[DashboardComposer] composing | shape=%s | type=%s | format=%s", shape, type(final_answer).__name__, resolved_format)

    # ── None / error ─────────────────────────────────────────────────────────
    if final_answer is None:
        logger.info("[DashboardComposer] → text (None)")
        return [_text("No result available.")]

    if isinstance(final_answer, dict):
        if "error" in final_answer or "_dep_failed" in final_answer:
            msg = final_answer.get("error") or final_answer.get("_dep_failed") or "Execution failed."
            logger.info("[DashboardComposer] → text (error dict)")
            return [_text(str(msg))]

    # ── Scalar ───────────────────────────────────────────────────────────────
    if not isinstance(final_answer, (dict, list)):
        logger.info("[DashboardComposer] → empty (scalar KPI redundant)")
        return []

    # ── Empty list ────────────────────────────────────────────────────────────
    if isinstance(final_answer, list) and len(final_answer) == 0:
        logger.info("[DashboardComposer] → text (empty list)")
        return [_text("No records returned.")]

    # ── List ──────────────────────────────────────────────────────────────────
    if isinstance(final_answer, list):
        dict_items   = [item for item in final_answer if isinstance(item, dict)]
        scalar_items = [item for item in final_answer if not isinstance(item, dict)]

        if not dict_items:
            logger.info("[DashboardComposer] → text (scalar list)")
            return _compose_scalar_list(final_answer)

        if dict_items:
            logger.info("[DashboardComposer] → list_of_dicts (len=%d)", len(dict_items))
            return _compose_list_of_dicts(_normalise_list(dict_items), resolved_format=resolved_format)

    # ── Dict ─────────────────────────────────────────────────────────────────
    if isinstance(final_answer, dict):
        # If it's a single key count/total dict (e.g. {"count": 7}), return empty list (redundant KPI)
        if len(final_answer) == 1:
            k, v = list(final_answer.items())[0]
            if not k.startswith("_") and _is_scalar(v):
                logger.info("[DashboardComposer] → empty (single count dict KPI redundant)")
                return []
        logger.info("[DashboardComposer] → dict composition")
        return _compose_dict(final_answer, resolved_format=resolved_format)

    # ── Fallback ──────────────────────────────────────────────────────────────
    logger.warning("[DashboardComposer] unhandled type=%s — text fallback", type(final_answer).__name__)
    return [_text(str(final_answer))]
