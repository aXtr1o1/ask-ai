"""
Understanding Agent -- Node 1 in the LangGraph multi-agent pipeline.

Responsibilities:
  - Deeply understand the user's query in the facility management context
  - Extract ALL relevant filters from the full module schemas (ASSETS/PPM/BDM/FA/SB)
  - Determine intent type, scope, entities, clarity, and context dependency
  - Produce structured JSON output consumed by the Goal Planning Agent
  - Log a clean, structured summary to the console (no emojis)

Model: gemini-2.5-flash with thinking enabled
"""

import json
from datetime import date

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.agents.prompts.understanding_prompt import (
    UNDERSTANDING_SYSTEM_PROMPT,
    UNDERSTANDING_USER_TEMPLATE,
)
from app.agents.log_config import setup_agent_logger
from app.config import settings

logger = setup_agent_logger("understanding_agent")


# -- Model initialisation -----------------------------------------------------

def _build_model() -> ChatGoogleGenerativeAI:
    """Build the Understanding Agent model with thinking enabled."""
    return ChatGoogleGenerativeAI(
        model=settings.MULTI_AGENT_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,          # required for thinking mode
        thinking_budget=3000,   # correct kwarg for langchain_google_genai
    )


# -- Console log printer -------------------------------------------------------

def _print_understanding_log(intent: dict, thinking_tokens: dict, query: str) -> str:
    """Print a clean structured log block. No emojis."""
    scope_str    = ", ".join(intent.get("scope", [])) or "Undetermined"
    modules      = intent.get("entities", {}).get("modules", [])
    filters      = intent.get("entities", {}).get("filters", {}) or {}
    count_req    = intent.get("entities", {}).get("count_requested")
    is_agg       = intent.get("entities", {}).get("is_aggregate")
    group_by     = intent.get("entities", {}).get("group_by")
    date_raw     = intent.get("entities", {}).get("date_range_raw")

    # Build entity detail lines
    entity_lines = []
    if modules:
        entity_lines.append(f"modules         = {modules}")
    for k, v in filters.items():
        if v is not None:
            entity_lines.append(f"{k:<16}= {v!r}")
    if count_req:
        entity_lines.append(f"count_requested = {count_req}")
    if is_agg is not None:
        entity_lines.append(f"is_aggregate    = {is_agg}")
    if group_by:
        entity_lines.append(f"group_by        = {group_by!r}")
    if date_raw:
        entity_lines.append(f"date_range_raw  = {date_raw!r}")

    entity_block = "\n".join(
        f"||    {line}" for line in entity_lines
    ) if entity_lines else "||    (none extracted)"

    clarification_str = (
        f"\n||  Clarify Q       : {intent.get('clarification_question')}"
        if intent.get("clarification_needed")
        else ""
    )

    log = (
        f"\n"
        f"|| ============================================================\n"
        f"||  UNDERSTANDING AGENT -- RESULT\n"
        f"|| ============================================================\n"
        f"||  Query          : {query[:80]}\n"
        f"||  Intent Type    : {intent.get('intent_type', 'UNKNOWN')}\n"
        f"||  Scope          : {scope_str}\n"
        f"||  Clarity        : {intent.get('clarity', 'UNKNOWN')}\n"
        f"||  Needs Search   : {intent.get('needs_search', False)}\n"
        f"||  Context Dep.   : {intent.get('context_dependency', 'UNKNOWN')}\n"
        f"||  Clarify Needed : {intent.get('clarification_needed', False)}"
        f"{clarification_str}\n"
        f"||  Summary        : {intent.get('summary', '--')}\n"
        f"|| ------------------------------------------------------------\n"
        f"||  ENTITIES EXTRACTED:\n"
        f"{entity_block}\n"
        f"||  Thinking Tokens (internal reasoning) : {thinking_tokens['thinking']:,}\n"
        f"||  Input Tokens   (prompt size)         : {thinking_tokens['input']:,}\n"
        f"||  Output Tokens  (answer size)         : {thinking_tokens['output']:,}\n"
        f"|| ============================================================"
    )
    logger.info(log)
    return log


# -- Format conversation history for prompt -----------------------------------

def _format_history(history: list) -> str:
    """Format conversation history into a readable string for the prompt."""
    if not history:
        return "No prior conversation."
    lines = []
    for msg in history[-6:]:           # last 3 turns = 6 messages max
        role = msg.get("role", "unknown").upper()
        content = str(msg.get("content", ""))[:300]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


# -- Main agent node ----------------------------------------------------------

async def understanding_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Understanding Agent.

    Reads:  state['user_query'], state['conversation_history']
    Writes: state['understood_intent'], state['understanding_log'],
            state['understanding_thinking_tokens'], state['agent_trace']
    """
    user_query = state.get("user_query", "").strip()
    history    = state.get("conversation_history", [])
    trace      = list(state.get("agent_trace", []))

    logger.info("=" * 66)
    logger.info("Understanding Agent -- START  |  query='%s'", user_query[:80])
    logger.info("=" * 66)

    # -- Log current conversation history so we can see context on every query --
    if history:
        logger.info("|| CONVERSATION HISTORY (%d turns):", len(history))
        for i, msg in enumerate(history):
            role    = msg.get("role", "unknown").upper()
            content = str(msg.get("content", ""))[:120]
            logger.info("||   [%d] %s: %s", i + 1, role, content)
    else:
        logger.info("|| CONVERSATION HISTORY: empty (first query in session)")
    logger.info("|" + "-" * 65)

    # -- Build messages for the model -----------------------------------------
    history_str   = _format_history(history)
    user_content  = UNDERSTANDING_USER_TEMPLATE.format(
        conversation_history=history_str,
        user_query=user_query,
    )

    messages = [
        SystemMessage(content=UNDERSTANDING_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    # -- Invoke the model -----------------------------------------------------
    try:
        model = _build_model()
        response = await model.ainvoke(messages)

        # Extract token counts from usage_metadata
        # In langchain_google_genai 4.2.0, thinking tokens are at:
        #   usage_metadata['output_token_details']['reasoning']  (NOT 'thinking_tokens')
        token_counts = {"thinking": 0, "input": 0, "output": 0}
        usage = getattr(response, "usage_metadata", None)
        if usage and isinstance(usage, dict):
            token_counts["input"]    = usage.get("input_tokens", 0) or 0
            token_counts["output"]   = usage.get("output_tokens", 0) or 0
            out_details = usage.get("output_token_details") or {}
            if isinstance(out_details, dict):
                token_counts["thinking"] = out_details.get("reasoning", 0) or 0

        # Parse JSON output — handle list content (thinking model returns list)
        raw_content = response.content
        if isinstance(raw_content, list):
            text_parts = [
                p.get("text", "") if isinstance(p, dict) else str(p)
                for p in raw_content
                if not (isinstance(p, dict) and p.get("type") == "thinking")
            ]
            raw_content = "".join(text_parts).strip()
        else:
            raw_content = str(raw_content).strip()

        # Strip markdown fences if model adds them despite instructions
        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]
        raw_content = raw_content.strip()

        understood_intent = json.loads(raw_content)

    except json.JSONDecodeError as jde:
        logger.error("JSON parse failed: %s | raw='%s'", jde, raw_content[:200])
        understood_intent = {
            "intent_type": "AMBIGUOUS",
            "scope": [],
            "entities": {
                "modules": [], "filters": {}, "count_requested": None,
                "is_aggregate": None, "group_by": None,
                "comparison_subjects": [], "date_range_raw": None,
            },
            "clarity": "LOW",
            "needs_search": False,
            "context_dependency": "INDEPENDENT",
            "clarification_needed": True,
            "clarification_question": "Could you please rephrase your question?",
            "summary": "Failed to parse understanding -- query may be unclear.",
        }
        token_counts = {"thinking": 0, "input": 0, "output": 0}

    except Exception as exc:
        logger.error("Understanding Agent error: %s", exc, exc_info=True)
        raise

    # -- Log and build trace entry --------------------------------------------
    log_str = _print_understanding_log(understood_intent, token_counts, user_query)
    trace.append(
        f"[UnderstandingAgent] intent={understood_intent.get('intent_type')} | "
        f"clarity={understood_intent.get('clarity')} | "
        f"scope={understood_intent.get('scope')} | "
        f"thinking_tokens={token_counts['thinking']} | input_tokens={token_counts['input']}"
    )

    return {
        **state,
        "understood_intent":             understood_intent,
        "understanding_log":             log_str,
        "understanding_thinking_tokens": token_counts["thinking"],
        "agent_trace":                   trace,
    }
