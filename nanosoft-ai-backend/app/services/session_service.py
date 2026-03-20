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


async def get_sessions_for_user(user_name: str) -> list:
    """
    Returns all sessions for a given user_name.
    Each session contains: session_id, title, created_at, updated_at (no chat_history).
    """
    conn = None
    try:
        conn = get_pool()
        conn.rollback()  # clear any previous failed transaction
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT session_id, title, created_at, updated_at
            FROM chat_sessions
            WHERE user_name = %s
            ORDER BY updated_at DESC
            """,
            (user_name,)
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

        logger.info(f"✅ Sessions fetched | user_name={user_name} | count={len(sessions)}")
        return sessions

    except Exception as e:
        logger.error(f"❌ Failed to fetch sessions | user_name={user_name} | error={e}", exc_info=True)
        try:
            if conn is not None and not getattr(conn, "closed", True):
                conn.rollback()
        except Exception:
            pass
        return []


async def get_chat_history_for_session(user_name: str, session_id: str) -> list:
    """
    Returns full chat_history for a given session_id + user_name.
    Returns list of {query, assistant} dicts.
    """
    conn = None
    try:
        conn = get_pool()
        conn.rollback()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT chat_history FROM chat_sessions
            WHERE user_name = %s AND session_id = %s
            """,
            (user_name, session_id)
        )

        row = cursor.fetchone()
        cursor.close()

        if not row:
            logger.info(f"⚠️ No session found | session_id={session_id} | user_name={user_name}")
            return []

        history = row[0] if row[0] is not None else []
        if isinstance(history, str):
            history = json.loads(history) if history else []

        # strip context field — frontend does not need it
        # ──          query  → plain text OR base64 audio string
        # ──          assistant → full AI response for display
        # ──          is_audio  → bool flag for frontend rendering
        filtered_history = [
            {
                "query":     item.get("query",     ""),
                "assistant": item.get("assistant", ""),
                "context":   item.get("context", ""),
                "is_audio":  item.get("is_audio",  False)
            }
            for item in history
        ]

        logger.info(f"✅ Chat history fetched | session_id={session_id} | messages={len(filtered_history)}")
        return filtered_history

    except Exception as e:
        logger.error(f"❌ Failed to fetch chat history | session_id={session_id} | error={e}", exc_info=True)
        try:
            if conn is not None and not getattr(conn, "closed", True):
                conn.rollback()
        except Exception:
            pass
        return []