"""
Mini Validation Agent — Node 4 in the LangGraph multi-agent pipeline.

Responsibilities:
  - Validate that the Retrieval Agent fetched the right data for the user's query
  - Decide: PASS (proceed to execution), RETRY (re-fetch with instructions), FAIL
  - Provide specific, actionable retry instructions when validation fails
  - Never block indefinitely — respects max retry_count of 2

Model: gemini-2.5-flash with thinking enabled
"""

import json
from typing import Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.agents.prompts.validation_prompt import (
    VALIDATION_SYSTEM_PROMPT,
    VALIDATION_USER_TEMPLATE,
)
from app.agents.log_config import setup_agent_logger
from app.config import settings

logger = setup_agent_logger("validation_agent")

MAX_RETRIES = 2


# ── Model initialisation ──────────────────────────────────────────────────────

def _build_model() -> ChatGoogleGenerativeAI:
    """Build the Mini Validation Agent model with thinking enabled."""
    return ChatGoogleGenerativeAI(
        model=settings.MULTI_AGENT_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,          # required for thinking mode
        thinking_budget=2000,   # lower budget — validation is a focused decision
    )


# ── Console printer ───────────────────────────────────────────────────────────

def _print_validation_log(
    status: str,
    reason: str,
    retry_instructions: str,
    thinking_tokens: dict,
    query: str,
    retry_count: int,
) -> str:
    """Print a clean structured log block."""
    log = (
        f"\n"
        f"|| ============================================================\n"
        f"||  MINI VALIDATION AGENT -- RESULT\n"
        f"|| ============================================================\n"
        f"||  Query           : {query[:80]}\n"
        f"||  Validation      : {status}\n"
        f"||  Retry Count     : {retry_count}\n"
        f"||  Reason          : {reason}\n"
        f"||  Retry Instr.    : {(retry_instructions or 'N/A')[:120]}\n"
        f"||  Thinking Tokens : {thinking_tokens['thinking']:,}\n"
        f"||  Input Tokens    : {thinking_tokens['input']:,}\n"
        f"||  Output Tokens   : {thinking_tokens['output']:,}\n"
        f"|| ============================================================"
    )
    logger.info(log)
    return log


# ── Main agent node ───────────────────────────────────────────────────────────

async def validation_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Mini Validation Agent.

    Reads:  state['user_query'], state['understood_intent'], state['goal_plan'],
            state['retrieval_results'], state['retry_count']
    Writes: state['validation_status'], state['validation_reason'],
            state['retry_instructions'], state['validation_log'],
            state['validation_thinking_tokens'], state['retry_count'], state['agent_trace']
    """
    user_query        = state.get("user_query", "").strip()
    understood_intent = state.get("understood_intent", {}) or {}
    goal_plan         = state.get("goal_plan", {}) or {}
    retrieval_results = state.get("retrieval_results", []) or []
    retry_count       = state.get("retry_count", 0) or 0
    trace             = list(state.get("agent_trace", []))

    logger.info("-" * 66)
    logger.info(
        "Mini Validation Agent -- START | query='%s' | retry_count=%d",
        user_query[:80], retry_count
    )
    logger.info("-" * 66)

    # ── Short-circuit: DIRECT_ANSWER or CLARIFY doesn't need validation ───────
    approach = goal_plan.get("approach", "")
    if approach in ("DIRECT_ANSWER", "CLARIFY"):
        logger.info("|| Approach is %s — auto-PASS, no retrieval to validate", approach)
        log_str = _print_validation_log(
            status="PASS",
            reason=f"No retrieval was performed (approach={approach}). Proceeding to execution.",
            retry_instructions=None,
            thinking_tokens={"thinking": 0, "input": 0, "output": 0},
            query=user_query,
            retry_count=retry_count,
        )
        trace.append(f"[ValidationAgent] status=PASS (auto) | approach={approach} | thinking_tokens=0")
        return {
            **state,
            "validation_status":           "PASS",
            "validation_reason":           f"No retrieval needed for {approach}",
            "retry_instructions":          None,
            "validation_log":              log_str,
            "validation_thinking_tokens":  0,
            "agent_trace":                 trace,
        }

    # ── Pre-validation intention log ─────────────────────────────────────────
    approach       = goal_plan.get("approach", "?")
    results_count  = len(retrieval_results)
    has_data       = any(r.get("data") for r in retrieval_results)
    logger.info(
        "\n|| ============================================================\n"
        "||  MINI VALIDATION AGENT -- HOW I WILL VALIDATE\n"
        "|| ============================================================\n"
        "||  Goal Approach    : %s\n"
        "||  Retrieved Steps  : %d result(s) | Has Data: %s\n"
        "||  Retry Count So Far: %d / %d max\n"
        "||  I will check     : Did the retrieval tool fetch the RIGHT data?\n"
        "||                     Is the data relevant to answer the user query?\n"
        "||                     If empty — is 0 a valid answer or should I RETRY?\n"
        "||  Decision will be : PASS (proceed) | RETRY (re-fetch) | FAIL (give up)\n"
        "|| ============================================================",
        approach, results_count, has_data, retry_count, MAX_RETRIES
    )

    # ── Build prompt ──────────────────────────────────────────────────────────
    user_content = VALIDATION_USER_TEMPLATE.format(
        user_query=user_query,
        understood_intent=json.dumps(understood_intent, indent=2),
        goal_plan=json.dumps(goal_plan, indent=2),
        retrieval_results=json.dumps(retrieval_results, indent=2),
        retry_count=retry_count,
    )

    messages = [
        SystemMessage(content=VALIDATION_SYSTEM_PROMPT),
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

        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]
        raw_content = raw_content.strip()

        validation_result = json.loads(raw_content)
        v_status          = validation_result.get("validation_status", "PASS")
        v_reason          = validation_result.get("validation_reason", "")
        v_retry_instr     = validation_result.get("retry_instructions")

    except (json.JSONDecodeError, Exception) as exc:
        logger.error("Validation Agent error: %s", exc, exc_info=True)
        # On error, default to PASS so pipeline doesn't block
        v_status      = "PASS"
        v_reason      = "Validation agent encountered an error — defaulting to PASS"
        v_retry_instr = None
        token_counts  = {"thinking": 0, "input": 0, "output": 0}

    # ── Enforce max retry guard ───────────────────────────────────────────────
    if v_status == "RETRY" and retry_count >= MAX_RETRIES:
        logger.warning(
            "|| Max retries (%d) reached — overriding RETRY → PASS", MAX_RETRIES
        )
        v_status      = "PASS"
        v_reason      = f"Max retries ({MAX_RETRIES}) reached. Proceeding with available data. Original reason: {v_reason}"
        v_retry_instr = None

    # ── Update retry_count if we are retrying ─────────────────────────────────
    new_retry_count = retry_count + 1 if v_status == "RETRY" else retry_count

    log_str = _print_validation_log(
        status=v_status,
        reason=v_reason,
        retry_instructions=v_retry_instr,
        thinking_tokens=token_counts,
        query=user_query,
        retry_count=retry_count,
    )
    trace.append(
        f"[ValidationAgent] status={v_status} | retry_count={retry_count} | "
        f"thinking_tokens={token_counts['thinking']} | reason={v_reason[:60]}"
    )

    return {
        **state,
        "validation_status":          v_status,
        "validation_reason":          v_reason,
        "retry_instructions":         v_retry_instr,
        "retry_count":                new_retry_count,
        "validation_log":             log_str,
        "validation_thinking_tokens": token_counts["thinking"],
        "agent_trace":                trace,
    }
