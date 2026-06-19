# -*- coding: utf-8 -*-
"""
Standalone Test Runner -- Multi-Agent Pipeline (Phase 1)

Run this script to test the Understanding Agent + Goal Planning Agent.
Type your queries directly in the terminal. The agents will process each
query and print their full structured reasoning to the console.

Zero changes to the existing langchain_service.py system.

HOW TO RUN (from nanosoft-ai-backend/):
    $env:PYTHONUTF8=1; .\app\venv\Scripts\python -m app.agents.run_agents
"""

import asyncio
import logging
import sys
import io

# -- Force UTF-8 on Windows stdout --------------------------------------------
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# -- Root logging setup -------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Suppress noisy third-party loggers
for _noisy in ("httpx", "httpcore", "google.auth", "urllib3", "asyncio"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


# -- Main interactive loop ----------------------------------------------------

async def run_interactive():
    """
    Interactive REPL: type a query, agents process it, logs appear in console.
    Conversation history is maintained across turns for follow-up queries.
    Type 'exit' or 'quit' to stop.
    """
    from app.agents.multi_agent_graph import run_agent_pipeline

    print()
    print("=" * 70)
    print("  ASK-AI Multi-Agent Pipeline -- Phase 1 Test Runner")
    print("  Model : gemini-2.5-flash | Thinking : Enabled")
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
                user_name="test_user",
            )
        except Exception as exc:
            import traceback
            print(f"  [ERROR] Pipeline failed: {exc}")
            traceback.print_exc()
            print("-" * 70)
            print()
            continue

        # -- Print final summary line -----------------------------------------
        intent = final_state.get("understood_intent") or {}
        plan   = final_state.get("goal_plan") or {}

        print("-" * 70)
        print(f"  RESULT SUMMARY")
        print(f"  Intent     : {intent.get('intent_type', '--')} | Clarity: {intent.get('clarity', '--')}")
        print(f"  Approach   : {plan.get('approach', '--')} | Complexity: {plan.get('estimated_complexity', '--')}")
        print(f"  Tools      : {plan.get('tools_required', [])}")
        print(f"  Summary    : {intent.get('summary', '--')}")
        print("-" * 70)
        
        retrieval_results = final_state.get("retrieval_results")
        if retrieval_results:
            print()
            print("  RETRIEVAL DATA OUTPUT:")
            import json
            print(json.dumps(retrieval_results, indent=2))
        print()

        # -- Build a rich assistant context entry for history -----------------
        # Problem if we store only intent summary:
        #   Next query "give me 5 of them" → agent sees no tool name, no filters
        #   → cannot carry forward ASSETS_TOOL + status="online" etc.
        #
        # Fix: store a structured context that includes:
        #   - Module(s) that were active
        #   - Tool(s) that were planned
        #   - All filters that were extracted
        #   - Approach and complexity
        #
        # The Understanding Agent reads this on the next query and knows EXACTLY
        # what was running, what params were in play, enabling proper follow-ups.

        # Gather filter fields from understanding intent
        entities   = intent.get("entities", {}) or {}
        filters    = entities.get("filters", {}) or {}
        modules    = entities.get("modules", [])
        group_by   = entities.get("group_by")
        is_agg     = entities.get("is_aggregate")

        # Gather tool and approach from goal plan
        tools_planned = plan.get("tools_required", [])
        approach      = plan.get("approach", "")
        complexity    = plan.get("estimated_complexity", "")

        # Build filter summary — only non-null fields
        filter_parts = [f"{k}={v!r}" for k, v in filters.items() if v is not None]
        if is_agg:
            filter_parts.append(f"is_aggregate=True")
        if group_by:
            filter_parts.append(f"group_by={group_by!r}")

        filter_str = ", ".join(filter_parts) if filter_parts else "none"
        tools_str  = ", ".join(tools_planned) if tools_planned else "none"
        module_str = ", ".join(modules) if modules else "unknown"

        # Rich assistant context — structured so the model can parse it on next turn
        rich_context = (
            f"[PREVIOUS TURN CONTEXT]\n"
            f"User asked: {raw}\n"
            f"Module(s) : {module_str}\n"
            f"Tool(s) planned: {tools_str}\n"
            f"Filters used: {filter_str}\n"
            f"Approach: {approach} | Complexity: {complexity}\n"
            f"Understanding: {intent.get('summary', '')}"
        )

        conversation_history.append({"role": "user",      "content": raw})
        conversation_history.append({"role": "assistant", "content": rich_context})

        # Keep last 10 messages (5 full turns = 10 messages)
        if len(conversation_history) > 10:
            conversation_history = conversation_history[-10:]


def main():
    asyncio.run(run_interactive())


if __name__ == "__main__":
    main()
