"""
Session Service — Fetch sessions and chat history from Supabase
"""
"""
Session Service — Fetch sessions and chat history from Supabase
"""
import logging
from app.api.database.postgresql_client import get_postgresql_client

logger = logging.getLogger("session_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)

#this function is used to fetch all the availabe sessions to the users   when he log ins 
async def get_sessions_for_user(user_id: str) -> list:
    """
    Returns all sessions for a given user_id.
    Each session contains: session_id, created_at, updated_at
    (NO chat_history — just the session list)
    """
    try:
        db = get_postgresql_client()
        import psycopg2.extras
        with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT session_id, title, created_at, updated_at
                FROM chat_sessions
                WHERE user_id = %s
                ORDER BY updated_at DESC
                """,
                (user_id,)
            )
            sessions = cur.fetchall()
        logger.info(f"✅ Sessions fetched | user_id={user_id} | count={len(sessions)}")
        return sessions

    except Exception as e:
        logger.error(f"❌ Failed to fetch sessions | user_id={user_id} | error={e}", exc_info=True)
        return []

#this function is used to send the  only the chat history  to the user for  the respective sessions

async def get_chat_history_for_session(user_id: str, session_id: str) -> list:
    """
    Returns full chat_history for a given session_id + user_id.
    Returns list of {query, assistant} dicts.
    """
    try:
        db = get_postgresql_client()
        import psycopg2.extras
        with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT chat_history
                FROM chat_sessions
                WHERE user_id = %s AND session_id = %s
                """,
                (user_id, session_id)
            )
            row = cur.fetchone()
        if not row:
            logger.info(f"⚠️ No session found | session_id={session_id} | user_id={user_id}")
            return []
        history = row.get("chat_history", [])
        logger.info(f"✅ Chat history fetched | session_id={session_id} | messages={len(history)}")
        return history

    except Exception as e:
        logger.error(f"❌ Failed to fetch chat history | session_id={session_id} | error={e}", exc_info=True)
        return []