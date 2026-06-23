# -*- coding: utf-8 -*-
"""
Standalone Test Runner -- Multi-Agent Pipeline (Full 6-Agent)

Run this script to test the full pipeline interactively.
Type your queries directly in the terminal. The agents will process each
query and print their full structured reasoning to the console,
ending with the final answer. All logs are also written to logs/agents.log

HOW TO RUN (from nanosoft-ai-backend/):
    $env:PYTHONUTF8=1; .\\app\\venv\\Scripts\\python -m app.agents.run_agents
"""

import asyncio
import logging
import sys
import io

# -- Force UTF-8 on Windows stdout --------------------------------------------
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# WHY setup_agent_logger (not raw logging):
#   All agent files use setup_agent_logger from log_config.py which writes
#   to app/agents/logs/agents.log with the standard || prefix format.
#   Using the same logger here means run_agents output is in the same file
#   and the same format as the agents it is testing.
from app.agents.log_config import setup_agent_logger

logger = setup_agent_logger("run_agents")

# Suppress noisy third-party loggers
import logging
for _noisy in ("httpx", "httpcore", "google.auth", "urllib3", "asyncio"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


# -- Main interactive loop ----------------------------------------------------

async def run_interactive():
    """
    Interactive REPL: type a query, all 6 agents process it, logs + final answer appear.
    Conversation history is maintained across turns for follow-up queries.
    Type 'exit' or 'quit' to stop.
    """
    from app.agents.multi_agent_graph import run_agent_pipeline
    from app.agents.log_config import write_session_separator

    # Write a session separator to the log file so each run is clearly marked
    write_session_separator("SESSION START")

    print()
    print("=" * 70)
    print("  ASK-AI Multi-Agent Pipeline -- Full 6-Agent Pipeline")
    print("  Agents: Understanding -> Goal Planning -> Retrieval")
    print("          -> Mini Validation -> Filtering -> Execution")
    print("  Model : gemini-2.5-flash | Thinking : Enabled")
    print("  Logs  : app/agents/logs/agents.log")
    print("  Type your query and press Enter.")
    print("  Type 'exit' or 'quit' to stop.")
    print("=" * 70)
    print()

    conversation_history = []

    while True:
        # -- Read user input --------------------------------------------------
        try:
            raw = input("  Query > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  Session ended.\n")
            break

        if not raw:
            continue

        if raw.lower() in ("exit", "quit", "q"):
            print("\n  Session ended.\n")
            break

        # -- Run the agent pipeline -------------------------------------------
        print()
        print("-" * 70)

        try:
            final_state = await run_agent_pipeline(
                user_query=raw,
                conversation_history=conversation_history,
                user_name="poc",
                user_id=1,
            )
        except Exception as exc:
            import traceback
            print(f"  [ERROR] Pipeline failed: {exc}")
            traceback.print_exc()
            print("-" * 70)
            print()
            continue

        # -- Print pipeline summary -------------------------------------------
        intent    = final_state.get("understood_intent") or {}
        plan      = final_state.get("goal_plan") or {}
        v_status  = final_state.get("validation_status", "--")
        retry_cnt = final_state.get("retry_count", 0)

        # Token summary across all agents
        u_think  = final_state.get("understanding_thinking_tokens") or 0
        g_think  = final_state.get("goal_thinking_tokens") or 0
        r_think  = final_state.get("retrieval_thinking_tokens") or 0
        va_think = final_state.get("validation_thinking_tokens") or 0
        f_think  = final_state.get("filtering_thinking_tokens") or 0
        e_think  = final_state.get("execution_thinking_tokens") or 0
        total_think = u_think + g_think + r_think + va_think + f_think + e_think

        print("-" * 70)
        print("  PIPELINE SUMMARY")
        print(f"  Intent      : {intent.get('intent_type', '--')} | Clarity: {intent.get('clarity', '--')}")
        print(f"  Approach    : {plan.get('approach', '--')} | Complexity: {plan.get('estimated_complexity', '--')}")
        print(f"  Validation  : {v_status} | Retries: {retry_cnt}")
        print(f"  Think Tokens: Understanding={u_think:,} | GoalPlan={g_think:,} | "
              f"Retrieval={r_think:,} | Validation={va_think:,} | "
              f"Filtering={f_think:,} | Execution={e_think:,} | "
              f"TOTAL={total_think:,}")
        print("-" * 70)

        # -- Print the final answer -------------------------------------------
        final_answer = final_state.get("final_answer")
        if final_answer:
            print()
            print("  ANSWER:")
            print()
            # Indent each line for readability in terminal
            for line in final_answer.split("\n"):
                print(f"  {line}")
            print()
        else:
            print("  [No answer produced]")
            print()

        print("-" * 70)
        print()

        # -- Build rich context for conversation history ----------------------
        entities      = intent.get("entities", {}) or {}
        filters       = entities.get("filters", {}) or {}
        modules       = entities.get("modules", [])
        group_by      = entities.get("group_by")
        is_agg        = entities.get("is_aggregate")
        tools_planned = plan.get("tools_required", [])
        approach      = plan.get("approach", "")
        complexity    = plan.get("estimated_complexity", "")

        filter_parts = [f"{k}={v!r}" for k, v in filters.items() if v is not None]
        if is_agg:
            filter_parts.append("is_aggregate=True")
        if group_by:
            filter_parts.append(f"group_by={group_by!r}")

        filter_str = ", ".join(filter_parts) if filter_parts else "none"
        tools_str  = ", ".join(tools_planned) if tools_planned else "none"
        module_str = ", ".join(modules) if modules else "unknown"

        rich_context = (
            f"[PREVIOUS TURN CONTEXT]\n"
            f"User asked: {raw}\n"
            f"Module(s) : {module_str}\n"
            f"Tool(s) planned: {tools_str}\n"
            f"Filters used: {filter_str}\n"
            f"Approach: {approach} | Complexity: {complexity}\n"
            f"Understanding: {intent.get('summary', '')}\n"
            f"Answer given: {(final_answer or '')[:200]}"
        )

        conversation_history.append({"role": "user",      "content": raw})
        conversation_history.append({"role": "assistant", "content": rich_context})

        # Keep last 10 messages (5 full turns)
        if len(conversation_history) > 10:
            conversation_history = conversation_history[-10:]


def main():
    asyncio.run(run_interactive())


if __name__ == "__main__":
    main()
