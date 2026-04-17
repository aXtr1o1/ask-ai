"""
services/data/postgres_service.py
───────────────────────────────────
WRITE operations for chat sessions in PostgreSQL (chat_sessions table).

Functions:
    save_session_to_postgres_service() → upsert session + generate AI title
    update_session_title()             → rename a session
    delete_session_from_postgres()     → delete a session

Title generation:
    Uses first 3 interactions from history to generate a 4-6 word title via LLM.
    Runs as part of save_session — title is stored alongside history.

When sessions are saved:
    1. On WebSocket disconnect (if frontend hasn't already saved)
    2. On timeout (WS_SESSION_TIMEOUT exceeded)
    3. When frontend sends chat history via POST /api/session (preferred path)
"""

import logging
import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.api.database.postgres_client import get_pool
from app.config import settings
import asyncio

logger = logging.getLogger("services.data.postgres_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


def _get_title_model():
    """Get a fresh LLM instance for title generation."""
    return ChatGoogleGenerativeAI(
        model=settings.GOOGLE_AI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY
    )


def strip_html(text: str) -> str:
    """
    Remove HTML tags and normalize whitespace.
    Needed because assistant responses may contain HTML tables.
    Title generation should never see raw HTML.
    """
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


async def generate_session_title(history: list) -> str:
    """
    Generate a 4-6 word session title from the first 3 interactions.

    Why only first 3:
        First few messages establish the topic — later messages are follow-ups.
        Using all messages would produce generic titles.

    Audio handling:
        Audio queries are stored as base64 strings.
        Title generation uses "[voice query]" placeholder for audio items.

    Returns "New Chat" on any failure — never crashes the save operation.
    """
    if not history:
        return "New Chat"

    try:
        first_3 = history[:3]
        conversation_text = ""

        for item in first_3:
            # Audio queries → use placeholder (base64 is useless for title gen)
            if item.get("is_audio", False):
                user_part = "[voice query]"
            else:
                query_raw = item.get("query", "")
                user_part = strip_html(query_raw) if query_raw else ""

            # Strip HTML from assistant response — may contain <div> table markup
            assistant_raw  = item.get("context", "") or item.get("assistant", "")
            assistant_part = strip_html(assistant_raw)[:100]

            conversation_text += f"User: {user_part}\n"
            conversation_text += f"Assistant: {assistant_part}\n\n"

        logger.info("[POSTGRES] Title generation input:\n%s", conversation_text[:300])

        messages = [
            SystemMessage(content=(
                "You are a title generator. "
                "Given a chat conversation, generate a crisp, clear title of 4-6 words maximum. "
                "The title should describe what the conversation is about. "
                "Return ONLY the title text. No quotes, no punctuation, no explanation. "
                "Examples: 'PPM Schedule Status Check', 'General Greeting', 'Asset Count by Division'"
            )),
            HumanMessage(content=f"Generate a title for this conversation:\n\n{conversation_text}")
        ]

        model = _get_title_model()
        try:
            # 20s timeout — title generation is non-critical
            response = await asyncio.wait_for(
                asyncio.to_thread(model.invoke, messages),
                timeout=20.0
            )
        except asyncio.TimeoutError:
            logger.warning("[POSTGRES] Title generation timed out — using 'New Chat'")
            return "New Chat"

        title = str(response.content).strip()

        # Sanity check — reject if too long or empty
        if not title or len(title) > 60:
            title = "New Chat"

        logger.info("✅ [POSTGRES] Title generated: '%s'", title)
        return title

    except Exception as e:
        logger.error("❌ [POSTGRES] Title generation failed | error=%s", e, exc_info=True)
        return "New Chat"


async def save_session_to_postgres_service(session_id: str, user_name: str, history: list):
    """
    Upsert chat session into chat_sessions table.

    Why upsert (ON CONFLICT):
        The same session may be saved multiple times:
        - Frontend saves via HTTP POST
        - WebSocket disconnect also tries to save
        ON CONFLICT ensures the latest history always wins.

    Steps:
        1. Generate AI title from first 3 interactions
        2. Serialize history to JSON
        3. Upsert into chat_sessions

    Falls back to UPDATE if INSERT fails for any reason.
    """
    logger.info("[POSTGRES] Saving session | session_id=%s | user_name=%s | messages=%d",
                session_id, user_name, len(history))

    if not history:
        logger.info("[POSTGRES] Empty history — skipping save | session_id=%s", session_id)
        return

    try:
        title        = await generate_session_title(history)
        conn         = get_pool()
        conn.rollback()   # clear any previous failed transaction
        history_json = json.dumps(history)

        with conn.cursor() as cur:
            try:
                # Primary path: INSERT with ON CONFLICT upsert
                cur.execute(
                    """
                    INSERT INTO chat_sessions (session_id, user_name, chat_history, title, updated_at)
                    VALUES (%s, %s, %s::jsonb, %s, NOW())
                    ON CONFLICT (session_id) DO UPDATE SET
                        user_name    = EXCLUDED.user_name,
                        chat_history = EXCLUDED.chat_history,
                        title        = EXCLUDED.title,
                        updated_at   = NOW()
                    """,
                    (session_id, user_name, history_json, title),
                )
            except Exception as conflict_err:
                # Fallback path: manual INSERT or UPDATE if upsert syntax fails
                if "unique or exclusion constraint" in str(conflict_err).lower() or "on_conflict" in str(conflict_err).lower():
                    logger.warning("[POSTGRES] ON CONFLICT failed — falling back to manual INSERT/UPDATE")
                    cur.execute("SELECT 1 FROM chat_sessions WHERE session_id = %s", (session_id,))
                    row = cur.fetchone()
                    if row:
                        cur.execute(
                            """
                            UPDATE chat_sessions
                            SET user_name = %s, chat_history = %s::jsonb, title = %s, updated_at = NOW()
                            WHERE session_id = %s
                            """,
                            (user_name, history_json, title, session_id),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO chat_sessions (session_id, user_name, chat_history, title, updated_at)
                            VALUES (%s, %s, %s::jsonb, %s, NOW())
                            """,
                            (session_id, user_name, history_json, title),
                        )
                else:
                    raise

            conn.commit()

        logger.info(
            "✅ [POSTGRES] Session saved | session_id=%s | title='%s' | messages=%d",
            session_id, title, len(history),
        )

    except Exception as e:
        logger.error("❌ [POSTGRES] Save failed | session_id=%s | error=%s", session_id, e, exc_info=True)
        try:
            conn = get_pool()
            if conn and not conn.closed:
                conn.rollback()
        except Exception:
            pass


async def update_session_title(session_id: str, user_name: str, title: str) -> bool:
    """
    Update the title for an existing session.
    Called when user manually renames a session from the UI.

    Returns True on success, False on failure.
    """
    logger.info("[POSTGRES] Updating session title | session_id=%s | new_title='%s'", session_id, title)

    try:
        conn = get_pool()
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET title = %s, updated_at = NOW()
                WHERE session_id = %s AND user_name = %s
                """,
                (title, session_id, user_name),
            )
            conn.commit()
        logger.info("✅ [POSTGRES] Title updated | session_id=%s | title='%s'", session_id, title)
        return True

    except Exception as e:
        logger.error("❌ [POSTGRES] Title update failed | session_id=%s | error=%s", session_id, e, exc_info=True)
        try:
            conn = get_pool()
            if conn and not conn.closed:
                conn.rollback()
        except Exception:
            pass
        return False


async def delete_session_from_postgres(session_id: str, user_name: str) -> bool:
    """
    Delete a chat session for a user.
    Called when user deletes a session from the UI.

    Both session_id AND user_name required — prevents cross-user deletion.
    Returns True on success, False on failure.
    """
    logger.info("[POSTGRES] Deleting session | session_id=%s | user_name=%s", session_id, user_name)

    try:
        conn = get_pool()
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM chat_sessions
                WHERE session_id = %s AND user_name = %s
                """,
                (session_id, user_name),
            )
            conn.commit()
        logger.info("✅ [POSTGRES] Session deleted | session_id=%s", session_id)
        return True

    except Exception as e:
        logger.error("❌ [POSTGRES] Delete failed | session_id=%s | error=%s", session_id, e, exc_info=True)
        try:
            conn = get_pool()
            if conn and not conn.closed:
                conn.rollback()
        except Exception:
            pass
        return False