"""
langchain_helpers.py — Pure helper functions and regex constants for LangChain service.

All functions here are stateless (no class, no model). They are imported by
langchain_service.py and kept here so that the service file stays focused
on the LangChainService class logic only.
"""
import re as _re
import json as _json
from langchain_core.messages import AIMessage, SystemMessage

# ── Regex: strip model boilerplate "Would you like a markdown table?" ─────────
# UI already renders tables for multi-tool and most list flows.
_RE_TABLE_OFFER_PHRASE = _re.compile(
    r"\s*(?:"
    r"would you like to view (?:this )?data as a markdown table(?: for better understanding)?|"
    r"would you like (?:to see )?(?:this )?(?:data )?(?:as |in )?a (?:markdown )?table(?: for better understanding)?"
    r")\s*\??\s*",
    _re.I,
)


def _strip_redundant_table_offer(text: str) -> str:
    if not text or not isinstance(text, str):
        return text or ""
    cleaned = _RE_TABLE_OFFER_PHRASE.sub(" ", text)
    return _re.sub(r"\s+", " ", cleaned).strip()


# ── Date extraction from natural-language queries ─────────────────────────────

def extract_date_from_query(query: str):
    """Extract date keyword from user query for forced tool calls."""
    q = query.lower()
    # ORDER MATTERS — check longer phrases first
    if "last week" in q:
        return "last week", "last week"
    elif "this week" in q:
        return "this week", "today"
    elif "last month" in q:
        return "last month", "last month"
    elif "this month" in q:
        return "this month", "today"
    elif "this year" in q:
        return "this year", "today"
    elif "last year" in q:
        return "last year", "last year"
    elif "yesterday" in q:
        return "yesterday", "yesterday"
    elif "today" in q:
        return "today", "today"
    elif "current" in q or "now" in q:
        # Treat current/now wording as today's data
        return "today", "today"

    # ── Dynamic pattern: X days/weeks/months/years ago/before ──
    match = _re.search(r"(\d+)\s*(day|week|month|year)s?\s*(ago|before)", q)
    if match:
        found_phrase = match.group(0)
        return found_phrase, found_phrase

    # ── Match explicit month names (e.g. "March", "April 2026") ──
    month_match = _re.search(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december)(?:\s+\d{4})?\b",
        q,
    )
    if month_match:
        found_month = month_match.group(0).title()
        return found_month, found_month

    return None, None


# ── Follow-up keyword extractor ───────────────────────────────────────────────
# Reads the last AI response from the messages list.
# Our context_summary always says: '...matching "Keyword" in our records...'
# This pattern is produced by format_keyword_count_reply() in keyword_match_context.py
_RE_PREV_KEYWORD = _re.compile(
    r'matching\s+["\u2018\u2019\u201c\u201d\'](.*?)["\u2018\u2019\u201c\u201d\']',
    _re.IGNORECASE,
)


def _extract_prev_keyword(messages: list) -> "str | None":
    """
    Scan the messages list (reversed) for the previous assistant keyword.
    Two sources are checked:
      1. AIMessage content — used when real AIMessage objects exist in the list.
      2. SystemMessage content — scoped_memory_service packs previous_context as
         JSON inside a SystemMessage (format: {"previous_assistant_response": "...matching 'X'..."}).
    Returns the keyword string or None if not found.
    """
    for m in reversed(messages):
        # Source 1: real AIMessage (e.g. after multi-turn with tool history)
        if isinstance(m, AIMessage):
            content = (m.content or "") if isinstance(m.content, str) else ""
            hit = _RE_PREV_KEYWORD.search(content)
            if hit:
                return hit.group(1).strip()
        # Source 2: SystemMessage containing the scoped memory JSON blob
        if isinstance(m, SystemMessage):
            content = (m.content or "") if isinstance(m.content, str) else ""
            if "previous_assistant_response" in content:
                hit = _RE_PREV_KEYWORD.search(content)
                if hit:
                    return hit.group(1).strip()
    return None


# ── Patterns: detect when a prior AI answer already named the tool ─────────────
_RE_ESTAB_FA = _re.compile(
    r"\bfacility audit\b|\bfa\b.*\bcomplaints?\b|\bcomplaints?\b.*\bfa\b",
    _re.IGNORECASE,
)
_RE_ESTAB_BDM = _re.compile(
    r"\bbreakdown\b.*\bcomplaints?\b|\bcomplaints?\b.*\bbreakdown\b"
    r"|\bbdm\b.*\bcomplaints?\b|\bcomplaints?\b.*\bbdm\b",
    _re.IGNORECASE,
)
_RE_ESTAB_PPM = _re.compile(r"\bppm\b|\bpreventive maintenance\b", _re.IGNORECASE)
_RE_ESTAB_SB = _re.compile(
    r"\bschedule.based\b|\bsb\b.*\bwork\s*orders?\b|\bwork\s*orders?\b.*\bsb\b",
    _re.IGNORECASE,
)
_RE_ESTAB_ASSETS = _re.compile(r"\bassets?\b|\bequipments?\b", _re.IGNORECASE)


def _extract_established_tool_context(messages: list | None) -> "str | None":
    """
    Detect if the bot already answered an FA/BDM/PPM/SB/ASSETS query in previous_context.

    Architecture note: messages = [SystemMessage(system_prompt),
                                   SystemMessage(memory_json),
                                   HumanMessage(query)]
    There are NO AIMessage objects in the list. Previous context is packed as JSON
    inside the second SystemMessage under the key "previous_context", each item
    having "previous_assistant_response".

    Returns: 'fa', 'bdm', 'ppm', 'sb', 'assets', or None.
    """
    if not messages:
        return None

    for m in messages:
        if not isinstance(m, SystemMessage):
            continue
        content = (m.content or "") if isinstance(m.content, str) else ""
        if "previous_context" not in content:
            continue
        try:
            json_start = content.find("{")
            if json_start == -1:
                continue
            payload = _json.loads(content[json_start:])
            prev_turns = payload.get("previous_context") or []
            # Check most recent turns first
            for turn in reversed(prev_turns):
                resp = (turn.get("previous_assistant_response") or "").lower()
                if not resp:
                    continue
                if _RE_ESTAB_FA.search(resp):
                    return "fa"
                if _RE_ESTAB_BDM.search(resp):
                    return "bdm"
                if _RE_ESTAB_PPM.search(resp):
                    return "ppm"
                if _RE_ESTAB_SB.search(resp):
                    return "sb"
                if _RE_ESTAB_ASSETS.search(resp):
                    return "assets"
        except Exception:
            pass
    return None


def _is_after_clarification(messages: list | None) -> bool:
    """
    True if the last assistant turn asked for clarification.
    Reads the SystemMessage JSON memory blob (previous_context[-1].previous_assistant_response)
    since no AIMessage objects exist in the messages list.
    """
    if not messages:
        return False

    for m in messages:
        if not isinstance(m, SystemMessage):
            continue
        content = (m.content or "") if isinstance(m.content, str) else ""
        if "previous_context" not in content:
            continue
        try:
            json_start = content.find("{")
            if json_start == -1:
                continue
            payload = _json.loads(content[json_start:])
            prev_turns = payload.get("previous_context") or []
            if not prev_turns:
                return False
            # Only check the LAST assistant turn
            prev = (prev_turns[-1].get("previous_assistant_response") or "").lower()
            # Work order clarification: bot asked PPM vs SB
            is_workorder_clar = (
                "do you mean ppm (preventive maintenance)" in prev
                or "ppm (preventive maintenance) work orders or sb" in prev
                or "ppm or sb" in prev
            )
            # Generic table clarification: bot asked which dataset (Assets/PPM/BDM/FA/SB)
            is_table_clar = (
                "please clarify which kind of data" in prev
                or "assets, ppm, bdm, fa, or sb" in prev
            )
            return is_workorder_clar or is_table_clar
        except Exception:
            pass
    return False


def _complaint_query_is_clear(query: str, messages: list | None = None) -> bool:
    """
    True when the user named FA and/or BDM (or answered a prior clarification).
    Generic "complaints" alone stays ambiguous.
    """
    q = (query or "").lower()
    if _re.search(
        r"\b(fa|bdm|facility audit|breakdown maintenance|breakdown|ppm|sb|preventive|schedule[\s\-]based|asset|assets)\b",
        q,
    ):
        return True
    # "BDM and FA" / "FA and BDM" in one question → always fetch both, never clarify
    if _re.search(r"\bbd[m]?\b", q) and _re.search(r"\bfa\b", q):
        return True
    if _re.search(r"\b(fa|bdm)\s+and\s+(fa|bdm)\b", q):
        return True
    if _re.search(r"\bboth\b", q) and _re.search(
        r"\b(fa|bdm|complaints?|facility audit|breakdown)\b", q
    ):
        return True
    # User replied after clarification in the same session
    if messages and _is_after_clarification(messages):
        return True
    return False


def _query_wants_list_display(query: str) -> bool:
    """User asked to see data (tables), not only a numeric count."""
    q = (query or "").lower()
    return bool(
        _re.search(
            r"\b(show\s+me|show\s+all|show\s+the|list\b|display\b|give\s+me\s+(the\s+)?|retrieve\b|fetch\b)",
            q,
        )
        or q.strip().startswith("show ")
    )


def _infer_intent_from_query(query: str) -> "str | None":
    """Fast intent detection for common phrasing (avoids extra model call)."""
    q = (query or "").lower()
    if _re.search(
        r"\b(how many|count of|number of)\s+.+\s+(per|by|each|wise)\b"
        r"|\b(breakdown|grouped by|distribution)\b"
        r"|\bhow many per\b|\bcount by\b"
        r"|\bwise\b.*\bcounts?\b|\bcounts?\b.*\b(per|by|wise)\b",
        q,
    ):
        return "aggregate"
    # "show me how many …" → list (preview tables + counts), not count-only text
    if _re.search(
        r"\b(how many|total count|number of|count of|how many total|get the count|show total)\b",
        q,
    ):
        if _query_wants_list_display(q):
            return "list"
        return "count"
    if _re.search(r"\b(show|list|get |fetch |display|give me|retrieve|provide)\b", q):
        return "list"
    return None


def _append_explicit_today(text: str, query: str) -> str:
    """Ensure responses mention the same time wording user asked for."""
    q = (query or "").lower()
    if not any(k in q for k in ("today", "current", "now")):
        return (text or "").strip()

    base = (text or "").strip()

    if "current" in q:
        if "current" not in base.lower():
            return f"{base} This is for current data.".strip()
        return base

    if "now" in q:
        if "now" not in base.lower() and "today" not in base.lower():
            return f"{base} This is for now.".strip()
        return base

    if "today" not in base.lower():
        return f"{base} This is for today.".strip()
    return base


def _enrich_entity_from_args(entity: str, args: dict) -> str:
    """Append filter context to entity label for empty-result messages."""
    if not args:
        return entity
    if args.get("keyword"):
        entity = f"{entity} matching '{args.get('keyword')}'"
    for key, label in (
        ("complaint_no", "complaint"),
        ("asset_tag_no", "asset tag"),
        ("work_order", "work order"),
        ("asset_type", "type"),
        ("building", "building"),
        ("floor", "floor"),
        ("locality", "locality"),
        ("division", "division"),
        ("discipline", "discipline"),
        ("trade_group", "trade group"),
        ("status", "status"),
        ("priority", "priority"),
        ("condition", "condition"),
        ("tech", "technician"),
        ("category", "category"),
        ("contract", "contract"),
        ("make", "make"),
        ("model", "model"),
        ("serial_no", "serial number"),
    ):
        if args.get(key):
            entity = f"{entity} ({label} '{args.get(key)}')"
    if args.get("is_snagged"):
        entity = f"snagged {entity}"
    if args.get("is_scraped"):
        entity = f"scraped {entity}"
    return entity
