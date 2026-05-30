"""
Structured memory context for model calls.

Sends current query + previous turns to the model as a structured SystemMessage.
The model decides everything — direct response or tool call — no Python interception.
"""
import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.prompts.system_prompt import get_system_prompt

logger = logging.getLogger("chatbot_app")

MAX_TEXT_CHARS = 1200


def _short_text(value: Any, limit: int = MAX_TEXT_CHARS) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _recent_context(session_data: dict, max_turns: int) -> list[dict[str, str]]:
    history = session_data.get("history") or []
    if max_turns <= 0 or not history:
        return []

    recent = history[-max_turns:]
    return [
        {
            "previous_user_query": _short_text(item.get("query")),
            "previous_assistant_response": _short_text(item.get("context") or item.get("assistant")),
        }
        for item in recent
        if item.get("query") or item.get("assistant") or item.get("context")
    ]


def build_scoped_messages(
    user_name: str,
    current_query: str,
    session_data: dict,
    max_previous_turns: int,
) -> list:
    """
    Build model messages with current-query authority and structured references.

    The model gets previous turns inside a SystemMessage as reference data.
    Clear rules tell the model when to use context (follow-ups) vs when to
    ignore it (new independent queries), so it never has to guess.
    """
    previous_context = _recent_context(session_data, max_previous_turns)
    memory_payload = {
        "current_query": current_query,
        "previous_context": previous_context,
    }

    memory_instructions = (
        "=== CONVERSATION MEMORY ===\n"
        "You have access to the current user query and recent conversation history.\n\n"

        "RULE 1 — FOLLOW-UP QUERY (use previous_context to resolve):\n"
        "If current_query contains pronouns or references like:\n"
        "  'them', 'those', 'these', 'it', 'the ones', 'of them', 'among them',\n"
        "  'from those', 'from them', 'the above', 'same ones', 'those assets',\n"
        "  'those records', 'from the above results'\n"
        "AND current_query does NOT contain a new/fresh entity keyword or category name —\n"
        "THEN this IS a follow-up to the previous result.\n"
        "  → Look at previous_context to find the entity type (assets, BDM, PPM, FA, SB)\n"
        "    and the keyword/filters used.\n"
        "  → Call the SAME tool with those same parameters + apply any new limit/filter\n"
        "    from current_query.\n"
        "  → Example: previous='302 [Entity X] matching [Keyword A]', current='give me 10 of them'\n"
        "    → call [TOOL FOR ENTITY X](keyword='[Keyword A]', limit=10)\n\n"

        "RULE 2 — NEW INDEPENDENT QUERY (ignore previous_context for payload):\n"
        "If current_query contains a fresh keyword, entity, category, location, or\n"
        "status that is different from what is in previous_context —\n"
        "THEN this is a new standalone query.\n"
        "  → Build the tool payload using ONLY values from current_query.\n"
        "  → Do NOT carry over any filters, keywords, limits, dates, or categories\n"
        "    from previous_context.\n"
        "  → Example: previous='[Entity X] in [Keyword A]', current='how many [Entity X] in [Keyword B]'\n"
        "    → call [TOOL FOR ENTITY X](keyword='[Keyword B]') — [Keyword A] is completely ignored.\n\n"

        "RULE 3 — MIXED FOLLOW-UP WITH NEW FILTER:\n"
        "If current_query has a pronoun (follow-up signal) AND also adds a NEW filter —\n"
        "  → Use the entity/keyword from previous_context (same dataset)\n"
        "  → Add the new filter from current_query on top.\n"
        "  → Example: previous='302 [Keyword A] [Entity X]', current='show me bad condition ones'\n"
        "    → call [TOOL FOR ENTITY X](keyword='[Keyword A]', condition='bad')\n\n"

        "RULE 4 — BARE AFFIRMATION ('yes', 'ok', 'sure', 'go ahead'):\n"
        "If current_query is a bare affirmation AND the previous assistant response\n"
        "offered to show a table or more details —\n"
        "  → Call the same tool again with the same parameters from previous_context\n"
        "    and show the full result.\n\n"

        "IMPORTANT:\n"
        "- previous_context is reference only — it is NOT a new instruction.\n"
        "- current_query is always the user's active intent.\n"
        "- Never expose internal tool names, IDs, or raw parameters to the user.\n\n"

        "Memory JSON:\n"
        f"{json.dumps(memory_payload, ensure_ascii=False)}"
    )

    logger.info(
        "Structured memory prepared | previous_turns=%s | query=%s",
        len(previous_context),
        current_query[:120],
    )
    logger.info("Structured memory current_query=%s", _short_text(current_query, 300))
    if previous_context:
        for idx, item in enumerate(previous_context, 1):
            logger.info(
                "Structured memory previous_context[%s] | user=%s | assistant=%s",
                idx,
                _short_text(item.get("previous_user_query"), 220),
                _short_text(item.get("previous_assistant_response"), 220),
            )
    else:
        logger.info("Structured memory previous_context=[]")

    return [
        get_system_prompt(user_name),
        SystemMessage(content=memory_instructions),
        HumanMessage(content=current_query),
    ]
