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

from langgraph.graph import StateGraph, START, END

from app.agents.state import AgentState
from app.agents.understanding_agent import understanding_agent_node
from app.agents.goal_planning_agent import goal_planning_agent_node
from app.agents.retrieval_agent import retrieval_agent_node
from app.agents.validation_agent import validation_agent_node
from app.agents.filtering_agent import filtering_agent_node
from app.agents.execution_agent import execution_agent_node
from app.agents.log_config import setup_agent_logger

logger = setup_agent_logger("multi_agent_graph")


# ── Conditional routing function ──────────────────────────────────────────────

def route_after_validation(state: AgentState) -> str:
    """
    Route from mini_validation_agent:
      - RETRY → retrieval_agent   (loop back for another attempt)
      - PASS  → filtering_agent   (filter data before execution)
      - FAIL  → filtering_agent   (execution agent handles gracefully)
    """
    status = state.get("validation_status", "PASS")
    if status == "RETRY":
        logger.info("|| Routing: RETRY → retrieval_agent")
        return "retrieval_agent"
    else:
        logger.info("|| Routing: %s → filtering_agent", status)
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

    # Conditional: RETRY loops back to retrieval_agent; PASS/FAIL goes to filtering_agent
    graph.add_conditional_edges(
        "mini_validation_agent",
        route_after_validation,
        {
            "retrieval_agent": "retrieval_agent",
            "filtering_agent": "filtering_agent",
        },
    )

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

        "understood_intent":             None,
        "understanding_log":             None,
        "understanding_thinking_tokens": None,

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
    }

    logger.info("=" * 66)
    logger.info("PIPELINE START  |  query='%s'  |  user='%s'", user_query[:80], user_name or "anon")
    logger.info("=" * 66)

    final_state = await agent_graph.ainvoke(initial_state)

    # ── Final pipeline summary ────────────────────────────────────────────────
    logger.info("\n" + "=" * 66)
    logger.info("PIPELINE COMPLETE -- AGENT TRACE:")
    for entry in final_state.get("agent_trace", []):
        logger.info("   >> %s", entry)
    logger.info("=" * 66 + "\n")

    return final_state
