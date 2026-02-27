"""
Session Service — Fetch sessions and chat history from PostgreSQL (chat_sessions).
"""
import logging
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
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT session_id, title, created_at, updated_at
            FROM chat_sessions
            WHERE user_id = $1
            ORDER BY updated_at DESC
            """,
            user_id,
        )
        sessions = [
            {
                "session_id": r["session_id"],
                "title": r["title"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
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
        pool = await get_pool()
        row = await pool.fetchrow(
            """
            SELECT chat_history FROM chat_sessions
            WHERE user_id = $1 AND session_id = $2
            """,
            user_id,
            session_id,
        )
        if not row:
            logger.info(f"⚠️ No session found | session_id={session_id} | user_id={user_id}")
            return []

        history = row["chat_history"] if row["chat_history"] is not None else []
        if isinstance(history, str):
            import json
            history = json.loads(history) if history else []  # fallback if returned as string
        logger.info(f"✅ Chat history fetched | session_id={session_id} | messages={len(history)}")
        return history

    except Exception as e:
        logger.error(f"❌ Failed to fetch chat history | session_id={session_id} | error={e}", exc_info=True)
        return []