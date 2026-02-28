"""
Chat session persistence — Save and retrieve chat session history (PostgreSQL).
"""
import logging
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.api.database.postgres_client import get_pool
from app.config import settings

logger = logging.getLogger("postgres_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)

# for Title generation  no tools needed 
def _get_title_model():
    return ChatGoogleGenerativeAI(
        model=settings.GOOGLE_AI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY
    )

# Generate crisp title from first 3 interactions
async def generate_session_title(history: list) -> str:
    """
    Takes first 3 interactions from chat history and generates
    a crisp 4-6 word title using the LLM.
    """
    if not history:
        return "New Chat"

    try:
        # Take only first 3 interactions
        first_3 = history[:3]

        # Build a simple summary text from the interactions
        conversation_text = ""
        for item in first_3:
            conversation_text += f"User: {item.get('query', '')}\n"
            conversation_text += f"Assistant: {item.get('assistant', '')[:100]}\n\n"

        messages = [
            SystemMessage(content=(
                "You are a title generator. "
                "Given a chat conversation, generate a crisp, clear title of 4-6 words maximum. "
                "The title should describe what the conversation is about. "
                "Return ONLY the title text. No quotes, no punctuation, no explanation."
                "you can refer examples like  PPM Schedule Status Check,General Greeting,Online Assets Count Query,Breakdown Complaint Overview"
            )),
            HumanMessage(content=f"Generate a title for this conversation:\n\n{conversation_text}")
        ]

        model    = _get_title_model()
        response = model.invoke(messages)
        title    = str(response.content).strip()

        # Safety: if title is too long or empty, fallback 
        #setting 60 as of now comparing with the length of the title
        if not title or len(title) > 60:
            title = "New Chat"

        logger.info(f"✅ Title generated: '{title}'")
        return title

    except Exception as e:
        logger.error(f"❌ Title generation failed: {e}", exc_info=True)
        return "New Chat"


 # ── Save session to PostgreSQL ─────────────────────────────────────────────────
async def save_session_to_postgres_service(session_id: str, user_id: str, history: list):
    """
    Saves chat session history + generated title to PostgreSQL (chat_sessions).
    Called on WebSocket disconnect (timeout or client disconnect).
    Uses upsert on session_id (insert or update).
    """
    logger.info("trying to store the data in the db")
    if not history:
        logger.info(f"⚠️ Empty history for session_id: {session_id} — skipping save")
        return

    try:
        title = await generate_session_title(history)
        conn = get_pool()
        history_json = json.dumps(history)

        with conn.cursor() as cur:
            try:
                # Upsert: requires UNIQUE(session_id). Run scripts/add_session_id_unique.sql if missing.
                cur.execute(
                    """
                    INSERT INTO chat_sessions (session_id, user_id, chat_history, title, updated_at)
                    VALUES (%s, %s, %s::jsonb, %s, NOW())
                    ON CONFLICT (session_id) DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        chat_history = EXCLUDED.chat_history,
                        title = EXCLUDED.title,
                        updated_at = NOW()
                    """,
                    (session_id, user_id, history_json, title),
                )
            except Exception as conflict_err:
                if "unique or exclusion constraint" in str(conflict_err).lower() or "on_conflict" in str(conflict_err).lower():
                    # Fallback: update if row exists, else insert
                    cur.execute(
                        "SELECT 1 FROM chat_sessions WHERE session_id = %s",
                        (session_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        cur.execute(
                            """
                            UPDATE chat_sessions
                            SET user_id = %s, chat_history = %s::jsonb, title = %s, updated_at = NOW()
                            WHERE session_id = %s
                            """,
                            (user_id, history_json, title, session_id),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO chat_sessions (session_id, user_id, chat_history, title, updated_at)
                            VALUES (%s, %s, %s::jsonb, %s, NOW())
                            """,
                            (session_id, user_id, history_json, title),
                        )
                else:
                    raise
            conn.commit()

        logger.info(f"✅ PostgreSQL save successful | session_id={session_id} | title='{title}' | messages={len(history)}")

    except Exception as e:
        logger.error(f"❌ PostgreSQL save failed | session_id={session_id} | error={e}", exc_info=True)


