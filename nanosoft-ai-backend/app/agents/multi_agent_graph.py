"""
Multi-Agent LangGraph Graph — Full Pipeline

Wires all 8 agents into a LangGraph StateGraph with two conditional retry loops.

Graph topology:
    START
      → understanding_agent
      → goal_planning_agent
      → retrieval_agent
      → mini_validation_agent
          ├─ RETRY (retry_count < 2) → retrieval_agent        (loop back on bad retrieval)
          └─ PASS / FAIL             → filtering_agent
      → filtering_agent
      → execution_agent
      → overall_validation_agent
          ├─ RETRY (overall_retry_count < 2) → goal_planning_agent (re-plan with fix instructions)
          └─ PASS                            → formatting_agent
      → formatting_agent
      → END
"""

import logging
import time

from langgraph.graph import StateGraph, START, END

from app.agents.state import AgentState
from app.agents.understanding_agent import understanding_agent_node
from app.agents.goal_planning_agent import goal_planning_agent_node
from app.agents.retrieval_agent import retrieval_agent_node
from app.agents.validation_agent import validation_agent_node
from app.agents.filtering_agent import filtering_agent_node
from app.agents.execution_agent import execution_agent_node
from app.agents.overall_validation_agent import overall_validation_agent_node
from app.agents.formatting_agent import formatting_agent_node
from app.agents.log_config import setup_agent_logger, log_pipeline_token_usage

logger = setup_agent_logger("multi_agent_graph")


# ── Conditional routing function ──────────────────────────────────────────────

def route_after_validation(state: AgentState) -> str:
    """
    Route from mini_validation_agent:
      - RETRY → retrieval_agent   (loop back for another attempt with new instructions)
      - PASS  → filtering_agent   (data is good, proceed to filter then execute)
      - FAIL  → filtering_agent   (execution agent will handle gracefully via FAIL status)

    WHY RETRY loops back to retrieval_agent (not understanding or goal_planning):
      The understanding and goal_planning agents already produced correct intent and plan.
      The retrieval FAILED because of bad parameter values or wrong tool selection.
      Looping back to retrieval with specific retry_instructions fixes JUST the retrieval
      without wasting tokens re-running the entire pipeline from scratch.

    WHY FAIL still goes to filtering_agent (not END):
      Even on FAIL the Execution Agent must produce a response — either a helpful
      message saying no data was found, or a partial answer from whatever data arrived.
      Sending FAIL state to the Execution Agent lets it communicate this to the user
      gracefully instead of returning a raw empty state.
    """
    status = state.get("validation_status", "PASS")
    if status == "RETRY":
        logger.info("|| Routing [mini_validation]: RETRY -> retrieval_agent (will use retry_instructions)")
        return "retrieval_agent"
    else:
        logger.info("|| Routing [mini_validation]: %s -> filtering_agent", status)
        return "filtering_agent"


def route_after_overall_validation(state: AgentState) -> str:
    """
    Route from overall_validation_agent:
      - RETRY → goal_planning_agent  (re-plan from scratch with plan_fix_instructions)
      - PASS  → formatting_agent     (answer is good, apply final formatting)

    WHY RETRY now loops back to goal_planning_agent (not execution_agent):
      When the Overall Validation Agent finds the ROOT CAUSE is a bad plan —
      wrong approach, wrong tools, wrong execution steps — re-running just
      execution_agent with the SAME bad plan will never fix the answer.
      We must re-plan from scratch so retrieval, filtering, and execution
      all run again with a corrected plan.
      goal_planning_agent reads overall_plan_retry_instructions (written by
      overall_validation_agent) and prepends a ⚠️ RE-PLANNING block to its prompt
      so the LLM knows exactly what to fix.

    WHY always end at formatting_agent (even after max retries):
      The user must always get a response. Even if the overall confidence score is still
      below 7 after 2 retries, we proceed to formatting_agent with the best available answer.
      The overall_validation_agent's guard converts RETRY → PASS when retries are exhausted.
    """
    status = state.get("overall_validation_status", "PASS")
    if status == "RETRY":
        score = state.get("overall_confidence_score", 7)
        logger.info(
            "|| Routing [overall_validation]: RETRY -> goal_planning_agent "
            "(score=%d/10, will use plan_fix_instructions to re-plan)", score
        )
        # ── THIS IS THE LINE THAT CALLS BACK THE AGENT ──────────────────────
        # LangGraph reads this return value and activates the goal_planning_agent node.
        return "goal_planning_agent"
    else:
        score = state.get("overall_confidence_score", 7)
        logger.info(
            "|| Routing [overall_validation]: PASS -> formatting_agent (score=%d/10)", score
        )
        return "formatting_agent"


# ── Build the graph ───────────────────────────────────────────────────────────

def build_agent_graph() -> StateGraph:
    """
    Build and compile the LangGraph multi-agent pipeline.
    Returns a compiled graph ready for async invocation.
    """
    graph = StateGraph(AgentState)

    # ── Register nodes ───────────────────────────────────────────────────────
    graph.add_node("understanding_agent",       understanding_agent_node)
    graph.add_node("goal_planning_agent",       goal_planning_agent_node)
    graph.add_node("retrieval_agent",           retrieval_agent_node)
    graph.add_node("mini_validation_agent",     validation_agent_node)
    graph.add_node("filtering_agent",           filtering_agent_node)
    graph.add_node("execution_agent",           execution_agent_node)
    graph.add_node("overall_validation_agent",  overall_validation_agent_node)
    graph.add_node("formatting_agent",          formatting_agent_node)

    # ── Define edges ─────────────────────────────────────────────────────────
    graph.add_edge(START,                    "understanding_agent")
    graph.add_edge("understanding_agent",    "goal_planning_agent")
    graph.add_edge("goal_planning_agent",    "retrieval_agent")
    graph.add_edge("retrieval_agent",        "mini_validation_agent")

    # WHY conditional edge here (not after retrieval):
    #   The Mini Validation Agent checks if the DATA is correct BEFORE execution.
    #   A conditional edge lets the graph loop back to retrieval_agent for a RETRY
    #   without re-running understanding or goal_planning (those results are still valid).
    graph.add_conditional_edges(
        "mini_validation_agent",
        route_after_validation,
        {
            "retrieval_agent": "retrieval_agent",  # RETRY branch
            "filtering_agent": "filtering_agent",  # PASS / FAIL branch
        },
    )

    # WHY filtering_agent sits between validation and execution:
    #   DB results contain 30-60 fields per record. Filtering removes columns that
    #   are not needed for the answer, shrinking the execution prompt significantly.
    graph.add_edge("filtering_agent",           "execution_agent")

    # WHY conditional edge after overall_validation_agent:
    #   The Overall Validation Agent checks if the FINAL ANSWER is correct (not just data).
    #   If the answer quality is below threshold (score < 7) and retries remain,
    #   it loops back to goal_planning_agent with plan_fix_instructions so the ENTIRE
    #   retrieval + filtering + execution chain re-runs with a corrected plan.
    graph.add_edge("execution_agent",           "overall_validation_agent")
    graph.add_conditional_edges(
        "overall_validation_agent",
        route_after_overall_validation,
        {
            # ── THE LINE THAT WIRES THE RETRY CALL ─────────────────────────────
            # When route_after_overall_validation() returns "goal_planning_agent",
            # LangGraph activates goal_planning_agent_node as the next node to run.
            "goal_planning_agent": "goal_planning_agent",  # RETRY → re-plan from scratch
            "formatting_agent":    "formatting_agent",     # PASS  → format and return
        },
    )

    # WHY formatting_agent is the final node:
    #   The Formatting Agent transforms the validated answer into the user's expected
    #   output format (TABLE, BULLET_LIST, JSON, MARKDOWN, etc.) and writes formatted_answer.
    #   This is the field the API returns to the user.
    graph.add_edge("formatting_agent", END)

    compiled = graph.compile()
    logger.info(
        "Multi-Agent Graph compiled | nodes=["
        "understanding_agent -> goal_planning_agent -> retrieval_agent "
        "-> mini_validation_agent -[PASS/FAIL]-> filtering_agent "
        "-> execution_agent | -[RETRY]-> retrieval_agent]"
    )
    return compiled


# ── Singleton graph instance ──────────────────────────────────────────────────
agent_graph = build_agent_graph()


# ── Public run function ───────────────────────────────────────────────────────

async def run_agent_pipeline(
    user_query: str,
    conversation_history: list | None = None,
    user_name: str | None = None,
    user_id: int | None = None,
) -> AgentState:
    """
    Run the full multi-agent pipeline for a user query.

    Args:
        user_query:            The raw user message string.
        conversation_history:  List of prior messages as dicts with 'role' and 'content'.
        user_name:             Authenticated user name (e.g. 'poc').
        user_id:               Authenticated user ID (e.g. 1).

    Returns:
        The final AgentState after all agents have run.
        Key fields: state['final_answer'], state['agent_trace']
    """
    initial_state: AgentState = {
        "user_query":                    user_query,
        "conversation_history":          conversation_history or [],
        "user_name":                     user_name or "system",
        "user_id":                       user_id,

        # WHY all fields initialised to None:
        #   LangGraph requires all TypedDict keys to be present in the initial state.
        #   Agents read state fields with .get() and use None as a sentinel for
        #   "not yet set by upstream agent". This avoids KeyError on any field access.
        "understood_intent":             None,
        "understanding_log":             None,
        "understanding_thinking_tokens": None,
        # WHY web_search_summary starts None:
        #   Set by Understanding Agent only when needs_search=True.
        #   Downstream agents check this field; None means no external search ran.
        "web_search_summary":            None,

        "goal_plan":                     None,
        "goal_log":                      None,
        "goal_thinking_tokens":          None,

        "retrieval_plan":                None,
        "retrieval_results":             None,
        "retrieval_log":                 None,
        "retrieval_thinking_tokens":     None,

        "filtered_results":              None,
        "filtering_log":                 None,
        "filtering_thinking_tokens":     None,

        "validation_status":             None,
        "validation_reason":             None,
        "retry_instructions":            None,
        "retry_count":                   0,
        "validation_log":                None,
        "validation_thinking_tokens":    None,

        "final_answer":                  None,
        "execution_log":                 None,
        "execution_thinking_tokens":     None,

        # WHY overall_retry_count starts at 0:
        #   This counter tracks how many times the overall_validation_agent
        #   has sent the answer back to execution_agent. Max is 2.
        "overall_validation_status":          None,
        "overall_confidence_score":           None,
        "overall_validation_reason":          None,
        "overall_plan_retry_instructions":    None,   # plan-level fix for goal_planning_agent
        "overall_retry_count":                0,
        "overall_validation_log":             None,
        "overall_validation_thinking_tokens": None,

        "formatted_answer":              None,
        "detected_format":               None,
        "formatting_log":                None,
        "formatting_thinking_tokens":    None,

        "agent_trace":                   [],

        # WHY all latency fields initialised to None:
        #   Each agent writes its own latency field. None = not yet run.
        "latency_understanding":          None,
        "latency_goal_planning":          None,
        "latency_retrieval":              None,
        "latency_validation":             None,
        "latency_filtering":              None,
        "latency_execution":              None,
        "latency_overall_validation":     None,
        "latency_formatting":             None,
        "latency_total":                  None,
    }

    logger.info("=" * 66)
    logger.info("PIPELINE START  |  query='%s'  |  user='%s'", user_query[:80], user_name or "anon")
    logger.info("=" * 66)

    _t_pipeline_start = time.perf_counter()
    final_state = await agent_graph.ainvoke(initial_state)
    pipeline_latency = round(time.perf_counter() - _t_pipeline_start, 3)
    # Inject total latency into state for the summary log
    final_state = {**final_state, "latency_total": pipeline_latency}
    logger.info("|| PIPELINE total latency=%.3f s", pipeline_latency)

    # ── Final pipeline summary ────────────────────────────────────────────────
    logger.info("\n" + "=" * 66)
    logger.info("PIPELINE COMPLETE -- AGENT TRACE:")
    for entry in final_state.get("agent_trace", []):
        logger.info("   >> %s", entry)
    logger.info("=" * 66 + "\n")

    # Log the overall token usage (added for the user)
    log_pipeline_token_usage(final_state, logger)

    return final_state
