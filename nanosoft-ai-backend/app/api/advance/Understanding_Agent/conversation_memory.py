"""
Conversation Memory — Structured Turn Storage

Each turn stores:
  user_query    : raw user input
  query_summary : Understanding Agent's cleaned, self-contained restatement
  intent        : general | db_query | web_search
  modules       : FM modules queried (empty for general/web_search)
  filter_fields : fields retrieved per module  (empty for general/web_search)
  filter_values : filter conditions per module (empty for general/web_search)

Two consumers:
  Understanding Agent → get_history()      → last 5 turns (full structured turns)
  Analysis Agent      → get_last_db_turn() → single most-recent db_query turn
"""
from collections import defaultdict
from threading import Lock
import logging

logger = logging.getLogger("advance.conversation_memory")


class ConversationMemory:
    def __init__(self):
        self._memory: dict[str, list[dict]] = defaultdict(list)
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def add_turn(
        self,
        session_id:       str,
        user_query:       str,
        query_summary:    str,
        intent:           str,
        modules:          list[str]       | None = None,
        filter_fields:    dict[str, dict] | None = None,
        filter_values:    dict[str, dict] | None = None,
        general_response: str             | None = None,
    ) -> None:
        """
        Store one conversation turn.  Single write point — never call this
        more than once per user query/response cycle.
        """
        turn = {
            "user_query":       user_query,
            "query_summary":    query_summary,
            "intent":           intent,
            "modules":          modules          or [],
            "filter_fields":    filter_fields    or {},
            "filter_values":    filter_values    or {},
            "general_response": general_response or "",
        }
        with self._lock:
            self._memory[session_id].append(turn)
            total = len(self._memory[session_id])

            logger.info("┌─ [Memory] STORED turn #%d — session=%s", total, session_id)
            logger.info("│  intent        : %s", intent)
            logger.info("│  user_query    : %s", user_query)
            logger.info("│  query_summary : %s", query_summary)
            logger.info("│  modules       : %s", modules or [])
            if filter_values:
                for mod, vals in (filter_values or {}).items():
                    logger.info("│  filter_values : [%s] %s", mod, vals)
            else:
                logger.info("│  filter_values : (none)")
            logger.info("└─ total turns in session: %d", total)

    # ------------------------------------------------------------------
    # Read — Understanding Agent
    # ------------------------------------------------------------------
    def get_history(
        self,
        session_id: str,
        max_turns:  int = 5,
    ) -> list[dict]:
        """
        Return the last *max_turns* structured turns for the Understanding Agent.
        """
        with self._lock:
            history = self._memory.get(session_id, [])
            if max_turns <= 0:
                return []
            result = history[-max_turns:]
            logger.info(
                "[Memory] get_history — session=%s returned=%d/%d turns",
                session_id, len(result), len(history),
            )
            return result

    # ------------------------------------------------------------------
    # Read — Analysis Agent
    # ------------------------------------------------------------------
    def get_last_db_turn(self, session_id: str) -> dict | None:
        """
        Return the most recent db_query turn for the Analysis Agent context.
        """
        with self._lock:
            history = self._memory.get(session_id, [])
            for turn in reversed(history):
                if turn.get("intent") == "db_query":
                    logger.info(
                        "[Memory] get_last_db_turn — session=%s → modules=%s | filters=%s",
                        session_id,
                        turn.get("modules"),
                        {m: list(v.keys()) for m, v in turn.get("filter_values", {}).items()},
                    )
                    return turn
            logger.info(
                "[Memory] get_last_db_turn — session=%s → no db_query turn found (fresh query)",
                session_id,
            )
            return None

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------
    def clear(self, session_id: str) -> None:
        """Clear all conversation history for a session."""
        with self._lock:
            self._memory.pop(session_id, None)
            logger.info("[ConversationMemory] cleared — session=%s", session_id)


# Singleton instance shared across all agents
conversation_memory = ConversationMemory()