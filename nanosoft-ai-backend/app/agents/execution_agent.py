"""
Execution Agent — Node 5 (Final) in the LangGraph multi-agent pipeline.

Responsibilities:
  - Receive validated retrieval results from the Mini Validation Agent
  - Reason deeply over the data using the Goal Planning Agent's analysis_instruction
  - Identify which fields in the returned records are relevant to the user's question
  - Produce a complete, intelligent natural language answer
  - Log a clean, structured summary to the console

Model: gemini-2.5-flash with thinking enabled (highest budget — this is the most important step)
"""

import json
from typing import Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.agents.prompts.execution_prompt import (
    EXECUTION_SYSTEM_PROMPT,
    EXECUTION_USER_TEMPLATE,
)
from app.agents.log_config import setup_agent_logger
from app.config import settings

logger = setup_agent_logger("execution_agent")


# ── Model initialisation ──────────────────────────────────────────────────────

def _build_model() -> ChatGoogleGenerativeAI:
    """Build the Execution Agent model with thinking enabled — highest budget."""
    return ChatGoogleGenerativeAI(
        model=settings.MULTI_AGENT_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,          # required for thinking mode
        thinking_budget=8000,   # highest budget — this agent produces the final answer
    )


# ── Console printer ───────────────────────────────────────────────────────────

def _print_execution_log(
    final_answer: str,
    thinking_tokens: dict,
    query: str,
    validation_status: str,
) -> str:
    """Print a clean structured log block."""
    answer_preview = final_answer[:200].replace("\n", " ")
    if len(final_answer) > 200:
        answer_preview += "..."

    log = (
        f"\n"
        f"|| ============================================================\n"
        f"||  EXECUTION AGENT -- RESULT\n"
        f"|| ============================================================\n"
        f"||  Query            : {query[:80]}\n"
        f"||  Validation Status: {validation_status}\n"
        f"||  Answer Preview   : {answer_preview}\n"
        f"||  Answer Length    : {len(final_answer)} chars\n"
        f"||  Thinking Tokens  : {thinking_tokens['thinking']:,}\n"
        f"||  Input Tokens     : {thinking_tokens['input']:,}\n"
        f"||  Output Tokens    : {thinking_tokens['output']:,}\n"
        f"|| ============================================================"
    )
    logger.info(log)
    return log


# ── Main agent node ───────────────────────────────────────────────────────────

async def execution_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Execution Agent.

    Reads:  state['user_query'], state['understood_intent'], state['goal_plan'],
            state['retrieval_results'], state['validation_status']
    Writes: state['final_answer'], state['execution_log'],
            state['execution_thinking_tokens'], state['agent_trace']
    """
    user_query        = state.get("user_query", "").strip()
    understood_intent = state.get("understood_intent", {}) or {}
    goal_plan         = state.get("goal_plan", {}) or {}
    # Use filtered_results if available (set by Filtering Agent), else fall back to raw
    retrieval_results = state.get("filtered_results") or state.get("retrieval_results", []) or []
    validation_status = state.get("validation_status", "PASS")
    trace             = list(state.get("agent_trace", []))

    logger.info("=" * 66)
    logger.info("Execution Agent -- START | query='%s' | validation=%s", user_query[:80], validation_status)
    logger.info("=" * 66)

    # ── Pre-execution intention log ─────────────────────────────────────────
    approach          = goal_plan.get("approach", "?")
    complexity        = goal_plan.get("complexity", "?")
    data_count        = sum(len(r.get("data") or []) for r in retrieval_results)
    analysis_instr    = ""
    for step in (goal_plan.get("steps") or []):
        if step.get("analysis_instruction"):
            analysis_instr = step["analysis_instruction"][:120]
            break
    logger.info(
        "\n|| ============================================================\n"
        "||  EXECUTION AGENT -- HOW I WILL EXECUTE\n"
        "|| ============================================================\n"
        "||  Validation Status : %s\n"
        "||  Goal Approach     : %s | Complexity: %s\n"
        "||  Data Received     : %d record(s) from retrieval\n"
        "||  Analysis Goal     : %s\n"
        "||  I will            : Read the retrieved data carefully\n"
        "||                      Apply the analysis goal to find the answer\n"
        "||                      Write a clear, natural language response\n"
        "|| ============================================================",
        validation_status, approach, complexity, data_count,
        analysis_instr or "(produce a direct answer from retrieved data)"
    )

    # ── Build prompt ──────────────────────────────────────────────────────────
    user_content = EXECUTION_USER_TEMPLATE.format(
        user_query=user_query,
        understood_intent=json.dumps(understood_intent, indent=2),
        goal_plan=json.dumps(goal_plan, indent=2),
        retrieval_results=json.dumps(retrieval_results, indent=2),
    )

    messages = [
        SystemMessage(content=EXECUTION_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    # ── Invoke model ──────────────────────────────────────────────────────────
    try:
        model = _build_model()
        response = await model.ainvoke(messages)

        # Extract token counts from usage_metadata
        # In langchain_google_genai 4.2.0, thinking tokens are at:
        #   usage_metadata['output_token_details']['reasoning']
        token_counts = {"thinking": 0, "input": 0, "output": 0}
        usage = getattr(response, "usage_metadata", None)
        if usage and isinstance(usage, dict):
            token_counts["input"]    = usage.get("input_tokens", 0) or 0
            token_counts["output"]   = usage.get("output_tokens", 0) or 0
            out_details = usage.get("output_token_details") or {}
            if isinstance(out_details, dict):
                token_counts["thinking"] = out_details.get("reasoning", 0) or 0

        # Execution agent outputs plain text (not JSON)
        raw_content = response.content
        if isinstance(raw_content, list):
            text_parts = [
                p.get("text", "") if isinstance(p, dict) else str(p)
                for p in raw_content
                if not (isinstance(p, dict) and p.get("type") == "thinking")
            ]
            final_answer = "".join(text_parts).strip()
        else:
            final_answer = str(raw_content).strip()

    except Exception as exc:
        logger.error("Execution Agent error: %s", exc, exc_info=True)
        final_answer = (
            "I encountered an error while generating the response. "
            "Please try again or rephrase your question."
        )
        token_counts = {"thinking": 0, "input": 0, "output": 0}

    # ── Log and trace ─────────────────────────────────────────────────────────
    log_str = _print_execution_log(
        final_answer=final_answer,
        thinking_tokens=token_counts,
        query=user_query,
        validation_status=validation_status,
    )
    trace.append(
        f"[ExecutionAgent] answer_len={len(final_answer)} | "
        f"thinking_tokens={token_counts['thinking']} | input_tokens={token_counts['input']}"
    )

    return {
        **state,
        "final_answer":               final_answer,
        "execution_log":              log_str,
        "execution_thinking_tokens":  token_counts["thinking"],
        "agent_trace":                trace,
    }
