"""
services/ai/intent_classifier.py
──────────────────────────────────
Classifies user query intent into one of three categories.

Extracted from langchain_service.py to keep that file focused on orchestration.

Why intent classification matters:
    After a tool returns data, the AI needs to format the response differently
    depending on what the user asked:
        - count     → one sentence with total number (no table)
        - aggregate → insight summary + optional breakdown table
        - list      → summary sentence + offer to show full table

Intent is determined by calling the LLM with a simple classification prompt.
This is CALL-2 in the 4-call flow inside langchain_service.py.

Usage:
    from app.services.ai.intent_classifier import classify_intent
    intent = classify_intent(model, query)  → "count" | "aggregate" | "list"
"""

import logging
from langchain_core.messages import HumanMessage

logger = logging.getLogger("services.ai.intent_classifier")


def classify_intent(model, query: str) -> str:
    """
    Classify the user query into one of three intent categories.

    Uses a separate model call (CALL-2) with a focused classification prompt.
    Returns exactly one of: "count", "aggregate", "list"

    Rules:
        count     → user wants ONLY a single total number
                    e.g. "how many assets", "total complaints", "count of PPM"
        aggregate → user wants a grouped summary or breakdown
                    e.g. "how many per division", "breakdown by status"
        list      → user wants records shown as a table
                    e.g. "show assets", "list complaints", "give me 10 PPM"

    IMPORTANT: "give me X" where X is a number = list (NOT count)
    IMPORTANT: "how many per X" = aggregate (NOT count)

    Args:
        model → LangChain model (already has tools bound — ok for classification too)
        query → the user's query string

    Returns:
        "count" | "aggregate" | "list"
    """
    logger.info("[INTENT] Classifying query | query='%s'", query[:100])

    # Single-message call — no history needed for intent classification
    intent_msg = model.invoke([
        HumanMessage(content=f"""
        Classify this user query into one of three intents:
        - "count"     → user wants ONLY a single total number
        - "aggregate" → user wants a grouped summary or breakdown by category
        - "list"      → user wants full records shown as a table

        IMPORTANT RULES:
        - "how many per X" or "count by X" or "breakdown by X" = aggregate (NOT count)
        - "how many total" or "how many exist" with no grouping = count
        - "show", "list", "display", "get", "fetch" = list
        - "give me X" where X is a number = list (NOT count)

        Query: "{query}"
        Reply with ONLY one word: count or aggregate or list
        """)
    ])

    intent = intent_msg.content.strip().lower()

    # Guard against unexpected responses — default to "list"
    if intent not in ("count", "aggregate", "list"):
        logger.warning(
            "[INTENT] Unexpected classification '%s' — defaulting to 'list'", intent
        )
        intent = "list"

    logger.info("[INTENT] ✅ Result | query='%s' | intent=%s", query[:80], intent)
    return intent, intent_msg