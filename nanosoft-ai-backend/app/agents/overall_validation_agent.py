"""
Overall Validation Agent — Node 7 in the LangGraph multi-agent pipeline.

Responsibilities:
  - Evaluate the ENTIRE pipeline end-to-end (not just retrieval)
  - Check that understanding, planning, retrieval, filtering, and execution all worked correctly
  - Assign a confidence score 0-10 on the quality of the final answer
  - If score < 7 and retries < MAX_RETRIES → send the answer back to execution_agent
    with specific override_instructions to improve it
  - If score >= 7 or max retries reached → forward to formatting_agent

WHY this is different from mini_validation_agent:
  mini_validation_agent  → checks ONLY if Retrieval Agent fetched the right data.
                           Its RETRY loops back to retrieval_agent (re-fetch the data).
  overall_validation_agent → checks the FINAL ANSWER quality across ALL agents.
                             Its RETRY loops back to execution_agent (re-generate the answer,
                             same data, better instructions). No new DB calls needed.

WHY MAX_RETRIES = 2 (same as mini_validation):
  Two attempts to improve the answer is enough. After 2 retries we proceed to
  formatting_agent with the best answer produced so far.

Model: gemini-2.5-flash with thinking enabled (thinking_budget=3000)
"""

import json
import time
from typing import Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.agents.prompts.overall_validation_prompt import (
    OVERALL_VALIDATION_SYSTEM_PROMPT,
    OVERALL_VALIDATION_USER_TEMPLATE,
)
# WHY these helpers: see log_config.py for detailed explanations.
from app.agents.log_config import (
    setup_agent_logger,
    extract_token_counts,
    parse_llm_text,
    strip_json_fences,
)
from app.config import settings

logger = setup_agent_logger("overall_validation_agent")

MAX_RETRIES = 2


# ── Model initialisation ──────────────────────────────────────────────────────

def _build_model() -> ChatGoogleGenerativeAI:
    """
    Build the Overall Validation Agent model with moderate thinking budget.

    WHY thinking_budget=3000 (between mini_validation's 2000 and execution's 8000):
      This agent evaluates 5 agents' outputs — more context than mini_validation —
      but it only produces a JSON score + reason, not a full natural language answer.
      3000 thinking tokens gives it enough reasoning depth without over-spending.
    """
    return ChatGoogleGenerativeAI(
        model=settings.MULTI_AGENT_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,          # required for thinking mode (Gemini constraint)
        thinking_budget=3000,
    )


# ── Console printer ───────────────────────────────────────────────────────────

def _print_overall_validation_log(
    status: str,
    score: int,
    reason: str,
    plan_fix_instructions: str,
    token_counts: dict,
    query: str,
    overall_retry_count: int,
) -> str:
    """Print a clean structured log block matching the || format of all other agents."""
    log = (
        f"\n"
        f"|| ============================================================\n"
        f"||  OVERALL VALIDATION AGENT -- RESULT\n"
        f"|| ============================================================\n"
        f"||  Query                : {query[:80]}\n"
        f"||  Overall Status       : {status}\n"
        f"||  Confidence Score     : {score}/10\n"
        f"||  Overall Retry Count  : {overall_retry_count}\n"
        f"||  Reason               : {reason[:200]}\n"
        f"||  Plan Fix Instr.      : {(plan_fix_instructions or 'N/A')[:120]}\n"
        f"||  Thinking Tokens      : {token_counts['thinking']:,}\n"
        f"||  Input Tokens         : {token_counts['input']:,}\n"
        f"||  Output Tokens        : {token_counts['output']:,}\n"
        f"|| ============================================================"
    )
    logger.info(log)
    return log


# ── Main agent node ───────────────────────────────────────────────────────────

async def overall_validation_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Overall Validation Agent.

    Reads:  state['user_query'], state['understood_intent'], state['goal_plan'],
            state['filtered_results'], state['retrieval_results'],
            state['final_answer'], state['overall_retry_count']
    Writes: state['overall_validation_status'], state['overall_confidence_score'],
            state['overall_validation_reason'], state['overall_retry_instructions'],
            state['overall_retry_count'], state['overall_validation_log'],
            state['overall_validation_thinking_tokens'], state['agent_trace']
    """
    user_query           = state.get("user_query", "").strip()
    understood_intent    = state.get("understood_intent", {}) or {}
    goal_plan            = state.get("goal_plan", {}) or {}
    # WHY prefer filtered_results: same reason as execution_agent.
    # Filtered results have already had irrelevant columns removed.
    retrieval_results    = state.get("filtered_results") or state.get("retrieval_results", []) or []
    final_answer         = state.get("final_answer", "") or ""
    overall_retry_count  = state.get("overall_retry_count", 0) or 0
    trace                = list(state.get("agent_trace", []))

    logger.info("=" * 66)
    logger.info(
        "Overall Validation Agent -- START | query='%s' | overall_retry=%d",
        user_query[:80], overall_retry_count,
    )
    logger.info("=" * 66)
    _t_start = time.perf_counter()

    # ── Pre-validation intention log ─────────────────────────────────────────
    logger.info(
        "\n|| ============================================================\n"
        "||  OVERALL VALIDATION AGENT -- HOW I WILL VALIDATE\n"
        "|| ============================================================\n"
        "||  Overall Retry Count: %d / %d max\n"
        "||  Final Answer Length: %d chars\n"
        "||  I will check       : Did understanding_agent parse intent correctly?\n"
        "||                       Did goal_planning_agent plan the right steps?\n"
        "||                       Did retrieval_agent fetch the right data?\n"
        "||                       Did filtering_agent keep the right fields?\n"
        "||                       Does final_answer correctly answer the user query?\n"
        "||  Score (0-10)       : >= 7 = PASS | < 7 = RETRY (if retries < %d)\n"
        "|| ============================================================",
        overall_retry_count, MAX_RETRIES, len(final_answer), MAX_RETRIES
    )

    # ── Build a compact retrieval summary for the prompt ─────────────────────
    # WHY: We do not want to send 11,000 raw records into the validation prompt.
    # The overall validation agent only needs to understand what was retrieved,
    # not read every individual record.
    lean_results = []
    for r in retrieval_results:
        data = r.get("data") or {}
        if isinstance(data, dict):
            p_list   = data.get("p_list") or data.get("p_list_sample") or []
            p_count  = data.get("p_count", 0)
            summary  = data.get("_summary")
            lean_results.append({
                "step":        r.get("step"),
                "tool":        r.get("tool"),
                "filters":     r.get("filters"),
                "p_count":     p_count,
                "sample":      p_list[:3] if p_list else [],
                "_aggregated": data.get("_aggregated", False),
                "_summary":    summary,
            })
        elif isinstance(data, list):
            lean_results.append({
                "step":    r.get("step"),
                "tool":    r.get("tool"),
                "filters": r.get("filters"),
                "count":   len(data),
                "sample":  data[:3],
            })

    user_content = OVERALL_VALIDATION_USER_TEMPLATE.format(
        user_query=user_query,
        understood_intent=json.dumps(understood_intent, indent=2),
        goal_plan=json.dumps(goal_plan, indent=2),
        retrieval_results=json.dumps(lean_results, indent=2),
        final_answer=final_answer[:3000],   # cap to avoid token overflow on huge answers
        overall_retry_count=overall_retry_count,
    )

    messages = [
        SystemMessage(content=OVERALL_VALIDATION_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    # ── Invoke model ──────────────────────────────────────────────────────────
    try:
        model    = _build_model()
        response = await model.ainvoke(messages)

        token_counts   = extract_token_counts(response)
        raw_text       = parse_llm_text(response)
        raw_text       = strip_json_fences(raw_text)
        result_json    = json.loads(raw_text)

        ov_status       = result_json.get("overall_validation_status", "PASS")
        ov_score        = int(result_json.get("confidence_score", 7))
        ov_reason       = result_json.get("validation_reason", "")
        # WHY plan_fix_instructions (not override_instructions):
        #   The prompt now asks the LLM for plan_fix_instructions — specific guidance
        #   for the Goal Planning Agent on what to re-plan and why.
        #   This replaces the old override_instructions (which targeted execution_agent).
        ov_plan_fix     = result_json.get("plan_fix_instructions")

    except (json.JSONDecodeError, Exception) as exc:
        logger.error("Overall Validation Agent error: %s", exc, exc_info=True)
        # WHY default PASS on error: same reasoning as mini_validation_agent.
        # If this agent crashes, we must not block the pipeline. Let formatting_agent
        # handle whatever answer is available.
        ov_status    = "PASS"
        ov_score     = 7
        ov_reason    = "Overall validation agent encountered an error — defaulting to PASS"
        ov_plan_fix  = None
        token_counts = {"thinking": 0, "input": 0, "output": 0}

    # ── Enforce max retry guard ───────────────────────────────────────────────
    # WHY: if we've already retried twice, we must not loop forever.
    # Force PASS and let the formatting agent handle the best available answer.
    if ov_status == "RETRY" and overall_retry_count >= MAX_RETRIES:
        logger.warning(
            "|| [OverallValidationAgent] Max retries (%d) reached — overriding RETRY → PASS",
            MAX_RETRIES,
        )
        ov_status    = "PASS"
        ov_reason    = (
            f"Max retries ({MAX_RETRIES}) reached. Proceeding with best available answer. "
            f"Original reason: {ov_reason}"
        )
        ov_plan_fix  = None

    # ── Update retry count if we are retrying ─────────────────────────────────
    # WHY increment before writing: the next execution_agent run should see the updated count
    # so that if it still fails, the NEXT overall validation knows how many tries were used.
    new_overall_retry_count = overall_retry_count + 1 if ov_status == "RETRY" else overall_retry_count

    latency = round(time.perf_counter() - _t_start, 3)
    logger.info("|| [OverallValidationAgent] latency=%.3f s", latency)

    log_str = _print_overall_validation_log(
        status=ov_status,
        score=ov_score,
        reason=ov_reason,
        plan_fix_instructions=ov_plan_fix,
        token_counts=token_counts,
        query=user_query,
        overall_retry_count=overall_retry_count,
    )

    trace.append(
        f"[OverallValidationAgent] status={ov_status} | score={ov_score}/10 | "
        f"overall_retry={overall_retry_count} | "
        f"thinking={token_counts['thinking']} | latency={latency:.3f}s"
    )

    return {
        **state,
        "overall_validation_status":          ov_status,
        "overall_confidence_score":           ov_score,
        "overall_validation_reason":          ov_reason,
        # WHY write overall_plan_retry_instructions (not overall_retry_instructions):
        #   The RETRY now loops back to goal_planning_agent, not execution_agent.
        #   goal_planning_agent reads overall_plan_retry_instructions to understand
        #   what the Overall Validation Agent found wrong with the previous plan.
        "overall_plan_retry_instructions":    ov_plan_fix,
        "overall_retry_count":                new_overall_retry_count,
        "overall_validation_log":             log_str,
        "overall_validation_thinking_tokens": token_counts["thinking"],
        "total_input_tokens":   state.get("total_input_tokens", 0) + token_counts.get("input", 0),
        "total_output_tokens":  state.get("total_output_tokens", 0) + token_counts.get("output", 0),
        "total_thinking_tokens": state.get("total_thinking_tokens", 0) + token_counts.get("thinking", 0),
        "latency_overall_validation": latency,
        "agent_trace":                trace,
    }
