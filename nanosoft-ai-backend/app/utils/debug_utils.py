"""
app/utils/debug_utils.py
─────────────────────────
Debug helpers for inspecting in-memory session state.

Functions:
    print_memory() → prints lc_memory and history for a session to stdout
"""

import logging
from app.state import memory_store, MAX_HISTORY

logger = logging.getLogger("utils.debug_utils")


def print_memory(session_id: str) -> None:
    """Debug helper — prints lc_memory and history for a session."""
    session_data = memory_store.get(session_id, {})
    history      = session_data.get("history", [])
    lc_memory    = session_data.get("lc_memory", [])

    print(f"\n🧠 SESSION: {session_id} | user: {session_data.get('user_name', 'N/A')}")
    print(f"\n💾 HISTORY ({len(history)} entries)")
    for i, item in enumerate(history, 1):
        raw_query    = item.get("query", "")
        is_audio     = item.get("is_audio", False)
        display_q    = (
            "[AUDIO 🎙️]"
            if (is_audio or (isinstance(raw_query, str) and raw_query.startswith("data:audio")))
            else (raw_query[:100] + ("..." if len(raw_query) > 100 else ""))
        )
        print(f"  [{i}] Query:     {display_q}")
        print(f"       Assistant: {item['assistant'][:100]}{'...' if len(item['assistant']) > 100 else ''}")

    print(f"\n🤖 LC_MEMORY ({len(lc_memory) // 2} pairs | last {MAX_HISTORY} sent to model)")
    pairs = list(zip(lc_memory[0::2], lc_memory[1::2]))
    for i, (h, a) in enumerate(pairs, 1):
        h_content = h.content or ""
        print(f"  [{i}] Query:     {h_content[:100]}{'...' if len(h_content) > 100 else ''}")
        print(f"       Assistant: {(a.content or '')[:100]}")
    print()