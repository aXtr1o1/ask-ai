"""
Session Service — Fetch sessions and chat history from PostgreSQL (chat_sessions).
"""
import logging
import json
from app.api.database.postgres_client import get_pool

logger = logging.getLogger("session_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


async def get_sessions_for_user(user_id: str) -> list:
    """
    Returns all sessions for a given user_id.
    Each session contains: session_id, title, created_at, updated_at (no chat_history).
    """
    try:
        conn   = get_pool()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT session_id, title, created_at, updated_at
            FROM chat_sessions
            WHERE user_id = %s
            ORDER BY updated_at DESC
            """,
            (user_id,)
        )

        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        cursor.close()

        sessions = [
            {
                "session_id": row[cols.index("session_id")],
                "title":      row[cols.index("title")],
                "created_at": row[cols.index("created_at")].isoformat() if row[cols.index("created_at")] else None,
                "updated_at": row[cols.index("updated_at")].isoformat() if row[cols.index("updated_at")] else None,
            }
            for row in rows
        ]

        logger.info(f"✅ Sessions fetched | user_id={user_id} | count={len(sessions)}")
        return sessions

    except Exception as e:
        logger.error(f"❌ Failed to fetch sessions | user_id={user_id} | error={e}", exc_info=True)
        return []


async def get_chat_history_for_session(user_id: str, session_id: str) -> list:
    """
    Returns full chat_history for a given session_id + user_id.
    Returns list of {query, assistant} dicts.
    """
    try:
        conn   = get_pool()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT chat_history FROM chat_sessions
            WHERE user_id = %s AND session_id = %s
            """,
            (user_id, session_id)
        )

        row = cursor.fetchone()
        cursor.close()

        if not row:
            logger.info(f"⚠️ No session found | session_id={session_id} | user_id={user_id}")
            return []

        history = row[0] if row[0] is not None else []
        if isinstance(history, str):
            history = json.loads(history) if history else []

        logger.info(f"✅ Chat history fetched | session_id={session_id} | messages={len(history)}")
        return history

    except Exception as e:
        logger.error(f"❌ Failed to fetch chat history | session_id={session_id} | error={e}", exc_info=True)
        return []