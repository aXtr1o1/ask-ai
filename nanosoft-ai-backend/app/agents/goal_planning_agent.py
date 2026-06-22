"""
Goal Planning Agent — Node 2 in the LangGraph multi-agent pipeline.

Responsibilities:
  - Receive the structured understanding from the Understanding Agent
  - Determine the best approach and execution plan to satisfy the user's intent
  - Produce analytically rich execution steps including analysis_instruction per step
  - Log a clean, structured summary to the console

Model: gemini-2.5-flash with thinking enabled
"""

import json

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.agents.prompts.goal_planning_prompt import (
    GOAL_PLANNING_SYSTEM_PROMPT,
    GOAL_PLANNING_USER_TEMPLATE,
)
from app.agents.log_config import setup_agent_logger
from app.config import settings

logger = setup_agent_logger("goal_planning_agent")


# ── Model initialisation ──────────────────────────────────────────────────────

def _build_model() -> ChatGoogleGenerativeAI:
    """Build the Goal Planning Agent model with thinking enabled."""
    return ChatGoogleGenerativeAI(
        model=settings.MULTI_AGENT_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,          # required for thinking mode
        thinking_budget=5000,   # correct kwarg for langchain_google_genai
    )


# ── Console printer ───────────────────────────────────────────────────────────

def _print_goal_log(plan: dict, thinking_tokens: dict, query: str) -> str:
    """Print a clean structured log block. No emojis."""
    steps = plan.get("execution_steps", [])

    # Build step lines
    step_lines = []
    for step in steps:
        mode = step.get("execution_mode", "sequential")
        mode_icon = {"sequential": "->", "parallel": "=>", "conditional": "?>"}.get(mode, "->")
        analysis = step.get("analysis_instruction", "")
        step_lines.append(
            f"||    Step {step.get('step_number', '?')} {mode_icon} {step.get('action', '')}\n"
            f"||              Reason   : {step.get('reason', '')}\n"
            f"||              Analysis : {analysis[:120]}{'...' if len(analysis) > 120 else ''}"
        )
    steps_str = "\n".join(step_lines) if step_lines else "||    (no steps)"

    tools_str = ", ".join(plan.get("tools_required", [])) or "None"

    clarification_str = (
        f"\n||  Clarification Q    : {plan.get('clarification_question')}"
        if plan.get("needs_clarification")
        else ""
    )

    notes_str = (
        f"\n||  Planning Notes     : {plan.get('planning_notes')}"
        if plan.get("planning_notes")
        else ""
    )

    log = (
        f"\n"
        f"|| ============================================================\n"
        f"||  GOAL PLANNING AGENT -- RESULT\n"
        f"|| ============================================================\n"
        f"||  Query              : {query[:80]}\n"
        f"||  Approach           : {plan.get('approach', 'UNKNOWN')}\n"
        f"||  Tools Required     : {tools_str}\n"
        f"||  Requires DB Query  : {plan.get('requires_db_query', False)}\n"
        f"||  Requires Search    : {plan.get('requires_web_search', False)}\n"
        f"||  Needs Clarify      : {plan.get('needs_clarification', False)}"
        f"{clarification_str}\n"
        f"||  Complexity         : {plan.get('estimated_complexity', 'UNKNOWN')}"
        f"{notes_str}\n"
        f"|| ------------------------------------------------------------\n"
        f"||  EXECUTION PLAN:\n"
        f"{steps_str}\n"
        f"||  Thinking Tokens (internal reasoning) : {thinking_tokens['thinking']:,}\n"
        f"||  Input Tokens   (prompt size)         : {thinking_tokens['input']:,}\n"
        f"||  Output Tokens  (answer size)         : {thinking_tokens['output']:,}\n"
        f"|| ============================================================"
    )
    logger.info(log)
    return log


# ── Main agent node ───────────────────────────────────────────────────────────

async def goal_planning_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Goal Planning Agent.

    Reads:  state['understood_intent'], state['user_query']
    Writes: state['goal_plan'], state['goal_log'],
            state['goal_thinking_tokens'], state['agent_trace']
    """
    user_query        = state.get("user_query", "").strip()
    understood_intent = state.get("understood_intent", {})
    history           = state.get("conversation_history", [])
    trace             = list(state.get("agent_trace", []))

    logger.info("-" * 66)
    logger.info("Goal Planning Agent -- START  |  query='%s'", user_query[:80])
    logger.info("-" * 66)

    if not understood_intent:
        logger.warning("No understood_intent in state -- planning with empty context")
        understood_intent = {}

    # ── Format conversation history for the prompt ─────────────────────────────
    history_lines = []
    for msg in history[-6:]:          # last 3 turns max
        role    = msg.get("role", "unknown").upper()
        content = str(msg.get("content", ""))[:400]
        history_lines.append(f"{role}: {content}")
    history_str = "\n".join(history_lines) if history_lines else "No prior conversation."

    # ── Build messages for the model ──────────────────────────────────────────
    intent_json_str = json.dumps(understood_intent, indent=2)
    user_content = GOAL_PLANNING_USER_TEMPLATE.format(
        conversation_history=history_str,
        understood_intent=intent_json_str,
        user_query=user_query,
    )

    messages = [
        SystemMessage(content=GOAL_PLANNING_SYSTEM_PROMPT),   # FIX: use the rich system prompt
        HumanMessage(content=user_content),
    ]

    # ── Invoke the model ──────────────────────────────────────────────────────
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

        # ── Parse JSON output ─────────────────────────────────────────────────
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

        # Strip markdown fences if model adds them
        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]
        raw_content = raw_content.strip()

        goal_plan = json.loads(raw_content)

    except json.JSONDecodeError as jde:
        logger.error("JSON parse failed: %s | raw='%s'", jde, raw_content[:200])
        goal_plan = {
            "approach": "CLARIFY",
            "tools_required": [],
            "execution_steps": [
                {
                    "step_number": 1,
                    "action": "Ask user to clarify their request",
                    "reason": "Planning agent could not parse a clear execution path",
                    "analysis_instruction": "Ask the user to rephrase their question more clearly.",
                    "execution_mode": "sequential",
                    "depends_on": [],
                }
            ],
            "requires_web_search": False,
            "requires_db_query": False,
            "needs_clarification": True,
            "clarification_question": "Could you provide more details about what you need?",
            "estimated_complexity": "SIMPLE",
            "planning_notes": "Fallback plan due to parse error.",
        }
        token_counts = {"thinking": 0, "input": 0, "output": 0}

    except Exception as exc:
        logger.error("Goal Planning Agent error: %s", exc, exc_info=True)
        raise

    # ── Log and build trace entry ─────────────────────────────────────────────
    log_str = _print_goal_log(goal_plan, token_counts, query=user_query)
    trace.append(
        f"[GoalPlanningAgent] approach={goal_plan.get('approach')} | "
        f"tools={goal_plan.get('tools_required')} | "
        f"complexity={goal_plan.get('estimated_complexity')} | "
        f"thinking_tokens={token_counts['thinking']} | input_tokens={token_counts['input']}"
    )

    return {
        **state,
        "goal_plan":            goal_plan,
        "goal_log":             log_str,
        "goal_thinking_tokens": token_counts["thinking"],
        "agent_trace":          trace,
    }
