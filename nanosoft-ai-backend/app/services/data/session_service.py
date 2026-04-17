"""
services/data/session_service.py
──────────────────────────────────
Fetches session list and chat history from PostgreSQL (chat_sessions table).

READ-ONLY — this file never writes to the DB.
All writes go through postgres_service.py.

Functions:
    get_sessions_for_user()         → list all sessions for a user (no chat history)
    get_chat_history_for_session()  → get full chat history for one session
"""

import logging
import json
from app.api.database.postgres_client import get_pool

logger = logging.getLogger("services.data.session_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


async def get_sessions_for_user(user_name: str) -> list:
    """
    Return all sessions for a user ordered by most recently updated.

    Used by the frontend to populate the session sidebar.
    Returns lightweight session objects — NO chat_history included (too large).

    Each returned dict:
        session_id → unique session identifier
        title      → AI-generated title for the session
        created_at → ISO timestamp
        updated_at → ISO timestamp (used for ordering)

    Args:
        user_name: the client_name / sub_user_name

    Returns:
        list of session dicts, empty list on error
    """
    conn = None
    logger.info("[SESSION] Fetching sessions | user_name=%s", user_name)

    try:
        conn = get_pool()
        conn.rollback()   # clear any failed transaction state
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
                # Convert datetime to ISO string for JSON serialization
                "created_at": row[cols.index("created_at")].isoformat() if row[cols.index("created_at")] else None,
                "updated_at": row[cols.index("updated_at")].isoformat() if row[cols.index("updated_at")] else None,
            }
            for row in rows
        ]

        logger.info("✅ [SESSION] Sessions fetched | user_name=%s | count=%d", user_name, len(sessions))
        return sessions

    except Exception as e:
        logger.error("❌ [SESSION] Failed to fetch sessions | user_name=%s | error=%s", user_name, e, exc_info=True)
        try:
            if conn is not None and not getattr(conn, "closed", True):
                conn.rollback()
        except Exception:
            pass
        return []


async def get_chat_history_for_session(user_name: str, session_id: str) -> list:
    """
    Return full chat history for a specific session.

    Used by the frontend when user clicks on an old session to view it.
    Returns filtered history — only fields needed by frontend.

    Each returned dict:
        query     → user's message (plain text or base64 audio string)
        assistant → AI's full response (may be JSON for table/graph responses)
        context   → short summary (used for title generation, not display)
        is_audio  → bool flag so frontend knows to render audio player instead of text

    Args:
        user_name:  the client_name / sub_user_name
        session_id: unique session identifier

    Returns:
        list of message dicts, empty list if not found or on error
    """
    conn = None
    logger.info("[SESSION] Fetching chat history | user_name=%s | session_id=%s", user_name, session_id)

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
            logger.info("[SESSION] Session not found | session_id=%s | user_name=%s", session_id, user_name)
            return []

        # chat_history may be JSONB (dict) or text — handle both
        history = row[0] if row[0] is not None else []
        if isinstance(history, str):
            history = json.loads(history) if history else []

        # Return only fields the frontend needs
        filtered_history = [
            {
                "query":     item.get("query",     ""),
                "assistant": item.get("assistant", ""),
                "context":   item.get("context",   ""),
                "is_audio":  item.get("is_audio",  False),
            }
            for item in history
        ]

        logger.info(
            "✅ [SESSION] Chat history fetched | session_id=%s | messages=%d",
            session_id, len(filtered_history),
        )
        return filtered_history

    except Exception as e:
        logger.error(
            "❌ [SESSION] Failed to fetch chat history | session_id=%s | error=%s",
            session_id, e, exc_info=True,
        )
        try:
            if conn is not None and not getattr(conn, "closed", True):
                conn.rollback()
        except Exception:
            pass
        return []