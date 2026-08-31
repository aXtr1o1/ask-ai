"""
Shared date-resolution helpers for the facility management module functions.
"""
import logging
import re
from datetime import date, datetime, timedelta

logger = logging.getLogger("facility_tools")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


def resolveDate(date_value, fallback, is_end_date=False):
    """Resolve relative date keywords to actual dates."""
    if date_value is None:
        return None

    today = date.today()
    val = str(date_value).strip().lower()

    # ── Relative keyword resolution ──
    if val in ("today",):
        resolved = today.isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    if val in ("yesterday",):
        resolved = (today - timedelta(days=1)).isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    if val in ("this week", "thisweek"):
        if is_end_date:
            resolved = today.isoformat()
        else:
            resolved = (today - timedelta(days=today.weekday())).isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    if val in ("last week", "lastweek"):
        last_monday = today - timedelta(days=today.weekday() + 7)
        if is_end_date:
            resolved = (last_monday + timedelta(days=6)).isoformat()
        else:
            resolved = last_monday.isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    if val in ("this month", "thismonth"):
        if is_end_date:
            resolved = today.isoformat()
        else:
            resolved = today.replace(day=1).isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    if val in ("last month", "lastmonth"):
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        if is_end_date:
            resolved = last_month_end.isoformat()
        else:
            resolved = last_month_end.replace(day=1).isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    if val in ("this year", "thisyear"):
        if is_end_date:
            resolved = today.isoformat()
        else:
            resolved = today.replace(month=1, day=1).isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    if val in ("last year", "lastyear"):
        if is_end_date:
            resolved = today.replace(month=1, day=1).isoformat()
        else:
            resolved = today.replace(year=today.year - 1, month=1, day=1).isoformat()
        logger.info("📅 Relative keyword '%s' → resolved to %s", date_value, resolved)
        return resolved

    # ── Dynamic pattern: X days/weeks/months/years ago/before ──
    match = re.search(r"(\d+)\s*(day|week|month|year)s?\s*(ago|before)", val)
    if match:
        num = int(match.group(1))
        unit = match.group(2)

        if unit == "day":
            delta = timedelta(days=num)
        elif unit == "week":
            delta = timedelta(weeks=num)
        elif unit == "month":
            delta = timedelta(days=num * 30)
        else:  # year
            delta = timedelta(days=num * 365)

        resolved = (today - delta).isoformat()
        logger.info("📅 Relative pattern '%s' → resolved to %s", date_value, resolved)
        return resolved

    # ── Validate actual date string ──
    try:
        datetime.strptime(date_value, "%Y-%m-%d").date()
        logger.info("📅 Date '%s' validated successfully", date_value)
        return date_value
    except Exception:
        logger.warning("⚠️ Invalid date format '%s' → using fallback %s", date_value, fallback)
        return fallback


def getTime(date_from, date_to):
    """Resolve relative date keywords on both ends. No default date range is applied."""
    date_from = resolveDate(date_from, fallback=None, is_end_date=False)
    date_to   = resolveDate(date_to,   fallback=None, is_end_date=True)
    logger.info("📅 Date resolution | from: %s | to: %s", date_from, date_to)
    return date_from, date_to
