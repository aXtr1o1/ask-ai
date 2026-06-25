"""
Multi-Agent LangGraph Graph — Full Pipeline

Wires all 6 agents into a LangGraph StateGraph with conditional retry loop.

Graph topology:
    START
      → understanding_agent
      → goal_planning_agent
      → retrieval_agent
      → mini_validation_agent
          ├─ RETRY (retry_count < 2) → retrieval_agent  (loop back)
          └─ PASS / FAIL             → filtering_agent
      → filtering_agent
      → execution_agent
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
        logger.info("|| Routing: RETRY -> retrieval_agent (will use retry_instructions)")
        return "retrieval_agent"
    else:
        logger.info("|| Routing: %s -> filtering_agent", status)
        return "filtering_agent"


# ── Build the graph ───────────────────────────────────────────────────────────

def build_agent_graph() -> StateGraph:
    """
    Build and compile the LangGraph multi-agent pipeline.
    Returns a compiled graph ready for async invocation.
    """
    graph = StateGraph(AgentState)

    # ── Register nodes ───────────────────────────────────────────────────────
    graph.add_node("understanding_agent",   understanding_agent_node)
    graph.add_node("goal_planning_agent",   goal_planning_agent_node)
    graph.add_node("retrieval_agent",       retrieval_agent_node)
    graph.add_node("mini_validation_agent", validation_agent_node)
    graph.add_node("filtering_agent",       filtering_agent_node)
    graph.add_node("execution_agent",       execution_agent_node)

    # ── Define edges ─────────────────────────────────────────────────────────
    graph.add_edge(START,                    "understanding_agent")
    graph.add_edge("understanding_agent",    "goal_planning_agent")
    graph.add_edge("goal_planning_agent",    "retrieval_agent")
    graph.add_edge("retrieval_agent",        "mini_validation_agent")

    # WHY conditional edge here (not after retrieval):
    #   The Validation Agent checks if the data is correct BEFORE execution.
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
    graph.add_edge("filtering_agent", "execution_agent")
    graph.add_edge("execution_agent", END)

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

        "agent_trace":                   [],

        # WHY all latency fields initialised to None:
        #   Each agent writes its own latency field. None = not yet run.
        "latency_understanding":          None,
        "latency_goal_planning":          None,
        "latency_retrieval":              None,
        "latency_validation":             None,
        "latency_filtering":              None,
        "latency_execution":              None,
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
