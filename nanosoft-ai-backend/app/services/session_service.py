"""
Session Service — Fetch sessions and chat history from Supabase
"""
import logging
from app.api.database.supabase_client import get_supabase_client

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
        supabase = get_supabase_client()
        response = supabase.table("chat_sessions") \
            .select("session_id, title,created_at, updated_at") \
            .eq("user_id", user_id) \
            .order("updated_at", desc=True) \
            .execute()

        sessions = response.data or []
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
        supabase = get_supabase_client()
        response = supabase.table("chat_sessions") \
            .select("chat_history") \
            .eq("user_id", user_id) \
            .eq("session_id", session_id) \
            .single() \
            .execute()

        if not response.data:
            logger.info(f"⚠️ No session found | session_id={session_id} | user_id={user_id}")
            return []

        history = response.data.get("chat_history", [])
        logger.info(f"✅ Chat history fetched | session_id={session_id} | messages={len(history)}")
        return history

    except Exception as e:
        logger.error(f"❌ Failed to fetch chat history | session_id={session_id} | error={e}", exc_info=True)
        return []