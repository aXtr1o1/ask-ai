"""
AgentState — Shared state TypedDict for the LangGraph multi-agent pipeline.

This state is passed between all agent nodes in the graph.
Each agent reads from it and writes its own section.
"""

from typing import TypedDict, Optional, Any


class AgentState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────────
    user_query: str                      # The raw user message
    conversation_history: list           # Prior messages for context (list of dicts)
    user_name: Optional[str]             # Authenticated user name (from session)

    # ── Set by Understanding Agent ─────────────────────────────────────────────
    understood_intent: Optional[dict]    # Structured intent output (see understanding_agent.py)
    understanding_log: Optional[str]     # Human-readable console log string
    understanding_thinking_tokens: Optional[int]  # Thinking tokens used

    # ── Set by Goal Planning Agent ─────────────────────────────────────────────
    goal_plan: Optional[dict]            # Structured execution plan
    goal_log: Optional[str]             # Human-readable console log string
    goal_thinking_tokens: Optional[int] # Thinking tokens used

    # ── Meta-trace (appended by each agent for full pipeline visibility) ───────
    agent_trace: list[str]               # Ordered list of agent conclusions
