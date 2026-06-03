# app/state.py
from app.config import settings

MAX_HISTORY: int = settings.MAX_HISTORY
memory_store: dict = {}
frontend_saved_sessions: set = set()


def cap_history(history: list, max_entries: int) -> list:
    """Keep at most max_entries chat turns. max_entries <= 0 clears history."""
    if max_entries <= 0:
        return []
    if len(history) <= max_entries:
        return history
    return history[-max_entries:]


def lc_memory_for_model(lc_memory: list, max_pairs: int) -> list:
    """Return lc_memory slice sent to the model (Human/AIMessage pairs)."""
    if max_pairs <= 0:
        return []
    max_messages = max_pairs * 2
    if len(lc_memory) <= max_messages:
        return list(lc_memory)
    return lc_memory[-max_messages:]


def trim_session(session: dict, max_history: int) -> None:
    """In-place trim ``lc_memory`` (model context only).

    ``history`` is the full transcript for DB / frontend reload and is never
    capped by ``MAX_HISTORY``.
    """
    session["lc_memory"] = lc_memory_for_model(session.get("lc_memory", []), max_history)
