"""
AgentState — Shared state TypedDict for the LangGraph multi-agent pipeline.

This state is passed between all agent nodes in the graph.
Each agent reads from it and writes its own section.

Pipeline order:
  understanding_agent → goal_planning_agent → retrieval_agent
  → mini_validation_agent → (retry loop max 2x) → execution_agent
"""

from typing import TypedDict, Optional, Any


class AgentState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────────
    user_query: str                      # The raw user message
    conversation_history: list           # Prior messages for context (list of dicts)
    user_name: Optional[str]             # Authenticated user name (from session)
    user_id: Optional[int]               # Authenticated user ID (from session)

    # ── Set by Understanding Agent ─────────────────────────────────────────────
    understood_intent: Optional[dict]    # Structured intent output
    understanding_log: Optional[str]     # Human-readable console log string
    understanding_thinking_tokens: Optional[int]

    # ── Set by Goal Planning Agent ─────────────────────────────────────────────
    goal_plan: Optional[dict]            # Structured execution plan (with analysis_instruction per step)
    goal_log: Optional[str]             # Human-readable console log string
    goal_thinking_tokens: Optional[int]

    # ── Set by Retrieval Agent ─────────────────────────────────────────────────
    retrieval_plan: Optional[list]       # List of structured steps (decided by LLM)
    retrieval_results: Optional[list]    # Output of executed tool calls (raw, all fields)
    retrieval_log: Optional[str]         # Human-readable console log string
    retrieval_thinking_tokens: Optional[int]

    # ── Set by Filtering Agent ─────────────────────────────────────────────────
    filtered_results: Optional[list]     # Retrieval results filtered to relevant fields only
    filtering_log: Optional[str]         # Human-readable console log string
    filtering_thinking_tokens: Optional[int]
    # ── Set by Mini Validation Agent ───────────────────────────────────────────
    validation_status: Optional[str]     # PASS | RETRY | FAIL
    validation_reason: Optional[str]     # Why validation passed/failed/retrying
    retry_instructions: Optional[str]    # Specific guidance for retrieval retry
    retry_count: Optional[int]           # Number of retrieval retries so far (max 2)
    validation_log: Optional[str]        # Human-readable console log string
    validation_thinking_tokens: Optional[int]

    # ── Set by Execution Agent ─────────────────────────────────────────────────
    final_answer: Optional[str]          # The natural language answer shown to the user
    execution_log: Optional[str]         # Human-readable console log string
    execution_thinking_tokens: Optional[int]

    # ── Meta-trace (appended by each agent for full pipeline visibility) ───────
    agent_trace: list[str]               # Ordered list of agent conclusions
