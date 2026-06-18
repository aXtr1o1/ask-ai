"""
Multi-Agent LangGraph Graph — Phase 1

Wires the Understanding Agent and Goal Planning Agent into a LangGraph StateGraph.

Graph topology (Phase 1):
    START → understanding_agent → goal_planning_agent → END

Phase 1 produces only console logs.
No tools are executed. No final user response is generated.
"""

import logging

from langgraph.graph import StateGraph, START, END

from app.agents.state import AgentState
from app.agents.understanding_agent import understanding_agent_node
from app.agents.goal_planning_agent import goal_planning_agent_node

logger = logging.getLogger("multi_agent_graph")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    _ch = logging.StreamHandler()
    _ch.stream = open(_ch.stream.fileno(), mode='w', encoding='utf-8', buffering=1, closefd=False)
    _ch.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(_ch)
logger.propagate = False   # prevent double-printing to root logger


# ── Build the graph ───────────────────────────────────────────────────────────

def build_agent_graph() -> StateGraph:
    """
    Build and compile the Phase 1 LangGraph multi-agent pipeline.

    Returns a compiled graph ready for async invocation.
    """
    graph = StateGraph(AgentState)

    # ── Register nodes ────────────────────────────────────────────────────────
    graph.add_node("understanding_agent", understanding_agent_node)
    graph.add_node("goal_planning_agent", goal_planning_agent_node)

    # ── Define edges ──────────────────────────────────────────────────────────
    graph.add_edge(START, "understanding_agent")
    graph.add_edge("understanding_agent", "goal_planning_agent")
    graph.add_edge("goal_planning_agent", END)

    compiled = graph.compile()
    logger.info("Multi-Agent Graph compiled | nodes=[understanding_agent -> goal_planning_agent]")
    return compiled


# ── Singleton graph instance ──────────────────────────────────────────────────
# Compiled once at import time (lightweight — no model weights loaded yet)
agent_graph = build_agent_graph()


# ── Public run function ───────────────────────────────────────────────────────

async def run_agent_pipeline(
    user_query: str,
    conversation_history: list | None = None,
    user_name: str | None = None,
) -> AgentState:
    """
    Run the full Phase 1 multi-agent pipeline for a user query.

    Args:
        user_query:            The raw user message string.
        conversation_history:  List of prior messages as dicts with 'role' and 'content'.
        user_name:             Authenticated user name (optional for Phase 1 logging).

    Returns:
        The final AgentState after all agents have run.
        Check state['agent_trace'] for the full pipeline log.
    """
    initial_state: AgentState = {
        "user_query":                    user_query,
        "conversation_history":          conversation_history or [],
        "user_name":                     user_name,
        "understood_intent":             None,
        "understanding_log":             None,
        "understanding_thinking_tokens": None,
        "goal_plan":                     None,
        "goal_log":                      None,
        "goal_thinking_tokens":          None,
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
