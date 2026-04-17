"""
app/utils/query_utils.py
─────────────────────────
Query helper utilities for the WebSocket chat handler.

Functions:
    _has_date_keyword()      → checks if a query contains any date-related term
    _build_table_context()   → builds the context string for two-step table flow
"""

import re
import logging

logger = logging.getLogger("utils.query_utils")


def _has_date_keyword(text: str) -> bool:
    """Return True if the query contains any date-related keyword or pattern."""
    if not text:
        return False
    q = text.lower()
    keywords = (
        "today", "yesterday", "last week", "this week",
        "last month", "this month", "last year", "this year",
        "week", "month", "year", "day", "days", "date",
    )
    if any(kw in q for kw in keywords):
        return True
    return bool(re.search(r"\b\d{4}-\d{2}-\d{2}\b", q))


def _build_table_context(context_summary: str, user_query: str) -> str:
    """
    Build a short table context string for the two-step yes/no table flow.
    Defaults to 'last 7 days' when no date keyword is in the query.
    """
    summary = (context_summary or "").strip()

    # Strip the follow-up question line if included
    lines   = [l.strip() for l in summary.splitlines() if l.strip()]
    lines   = [l for l in lines if "would you like to see" not in l.lower()]
    summary = " ".join(lines).strip()

    if not _has_date_keyword(user_query):
        return "Here is the last 7 days data you requested."

    return summary or "Here is the detailed table you requested."