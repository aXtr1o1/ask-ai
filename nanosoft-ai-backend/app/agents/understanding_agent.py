"""
Understanding Agent -- Node 1 in the LangGraph multi-agent pipeline.

Responsibilities:
  - Deeply understand the user's query in the facility management context
  - Extract ALL relevant filters from the full module schemas (ASSETS/PPM/BDM/FA/SB)
  - Determine intent type, scope, entities, clarity, and context dependency
  - When needs_search=True: perform Google Search grounding and store the summary
    in state['web_search_summary'] so downstream agents can use it
  - Produce structured JSON output consumed by the Goal Planning Agent
  - Log a clean, structured summary including WHY each module was excluded

Model: gemini-2.5-flash with thinking enabled
"""

import json
import time

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.agents.prompts.understanding_prompt import (
    UNDERSTANDING_SYSTEM_PROMPT,
    UNDERSTANDING_USER_TEMPLATE,
)
# WHY: shared helpers from log_config avoid copy-pasting identical logic in every agent.
# extract_token_counts  -> extracts thinking/input/output from response.usage_metadata
# parse_llm_text        -> strips thinking-block parts from the model's content list
# strip_json_fences     -> removes ```json ... ``` fences the model sometimes adds
from app.agents.log_config import (
    setup_agent_logger,
    extract_token_counts,
    parse_llm_text,
    strip_json_fences,
)
from app.config import settings

logger = setup_agent_logger("understanding_agent")


# ── Model initialisation ──────────────────────────────────────────────────────

def _build_model() -> ChatGoogleGenerativeAI:
    """
    Build the Understanding Agent model with thinking enabled.

    WHY thinking_budget=3000:
      This agent needs to reason about which of the 5 FM modules applies, which
      filters to extract, whether context from history is relevant, and whether
      external knowledge is needed. 3000 thinking tokens gives enough budget for
      multi-module queries without over-spending on simple conversational queries.
    """
    return ChatGoogleGenerativeAI(
        model=settings.MULTI_AGENT_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,          # WHY: required for thinking mode (Gemini constraint)
        thinking_budget=3000,
    )


def _build_search_model() -> ChatGoogleGenerativeAI:
    """
    Build a model WITHOUT thinking for the Google Search grounding call.

    WHY no thinking here:
      The grounding call is purely for retrieving external factual content
      (FM regulations, standards, manufacturer specs). Thinking mode on a
      search-grounded call wastes tokens — the model just needs to summarise
      what Google returns. Thinking is only useful for complex reasoning.
    """
    return ChatGoogleGenerativeAI(
        model=settings.MULTI_AGENT_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0,
    )


# ── Console log printer ───────────────────────────────────────────────────────

def _print_understanding_log(
    intent: dict,
    thinking_tokens: dict,
    query: str,
    web_search_summary: str | None,
) -> str:
    """
    Print a clean structured log block that shows:
      - What the agent understood (intent, scope, clarity)
      - Which entities / filters were extracted
      - WHY each non-selected module was excluded (modules_excluded_reason)
      - Whether web search ran and what it found
      - Token usage breakdown

    WHY show excluded modules:
      Without omission reasoning a developer reading the log cannot tell if
      BDM was excluded because the query didn't mention complaints, or because
      the model made an error. The 'modules_excluded_reason' field makes every
      routing decision auditable.
    """
    scope_str = ", ".join(intent.get("scope", [])) or "Undetermined"
    modules   = intent.get("entities", {}).get("modules", [])
    filters   = intent.get("entities", {}).get("filters", {}) or {}
    count_req = intent.get("entities", {}).get("count_requested")
    is_agg    = intent.get("entities", {}).get("is_aggregate")
    group_by  = intent.get("entities", {}).get("group_by")
    date_raw  = intent.get("entities", {}).get("date_range_raw")

    # ── Build extracted entity lines ─────────────────────────────────────────
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

    # ── Build module-selection reasoning block ─────────────────────────────────
    # One crisp sentence per module: selected modules get the "chosen" reason,
    # excluded modules get their exclusion reason — all in a flat readable list.
    excluded_reasons = intent.get("modules_excluded_reason") or {}
    all_modules = ["ASSETS", "PPM", "BDM", "FA", "SB"]
    selected    = set(modules)

    module_lines = []
    for mod in all_modules:
        if mod in selected:
            chosen_reason = excluded_reasons.get(mod, "matched the query context")
            module_lines.append(f"||    ✓ {mod:<8}: {chosen_reason}")
        else:
            excl_reason = excluded_reasons.get(mod, "not relevant to this query")
            module_lines.append(f"||    ✗ {mod:<8}: {excl_reason}")

    module_block = "\n".join(module_lines)

    # ── Web search summary block ──────────────────────────────────────────────
    if web_search_summary:
        ws_preview = web_search_summary[:200].replace("\n", " ")
        web_block = (
            f"|| ------------------------------------------------------------\n"
            f"||  WEB SEARCH RESULT (first 200 chars):\n"
            f"||    {ws_preview}{'...' if len(web_search_summary) > 200 else ''}"
        )
    else:
        web_block = "||  WEB SEARCH: not required for this query"

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
        f"|| ------------------------------------------------------------\n"
        f"||  MODULE SELECTION (\u2713 chosen | \u2717 not chosen):\n"
        f"{module_block}\n"
        f"|| ------------------------------------------------------------\n"
        f"{web_block}\n"
        f"|| ------------------------------------------------------------\n"
        f"||  Thinking Tokens (internal reasoning) : {thinking_tokens['thinking']:,}\n"
        f"||  Input Tokens   (prompt size)         : {thinking_tokens['input']:,}\n"
        f"||  Output Tokens  (answer size)         : {thinking_tokens['output']:,}\n"
        f"|| ============================================================"
    )
    logger.info(log)
    return log


# ── Format conversation history for prompt ────────────────────────────────────

def _format_history(history: list) -> str:
    """
    Format conversation history into a readable string for the prompt.

    WHY last 6 messages only:
      Conversation history can grow indefinitely. Sending the full history
      would inflate token usage on every query. 6 messages = 3 turns = enough
      context for follow-up queries ("give me 5 of them", "show closed ones")
      without sending unnecessary context from much earlier turns.
    """
    if not history:
        return "No prior conversation."
    lines = []
    for msg in history[-6:]:
        role    = msg.get("role", "unknown").upper()
        content = str(msg.get("content", ""))[:300]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


# ── Google Search grounding ───────────────────────────────────────────────────

async def _run_web_search(query: str) -> str:
    """
    Perform a Google Search grounding call using the google-genai SDK.

    WHY this happens in the Understanding Agent (not Retrieval Agent):
      The original design had web search in Node 3 (Retrieval Agent). Moving it
      to Node 1 (Understanding Agent) means:
        1. The web summary is available to ALL downstream agents — Goal Planning
           can factor it into the approach, Execution can cite it in the answer.
        2. The Retrieval Agent stays focused on DB tool calls only.
        3. We avoid running web search AFTER tool retrieval (which could cause
           conflicting data vs. fresh context).

    WHY google-genai SDK directly (not langchain_google_genai.tools):
      GoogleSearchRetrieval was removed from langchain-google-genai in v2+.
      The correct approach in langchain-google-genai >= 4.x is to use the
      google.genai client with tools=[GoogleSearch()] directly.

    Returns:
      A text summary of relevant external information, or a fallback message.
    """
    try:
        import asyncio
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GOOGLE_API_KEY)

        search_prompt = (
            f"Search for information relevant to this facility management query: {query}\n"
            f"Provide a concise, factual summary of the most relevant findings."
        )

        # WHY run_in_executor: google.genai client is synchronous — calling it
        # directly in an async context blocks the entire event loop for all requests.
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=settings.MULTI_AGENT_MODEL,
                contents=search_prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
        )

        # Extract text parts (skip grounding metadata parts)
        summary = ""
        if response.candidates:
            for part in (response.candidates[0].content.parts or []):
                if hasattr(part, "text") and part.text:
                    summary += part.text

        summary = summary.strip()
        logger.info(
            "|| [WebSearch] Google Search grounding complete | summary_len=%d chars",
            len(summary),
        )
        return summary or "Web search returned no relevant results."

    except Exception as exc:
        logger.error("|| [WebSearch] Google Search grounding failed: %s", exc, exc_info=True)
        return f"Web search failed: {exc}"



# ── Fallback intent (used when model call or JSON parse fails) ────────────────

def _fallback_intent() -> dict:
    """
    Return a safe default intent when the model call or JSON parse fails.

    WHY AMBIGUOUS / LOW / clarification_needed=True:
      If the model crashes or returns unparseable JSON, we must not block the
      pipeline. Returning AMBIGUOUS with clarification_needed=True sends the
      query to the Execution Agent which will ask the user to rephrase — the
      safest possible recovery without crashing the whole request.
    """
    return {
        "intent_type":    "AMBIGUOUS",
        "scope":          [],
        "entities": {
            "modules": [], "filters": {}, "count_requested": None,
            "is_aggregate": None, "group_by": None,
            "comparison_subjects": [], "date_range_raw": None,
        },
        "clarity":                 "LOW",
        "needs_search":            False,
        "context_dependency":      "INDEPENDENT",
        "clarification_needed":    True,
        "clarification_question":  "Could you please rephrase your question?",
        "summary":                 "Failed to parse understanding — query may be unclear.",
        "modules_excluded_reason": {},
        "web_search_summary":      None,
    }


# ── Main agent node ───────────────────────────────────────────────────────────

async def understanding_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Understanding Agent.

    Reads:  state['user_query'], state['conversation_history']
    Writes: state['understood_intent'], state['understanding_log'],
            state['understanding_thinking_tokens'], state['web_search_summary'],
            state['agent_trace'], state['latency_understanding']

    WHY this is Node 1 (before Goal Planning):
      The Goal Planning Agent needs to know the intent type, scope, and
      extracted filters before it can decide which approach to use (DATA_QUERY
      vs DIRECT_ANSWER vs CLARIFY). Understanding must run first.
    """
    _t_start   = time.perf_counter()
    user_query = state.get("user_query", "").strip()
    history    = state.get("conversation_history", [])
    trace      = list(state.get("agent_trace", []))

    logger.info("=" * 66)
    logger.info("Understanding Agent -- START  |  query='%s'", user_query[:80])
    logger.info("=" * 66)

    # ── Log conversation history so context is visible per-query ──────────────
    # WHY log history here: when debugging a follow-up query that gives wrong
    # results, you need to see exactly what prior context the agent received.
    if history:
        logger.info("|| CONVERSATION HISTORY (%d turns):", len(history))
        for i, msg in enumerate(history):
            role    = msg.get("role", "unknown").upper()
            content = str(msg.get("content", ""))[:120]
            logger.info("||   [%d] %s: %s", i + 1, role, content)
    else:
        logger.info("|| CONVERSATION HISTORY: empty (first query in session)")
    logger.info("|" + "-" * 65)

    # ── Build messages for the model ──────────────────────────────────────────
    history_str  = _format_history(history)
    from datetime import date as _date
    today_str    = _date.today().strftime("%Y-%m-%d")
    user_content = UNDERSTANDING_USER_TEMPLATE.format(
        today=today_str,
        conversation_history=history_str,
        user_query=user_query,
    )
    messages = [
        SystemMessage(content=UNDERSTANDING_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    # ── Call the model ────────────────────────────────────────────────────────
    web_search_summary = None
    try:
        model    = _build_model()
        response = await model.ainvoke(messages)

        # WHY use shared helpers: see log_config.py for detailed explanations
        token_counts      = extract_token_counts(response)
        raw_text          = parse_llm_text(response)
        raw_text          = strip_json_fences(raw_text)
        understood_intent = json.loads(raw_text)

        # ── Optional second pass: Google Search grounding ─────────────────────
        # WHY second pass (not same call):
        #   The first call uses thinking mode to reason about the query structure.
        #   Mixing thinking mode with tool use (Google Search) in a single call
        #   is unreliable — the model may skip tool use when thinking is enabled.
        #   A separate targeted search call keeps both capabilities clean.
        if understood_intent.get("needs_search"):
            logger.info(
                "|| [WebSearch] needs_search=True — running Google Search grounding"
            )
            web_search_summary = await _run_web_search(user_query)
            # Store in the intent dict so downstream agents can read it from
            # state['understood_intent']['web_search_summary'] if needed
            understood_intent["web_search_summary"] = web_search_summary
        else:
            understood_intent["web_search_summary"] = None

    except json.JSONDecodeError as jde:
        logger.error(
            "|| JSON parse failed: %s | raw='%s'", jde,
            raw_text[:200] if "raw_text" in dir() else "N/A",
        )
        understood_intent = _fallback_intent()
        token_counts = {"thinking": 0, "input": 0, "output": 0}

    except Exception as exc:
        logger.error("|| Understanding Agent error: %s", exc, exc_info=True)
        raise

    # ── Latency ──────────────────────────────────────────────────────────────
    latency = round(time.perf_counter() - _t_start, 3)
    logger.info("|| [UnderstandingAgent] latency=%.3f s", latency)

    # ── Print structured log and build pipeline trace entry ───────────────────
    log_str = _print_understanding_log(
        understood_intent, token_counts, user_query, web_search_summary
    )
    trace.append(
        f"[UnderstandingAgent] intent={understood_intent.get('intent_type')} | "
        f"clarity={understood_intent.get('clarity')} | "
        f"scope={understood_intent.get('scope')} | "
        f"needs_search={understood_intent.get('needs_search', False)} | "
        f"thinking_tokens={token_counts['thinking']} | "
        f"input_tokens={token_counts['input']} | "
        f"latency={latency:.3f}s"
    )

    return {
        **state,
        "understood_intent":             understood_intent,
        "understanding_log":             log_str,
        "understanding_thinking_tokens": token_counts["thinking"],
        "total_input_tokens":            state.get("total_input_tokens", 0) + token_counts["input"],
        "total_output_tokens":           state.get("total_output_tokens", 0) + token_counts["output"],
        "total_thinking_tokens":         state.get("total_thinking_tokens", 0) + token_counts["thinking"],
        "web_search_summary":            web_search_summary,
        "latency_understanding":         latency,
        "agent_trace":                   trace,
    }
