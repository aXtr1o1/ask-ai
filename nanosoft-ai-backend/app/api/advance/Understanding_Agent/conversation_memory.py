from collections import defaultdict
from threading import Lock
import logging

logger = logging.getLogger("advance.conversation_memory")


class ConversationMemory:
    def __init__(self):
        self._memory = defaultdict(list)
        self._lock = Lock()

    def add_conversation(
        self,
        session_id: str,
        user_query: str,
        assistant_response: str,
    ):
        """
        Store the latest user query and assistant response.
        """
        with self._lock:
            self._memory[session_id].append(
                {
                    "role": "user",
                    "content": user_query,
                }
            )

            self._memory[session_id].append(
                {
                    "role": "assistant",
                    "content": assistant_response,
                }
            )

            logger.info("=" * 60)
            logger.info("Conversation Stored")
            logger.info("Session ID : %s", session_id)
            logger.info("History    : %s", self._memory[session_id])
            logger.info("=" * 60)

    def get_history(
        self,
        session_id: str,
        max_turns: int = 5,
    ) -> list[dict]:
        """
        Retrieve the latest conversation history.
        """
        with self._lock:
            history = self._memory.get(session_id, [])

            logger.info("=" * 60)
            logger.info("Conversation Retrieved")
            logger.info("Session ID : %s", session_id)
            logger.info("History    : %s", history)
            logger.info("=" * 60)

            if max_turns <= 0:
                return []

            return history[-max_turns * 2 :]

    def clear(self, session_id: str):
        """
        Clear conversation for a session.
        """
        with self._lock:
            self._memory.pop(session_id, None)

            logger.info("Conversation cleared for session %s", session_id)


# Singleton instance
conversation_memory = ConversationMemory()