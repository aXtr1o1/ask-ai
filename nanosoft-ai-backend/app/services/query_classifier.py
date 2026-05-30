"""
Query Classifier — Pre-classification before model invocation.

Purpose:
    Decide whether a user query needs facility data tools (ASSETS, PPM, BDM, FA, SB)
    or is purely conversational/general (greetings, personal questions, definitions).

Usage:
    from app.services.query_classifier import needs_facility_tools

    if needs_facility_tools(query, previous_context):
        ai_msg = model_with_tools.invoke(messages)
    else:
        ai_msg = model_plain.invoke(messages)        # no tools offered
"""

import re
import logging

logger = logging.getLogger("query_classifier")

# ─────────────────────────────────────────────────────────────────────────────
# 1. CONVERSATIONAL PATTERNS — these are NEVER facility data queries.
#    If ANY of these match, tools are NOT offered.
# ─────────────────────────────────────────────────────────────────────────────
_CONVERSATIONAL = re.compile(
    r"""
    ^\s*(
        # greetings
        hi\b | hello\b | hey\b | good\s+(morning|afternoon|evening|night) |
        # self-identification
        my\s+name\s+is | i\s+am\s+\w+ | i'm\s+\w+ |
        # questions about personal chat context
        what\s+is\s+my\s+name | what('s|\s+is)\s+my\s+name |
        what\s+(was|were|is)\s+(my|your)\s+(last|previous|prior)\s+(question|query|message) |
        what\s+did\s+i\s+(ask|say|tell|type) |
        what\s+did\s+you\s+(say|tell|answer|respond) |
        # identity questions about the bot
        who\s+are\s+you | what\s+are\s+you | what\s+is\s+your\s+name |
        are\s+you\s+(an?\s+)?(ai|bot|assistant|robot) |
        # thanks / acknowledgements
        thank\s*(you|s)?\b | thanks\b | ok\s*thank | great\s*thank |
        # general pleasantries
        how\s+are\s+you | i\s+am\s+(fine|good|okay|great|bad|well)
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ─────────────────────────────────────────────────────────────────────────────
# 2. FACILITY DATA KEYWORDS — if ANY of these appear, tools ARE offered.
#    This covers direct asset/maintenance/complaint queries.
# ─────────────────────────────────────────────────────────────────────────────
_FACILITY_KEYWORDS = re.compile(
    r"""
    \b(
        # ── Modules ──
        assets? | ppm | bdm | fa\b | sb\b |
        # ── Actions on data ──
        how\s+many | show\s+(me|all|the) | list\b | count\b | fetch\b | retrieve\b |
        give\s+me | display\b | total\b | number\s+of | aggregate\b |
        # ── Asset terms ──
        equipment | barcode | asset.?tag | serial | snagged | scraped |
        on.?hold | condition | make\b | model\b | thermostat | heater |
        hvac | chiller | fcu | ahu | pump | generator | meter | panel |
        cctv | camera | elevator | lift | transformer | dg\s*set |
        fire.?alarm | sprinkler | plumbing | electrical |
        # ── Maintenance / complaints ──
        complaint | maintenance | work.?order | breakdown | preventive |
        schedule.?based | facility.?audit | inspection | snagging |
        # ── Location / classification ──
        building | floor | locality | discipline | division | trade.?group |
        category | service.?type | priority | status | stage |
        online\b | offline\b |
        # ── Time references for data ──
        today | yesterday | this\s+week | last\s+week |
        this\s+month | last\s+month | this\s+year | last\s+year |
        # ── Follow-up data pronouns (they reference previous tool results) ──
        of\s+them | among\s+them | from\s+them | from\s+those |
        of\s+those | the\s+ones | those\s+assets | those\s+records
    )\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ─────────────────────────────────────────────────────────────────────────────
# 3. FOLLOW-UP CONTEXT KEYWORDS — pronouns that refer to a previous data result.
#    We check BOTH the query and the previous assistant context.
# ─────────────────────────────────────────────────────────────────────────────
_FOLLOWUP_PRONOUNS = re.compile(
    r"\b(them|those|these|it\b|the\s+ones|of\s+them|among\s+them|"
    r"from\s+those|from\s+them|the\s+above|same\s+ones|"
    r"show\s+me\s+(more|them|those)|give\s+me\s+(more|them|those))\b",
    re.IGNORECASE,
)

_PREV_DATA_CONTEXT = re.compile(
    r"\b(assets?|records?|results?|items?|ppm|bdm|fa\b|sb\b|complaints?|"
    r"work\s*orders?|matching|found|retrieved|fetched)\b",
    re.IGNORECASE,
)


def needs_facility_tools(query: str, previous_assistant_context: str = "") -> bool:
    """
    Return True  → invoke model WITH facility tools (ASSETS, PPM, BDM, FA, SB).
    Return False → invoke model WITHOUT tools (plain conversational response).

    Logic:
      1. If query matches a conversational pattern → False (no tools)
      2. If query has a follow-up pronoun AND previous context was a data result → True (tools needed)
      3. If query contains facility keywords → True (tools needed)
      4. Otherwise → False (safe default: conversational)
    """
    q = (query or "").strip()
    prev = (previous_assistant_context or "").strip()

    # ── STEP 1: Conversational shortcut ──────────────────────────────────────
    if _CONVERSATIONAL.match(q):
        logger.info(
            "🗣️ [QueryClassifier] CONVERSATIONAL | no tools | query='%s'", q[:80]
        )
        return False

    # ── STEP 2: Follow-up pronoun + previous data context ────────────────────
    if _FOLLOWUP_PRONOUNS.search(q) and _PREV_DATA_CONTEXT.search(prev):
        logger.info(
            "🔗 [QueryClassifier] FOLLOW-UP (pronoun + data context) | tools | query='%s'", q[:80]
        )
        return True

    # ── STEP 3: Facility keyword present ─────────────────────────────────────
    if _FACILITY_KEYWORDS.search(q):
        logger.info(
            "🏢 [QueryClassifier] FACILITY KEYWORD MATCH | tools | query='%s'", q[:80]
        )
        return True

    # ── STEP 4: Default — no strong signal → conversational ──────────────────
    logger.info(
        "🗣️ [QueryClassifier] NO FACILITY SIGNAL | no tools | query='%s'", q[:80]
    )
    return False
