"""
AgentState — Shared state TypedDict for the LangGraph multi-agent pipeline.

This state is passed between all agent nodes in the graph.
Each agent reads from it and writes its own section.

Pipeline order:
  understanding_agent → goal_planning_agent → retrieval_agent
  → mini_validation_agent → (retry loop max 2x) → filtering_agent
  → execution_agent → overall_validation_agent → (retry loop max 2x) → formatting_agent
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
    # WHY: When the Understanding Agent detects needs_search=True it performs
    # Google Search grounding in-place and stores the summary here. All downstream
    # agents (Goal Planning, Retrieval, Execution) can read this field and use it
    # as external context without triggering another web search.
    web_search_summary: Optional[str]    # Web search summary (set when needs_search=True, else None)


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

    # ── Set by Overall Validation Agent ────────────────────────────────────
    # WHY a separate overall validation (vs mini_validation_agent):
    #   mini_validation_agent checks ONLY the Retrieval Agent output (data quality gate).
    #   overall_validation_agent checks the ENTIRE pipeline end-to-end:
    #   understanding → planning → retrieval → filtering → final_answer quality.
    #   It gives a confidence score 0-10 and can loop back to execution_agent
    #   with specific fix instructions if the final answer is below threshold.
    overall_validation_status: Optional[str]      # PASS | RETRY | FAIL
    overall_confidence_score: Optional[int]        # 0-10 confidence score on the full pipeline
    overall_validation_reason: Optional[str]       # Detailed explanation of the score
    overall_retry_instructions: Optional[str]      # What execution_agent should do differently (kept for reference)
    # WHY overall_plan_retry_instructions:
    #   When overall_validation_agent determines that the ROOT CAUSE of a bad answer
    #   is a wrong plan (wrong approach, wrong tools, wrong execution steps), it writes
    #   specific re-planning instructions here.  goal_planning_agent reads this field
    #   on retry runs and prepends a ⚠️ RE-PLANNING block to its prompt so it produces
    #   a corrected plan before retrieval, filtering, and execution re-run.
    overall_plan_retry_instructions: Optional[str] # What goal_planning_agent must fix on re-plan retry
    overall_retry_count: Optional[int]             # Number of full re-plan retries so far (max 2)
    overall_validation_log: Optional[str]          # Human-readable console log string
    overall_validation_thinking_tokens: Optional[int]

    # ── Set by Formatting Agent ─────────────────────────────────────────────
    # WHY a separate formatting agent (vs baking format into execution_agent):
    #   Keeping formatting separate means execution_agent always produces clean,
    #   format-neutral text. The formatting agent then adapts it to whatever
    #   output format the user expects (table, list, JSON, etc.).
    #   This avoids bloating the execution prompt with format detection logic.
    formatted_answer: Optional[str]       # Final answer in user's requested format
    detected_format: Optional[str]        # PLAIN_TEXT | BULLET_LIST | TABLE | JSON | MARKDOWN | NUMBERED_LIST
    formatting_log: Optional[str]         # Human-readable console log string
    formatting_thinking_tokens: Optional[int]

    # ── Pipeline token accumulators ────────────────────────────────────────────
    total_input_tokens: Optional[int]
    total_output_tokens: Optional[int]
    total_thinking_tokens: Optional[int]

    # ── Per-agent latency (seconds, measured with time.perf_counter) ───────────
    latency_understanding: Optional[float]          # understanding_agent wall-clock seconds
    latency_goal_planning: Optional[float]          # goal_planning_agent wall-clock seconds
    latency_retrieval: Optional[float]              # retrieval_agent wall-clock seconds
    latency_validation: Optional[float]             # mini_validation_agent wall-clock seconds
    latency_filtering: Optional[float]              # filtering_agent wall-clock seconds
    latency_execution: Optional[float]              # execution_agent wall-clock seconds
    latency_overall_validation: Optional[float]     # overall_validation_agent wall-clock seconds
    latency_formatting: Optional[float]             # formatting_agent wall-clock seconds
    latency_total: Optional[float]                  # full pipeline wall-clock seconds

    # ── Meta-trace (appended by each agent for full pipeline visibility) ───────
    agent_trace: list[str]               # Ordered list of agent conclusions
