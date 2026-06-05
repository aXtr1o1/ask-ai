"""
LangChain Tools for Facility Management
"""
from langchain.tools import tool
import json
import logging

from app.models.schemas import AssetsInput, PPMInput, BDMInput
from fastapi import HTTPException
from app.api.models.schemas import AssetRequest, PPMRequest, BDMRequest
from app.models.schemas import FAInput, SBInput
from app.api.routes.assets import get_assets
from app.api.routes.ppm import get_ppm
from app.api.routes.bdm import get_bdm
from app.api.models.schemas import FARequest, SBRequest
from app.api.routes.fa import get_fa
from app.api.routes.sb import get_sb
from datetime import date, timedelta



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

    # ── Dynamic pattern: X days/weeks/months/years ago/before ──
    import re
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
        elif unit == "year":
            delta = timedelta(days=num * 365)
        else:
            delta = timedelta(days=num)
            
        resolved = (today - delta).isoformat()
        logger.info("📅 Relative pattern '%s' → resolved to %s", date_value, resolved)
        return resolved

    # ── Validate actual date string ──
    try:
        from datetime import datetime
        datetime.strptime(date_value, "%Y-%m-%d").date()
        logger.info("📅 Date '%s' validated successfully", date_value)
        return date_value
    except Exception:
        logger.warning("⚠️ Invalid date format '%s' → using fallback %s", date_value, fallback)
        return fallback


def getTime(date_from, date_to):
    # today = date.today()
    # today_str = today.isoformat()
    # default_from = (today - timedelta(days=6)).isoformat()

    # ── Resolve relative keywords first ──
    # ✅ fallback=None means no default 7-day filter is applied
    date_from = resolveDate(date_from, fallback=None, is_end_date=False)
    date_to   = resolveDate(date_to,   fallback=None, is_end_date=True)

    # # Case 1: both dates missing → last 7 days (HASHED BY USER REQUEST)
    # if date_from is None and date_to is None:
    #     logger.info("📅 No dates provided → defaulting to last 7 days: %s to %s", default_from, today_str)
    #     return default_from, today_str

    # # Case 2: only from date missing
    # elif date_from is None:
    #     logger.info("📅 date_from missing → defaulting to 7 days before date_to: %s to %s", default_from, date_to)
    #     return default_from, date_to

    # # Case 3: only to date missing
    # elif date_to is None:
    #     logger.info("📅 date_to missing → defaulting to today: %s to %s", date_from, today_str)
    #     return date_from, today_str

    # Case 4: Return resolved values
    logger.info("📅 Date Resolution (No Default) | from: %s -> %s | to: %s -> %s", date_from, date_from, date_to, date_to)
    return date_from, date_to


