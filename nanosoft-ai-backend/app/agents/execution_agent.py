"""
Execution Agent — Node 6 (Final) in the LangGraph multi-agent pipeline.

Responsibilities:
  - Receive filtered retrieval results from the Filtering Agent
  - Reason deeply over the data using the Goal Planning Agent's analysis_instruction
  - If web_search_summary is present, incorporate it into the answer
  - Produce a complete, intelligent natural language answer
  - Log a clean, structured summary to the console

WHY this is the final node (not followed by anything):
  The pipeline is: Understand → Plan → Retrieve → Validate → Filter → Execute
  Execution produces the natural language answer the user sees. Once this runs,
  the pipeline is complete. There is no post-processing node because the model's
  answer is the product — further LLM calls would only add latency.

Model: gemini-2.5-flash with thinking enabled (highest budget — final answer quality matters most)
"""

import json
import time
from typing import Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.agents.prompts.execution_prompt import (
    EXECUTION_SYSTEM_PROMPT,
    EXECUTION_USER_TEMPLATE,
)
# WHY these helpers: see log_config.py for detailed explanations.
from app.agents.log_config import (
    setup_agent_logger,
    extract_token_counts,
    parse_llm_text,
)
from app.agents.services.data_summarizer import smart_prepare
from app.config import settings

logger = setup_agent_logger("execution_agent")


# ── Model initialisation ──────────────────────────────────────────────────────

def _build_model() -> ChatGoogleGenerativeAI:
    """
    Build the Execution Agent model with the highest thinking budget.

    WHY thinking_budget=8000 (highest in the pipeline):
      This agent produces the final answer the user sees. It must:
        - Read and reason over potentially hundreds of DB records
        - Apply the analysis_instruction from Goal Planning
        - Incorporate web_search_summary if external knowledge was fetched
        - Write a clear, accurate, well-structured natural language response
      All of this requires the most reasoning capacity of any agent in the pipeline.
    """
    return ChatGoogleGenerativeAI(
        model=settings.MULTI_AGENT_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,          # WHY: required for thinking mode (Gemini constraint)
        thinking_budget=8000,
    )




# ── Main agent node ───────────────────────────────────────────────────────────

async def execution_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Execution Agent.

    Reads:  state['user_query'], state['understood_intent'], state['goal_plan'],
            state['retrieval_results'], state['validation_status']
    Writes: state['final_answer'], state['execution_log'],
            state['execution_thinking_tokens'], state['agent_trace']
    """
    user_query           = state.get("user_query", "").strip()
    understood_intent    = state.get("understood_intent", {}) or {}
    goal_plan            = state.get("goal_plan", {}) or {}
    # WHY prefer filtered_results over retrieval_results:
    #   The Filtering Agent has already removed irrelevant DB columns.
    #   Using filtered data keeps the execution prompt smaller and the answer focused.
    #   Fall back to raw retrieval_results only if filtering didn't run.
    retrieval_results    = state.get("filtered_results") or state.get("retrieval_results", []) or []
    validation_status    = state.get("validation_status", "PASS")
    # WHY read web_search_summary:
    #   If the Understanding Agent ran Google Search (needs_search=True), this field
    #   contains the external knowledge. We pass it to the prompt so the final answer
    #   can cite or integrate the search findings.
    web_search_summary   = state.get("web_search_summary")
    # WHY read overall_retry_instructions:
    #   When the Overall Validation Agent scores the previous answer below 7,
    #   it loops back here with specific instructions on what to fix.
    #   We inject these instructions at the TOP of the user prompt so the model
    #   addresses the identified problem directly instead of repeating the same answer.
    overall_retry_instr  = state.get("overall_retry_instructions")
    overall_retry_count  = state.get("overall_retry_count", 0) or 0
    trace                = list(state.get("agent_trace", []))

    logger.info("=" * 66)
    logger.info(
        "Execution Agent -- START | query='%s' | validation=%s | overall_retry=%d",
        user_query[:80], validation_status, overall_retry_count,
    )
    logger.info("=" * 66)
    _t_start = time.perf_counter()

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
        "||  Overall Retry Run : %d (0 = first run)\n"
        "||  Goal Approach     : %s | Complexity: %s\n"
        "||  Data Received     : %d record(s) from retrieval\n"
        "||  Analysis Goal     : %s\n"
        "||  Override Instr.   : %s\n"
        "||  I will            : Read the retrieved data carefully\n"
        "||                      Apply the analysis goal to find the answer\n"
        "||                      Write a clear, natural language response\n"
        "|| ============================================================",
        validation_status, overall_retry_count, approach, complexity, data_count,
        analysis_instr or "(produce a direct answer from retrieved data)",
        (overall_retry_instr[:100] if overall_retry_instr else "N/A (first run)"),
    )

    # ── Smart data preparation (replaces naive p_list[:100] cap) ──────────────
    # WHY smart_prepare instead of a raw cap:
    #   Truncating to 100 records gives WRONG answers when the user asks
    #   "how many overdue tasks?" and the DB returned 11,000 records.
    #   smart_prepare detects large datasets and replaces p_list with a compact
    #   Python-computed summary (group-by counts, numeric stats) + a 20-record
    #   sample. The LLM writes a CORRECT, DETAILED answer from the summary
    #   without ever seeing all 11,000 rows -- and without hitting token limits.
    #   Small datasets (<= 500 records) pass through unchanged.
    capped_results = smart_prepare(retrieval_results, understood_intent)

    # ── Build prompt ──────────────────────────────────────────────────────────
    # WHY prepend override_instructions:
    #   When the Overall Validation Agent sends us back (overall_retry_count > 0),
    #   the most important thing for the model to see FIRST is what it got wrong
    #   and how to fix it. Prepending the override block ensures the model addresses
    #   the specific problem before re-reading the data.
    override_block = ""
    if overall_retry_instr:
        override_block = (
            f"\n\n⚠️  QUALITY IMPROVEMENT REQUIRED (Retry {overall_retry_count} of 2):\n"
            f"The Overall Validation Agent scored your previous answer below 7/10.\n"
            f"You MUST fix the following specific problem before generating your new answer:\n"
            f"{overall_retry_instr}\n"
            f"Generate a completely new, corrected answer addressing this issue.\n"
        )

    user_content = EXECUTION_USER_TEMPLATE.format(
        user_query=user_query,
        understood_intent=json.dumps(understood_intent, indent=2),
        goal_plan=json.dumps(goal_plan, indent=2),
        retrieval_results=json.dumps(capped_results, indent=2),
    ) + override_block

    messages = [
        SystemMessage(content=EXECUTION_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    # ── Invoke model ──────────────────────────────────────────────────────────
    try:
        model    = _build_model()
        response = await model.ainvoke(messages)

        # WHY use shared helpers: see log_config.py for detailed explanations.
        # NOTE: execution agent outputs plain text (not JSON), so we only use
        # extract_token_counts + parse_llm_text — strip_json_fences is not needed.
        token_counts = extract_token_counts(response)
        final_answer = parse_llm_text(response)

    except Exception as exc:
        logger.error("Execution Agent error: %s", exc, exc_info=True)
        final_answer = (
            "I encountered an error while generating the response. "
            "Please try again or rephrase your question."
        )
        token_counts = {"thinking": 0, "input": 0, "output": 0}

    # ── Result log (same || format as all other agents) ────────────────────
    latency = round(time.perf_counter() - _t_start, 3)
    logger.info("|| [ExecutionAgent] latency=%.3f s", latency)
    preview = final_answer[:200].replace("\n", " ") + ("..." if len(final_answer) > 200 else "")
    log_str = (
        f"\n|| ============================================================\n"
        f"||  EXECUTION AGENT -- RESULT\n"
        f"|| ============================================================\n"
        f"||  Query            : {user_query[:80]}\n"
        f"||  Validation Status: {validation_status}\n"
        f"||  Answer Preview   : {preview}\n"
        f"||  Answer Length    : {len(final_answer)} chars\n"
        f"||  Thinking Tokens  : {token_counts['thinking']:,}\n"
        f"||  Input Tokens     : {token_counts['input']:,}\n"
        f"||  Output Tokens    : {token_counts['output']:,}\n"
        f"|| ============================================================"
    )
    logger.info(log_str)

    trace.append(
        f"[ExecutionAgent] answer_len={len(final_answer)} | "
        f"thinking={token_counts['thinking']} | input={token_counts['input']} | "
        f"latency={latency:.3f}s"
    )

    return {
        **state,
        "final_answer":               final_answer,
        "execution_log":              log_str,
        "execution_thinking_tokens":  token_counts["thinking"],
        "total_input_tokens":         state.get("total_input_tokens", 0) + token_counts.get("input", 0),
        "total_output_tokens":        state.get("total_output_tokens", 0) + token_counts.get("output", 0),
        "total_thinking_tokens":      state.get("total_thinking_tokens", 0) + token_counts.get("thinking", 0),
        "latency_execution":          latency,
        "agent_trace":                trace,
    }
