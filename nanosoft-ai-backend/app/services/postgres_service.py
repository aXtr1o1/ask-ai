"""
Chat session persistence — Save and retrieve chat session history (PostgreSQL).
"""
import logging
import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.api.database.postgres_client import get_pool
from app.config import settings
import asyncio

logger = logging.getLogger("postgres_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


def _get_title_model():
    return ChatGoogleGenerativeAI(
        model=settings.GOOGLE_AI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY
    )


# Strip HTML tags from text before using for title generation
def strip_html(text: str) -> str:
    """Remove HTML tags and clean up whitespace."""
    if not text:
        return ""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Remove extra whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


async def generate_session_title(history: list) -> str:
    """
    Takes first 3 interactions from chat history and generates
    a crisp 4-6 word title using the LLM.
    """
    if not history:
        return "New Chat"

    try:
        first_3 = history[:3]

        conversation_text = ""
        for item in first_3:
            # ── Audio query: show [voice query] placeholder
            if item.get("is_audio", False):
                user_part = "[voice query]"
            else:
                query_raw = item.get("query", "")
                # ✅ FIX: Strip HTML from query just in case
                user_part = strip_html(query_raw) if query_raw else ""

            #  Strip HTML from assistant text before title generation
            # assistant field may contain <div style="..."> HTML tags
            assistant_raw = item.get("context", "") or item.get("assistant", "")
            assistant_part = strip_html(assistant_raw)[:100]

            conversation_text += f"User: {user_part}\n"
            conversation_text += f"Assistant: {assistant_part}\n\n"

        logger.info(f"📝 Title generation input:\n{conversation_text}")

        messages = [
            SystemMessage(content=(
                "You are a title generator. "
                "Given a chat conversation, generate a crisp, clear title of 4-6 words maximum. "
                "The title should describe what the conversation is about. "
                "Return ONLY the title text. No quotes, no punctuation, no explanation. "
                "You can refer to examples like: PPM Schedule Status Check, General Greeting, "
            )),
            HumanMessage(content=f"Generate a title for this conversation:\n\n{conversation_text}")
        ]

        model = _get_title_model()
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(model.invoke, messages),
                timeout=20.0
            )
        except asyncio.TimeoutError:
            logger.warning("⚠️ Title generation timed out — using fallback")
            return "New Chat"
        
        title = str(response.content).strip()

        if not title or len(title) > 60:
            title = "New Chat"

        logger.info(f"✅ Title generated: '{title}'")
        return title

    except Exception as e:
        logger.error(f"❌ Title generation failed: {e}", exc_info=True)
        return "New Chat"


# ── Save session to PostgreSQL ──────────────────────────────────────────────
async def save_session_to_postgres_service(session_id: str, user_name: str, history: list, group_name: str = None):
    """
    Saves chat session history + generated title to PostgreSQL (chat_sessions).
    Uses upsert on session_id (insert or update).
    """
    logger.info("trying to store the data in the db")
    if not history:
        logger.info(f"⚠️ Empty history for session_id: {session_id} — skipping save")
        return

    try:
        title        = await generate_session_title(history)
        conn         = get_pool()
        conn.rollback()
        history_json = json.dumps(history)

        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO chat_sessions (session_id, user_name, chat_history, title, updated_at, group_name)
                    VALUES (%s, %s, %s::jsonb, %s, NOW(), %s)
                    ON CONFLICT (session_id) DO UPDATE SET
                        user_name    = EXCLUDED.user_name,
                        chat_history = EXCLUDED.chat_history,
                        title        = EXCLUDED.title,
                        updated_at   = NOW(),
                        group_name   = EXCLUDED.group_name
                    """,
                    (session_id, user_name, history_json, title, group_name),
                )
            except Exception as conflict_err:
                if "unique or exclusion constraint" in str(conflict_err).lower() or "on_conflict" in str(conflict_err).lower():
                    cur.execute(
                        "SELECT 1 FROM chat_sessions WHERE session_id = %s",
                        (session_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        cur.execute(
                            """
                            UPDATE chat_sessions
                            SET user_name = %s, chat_history = %s::jsonb, title = %s, updated_at = NOW(), group_name = %s
                            WHERE session_id = %s
                            """,
                            (user_name, history_json, title, group_name, session_id),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO chat_sessions (session_id, user_name, chat_history, title, updated_at, group_name)
                            VALUES (%s, %s, %s::jsonb, %s, NOW(), %s)
                            """,
                            (session_id, user_name, history_json, title, group_name),
                        )
                else:
                    raise
            conn.commit()

        logger.info(f"✅ PostgreSQL save successful | session_id={session_id} | title='{title}' | messages={len(history)}")

    except Exception as e:
        logger.error(f"❌ PostgreSQL save failed | session_id={session_id} | error={e}", exc_info=True)
        try:
            conn = get_pool()
            if conn and not conn.closed:
                conn.rollback()
        except Exception:
            pass

# added by sudharshan for updating the session title when the user renames the session
async def update_session_title(session_id: str, user_name: str, title: str) -> bool:
    """Update the title for an existing session. Returns True on success."""
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
            # If no row was updated, do nothing
            conn.commit()
        logger.info(f"✅ Session title updated | session_id={session_id} | title='{title}'")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to update session title | session_id={session_id} | error={e}", exc_info=True)
        try:
            conn = get_pool()
            if conn and not conn.closed:
                conn.rollback()
        except Exception:
            pass
        return False


async def toggle_pin_session(session_id: str, user_name: str, is_pinned: bool) -> bool:
    """Update the pinned status for a session. Returns True on success."""
    try:
        conn = get_pool()
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET is_pinned = %s, updated_at = NOW()
                WHERE session_id = %s AND LOWER(user_name) = LOWER(%s)
                """,
                (is_pinned, session_id, user_name),
            )
            rows_updated = cur.rowcount
            conn.commit()
        
        if rows_updated > 0:
            logger.info(f"✅ Session pin status updated | session_id={session_id} | is_pinned={is_pinned} | rows={rows_updated}")
        else:
            logger.warning(f"⚠️ No session found to pin | session_id={session_id} | user_name={user_name}")
        return rows_updated > 0
    except Exception as e:
        logger.error(f"❌ Failed to update session pin status | session_id={session_id} | error={e}", exc_info=True)
        try:
            conn = get_pool()
            if conn and not conn.closed:
                conn.rollback()
        except Exception:
            pass
        return False


async def toggle_archive_session(session_id: str, user_name: str, is_archived: bool) -> bool:
    """Update the archived status for a session. Returns True on success."""
    try:
        conn = get_pool()
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET is_archived = %s, updated_at = NOW()
                WHERE session_id = %s AND LOWER(user_name) = LOWER(%s)
                """,
                (is_archived, session_id, user_name),
            )
            rows_updated = cur.rowcount
            conn.commit()
            
        if rows_updated > 0:
            logger.info(f"✅ Session archive status updated | session_id={session_id} | is_archived={is_archived} | rows={rows_updated}")
        else:
            logger.warning(f"⚠️ No session found to archive | session_id={session_id} | user_name={user_name}")
        return rows_updated > 0
    except Exception as e:
        logger.error(f"❌ Failed to update session archive status | session_id={session_id} | error={e}", exc_info=True)
        try:
            conn = get_pool()
            if conn and not conn.closed:
                conn.rollback()
        except Exception:
            pass
        return False

# added by sudharshan for deleting the session when the user deletes the session from UI
async def delete_session_from_postgres(session_id: str, user_name: str) -> bool:
    """Delete a chat session for a user. Returns True on success."""
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
        logger.info(f"✅ Session deleted | session_id={session_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to delete session | session_id={session_id} | error={e}", exc_info=True)
        try:
            conn = get_pool()
            if conn and not conn.closed:
                conn.rollback()
        except Exception:
            pass
        return False

async def toggle_session_public(session_id: str, user_name: str, is_public: bool) -> bool:
    """Make a session public or private. Creates the record if it doesn't exist."""
    try:
        conn = get_pool()
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_sessions (session_id, user_name, is_public, chat_history, title, updated_at)
                VALUES (%s, %s, %s, '[]'::jsonb, 'New Chat', NOW())
                ON CONFLICT (session_id) DO UPDATE SET
                    is_public = EXCLUDED.is_public,
                    updated_at = NOW()
                """,
                (session_id, user_name, is_public),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to update public status | session_id={session_id} | error={e}", exc_info=True)
        return False

async def get_public_chat_history(session_id: str, owner: str = None) -> list:
    """Fetch history for a shared session if it is public."""
    try:
        conn = get_pool()
        conn.rollback()
        with conn.cursor() as cur:
            if owner:
                cur.execute(
                    "SELECT chat_history, is_public FROM chat_sessions WHERE session_id = %s AND LOWER(user_name) = LOWER(%s)",
                    (session_id, owner)
                )
            else:
                cur.execute(
                    "SELECT chat_history, is_public FROM chat_sessions WHERE session_id = %s",
                    (session_id,)
                )
            row = cur.fetchone()
            conn.rollback()
            if not row: return None
            
            history, is_public = row
            if not is_public:
                logger.warning(f"🔒 Attempt to access private session | session_id={session_id}")
                return None
            
            import json
            return history if isinstance(history, list) else json.loads(history)
    except Exception as e:
        logger.error(f"❌ Failed to fetch public history | error={e}")
        return None


async def create_folder(user_name: str, folder_name: str) -> bool:
    """Create a new folder for a user."""
    try:
        conn = get_pool()
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO "Groups_folderName" (user_name, folder_name, created_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (user_name, folder_name) DO NOTHING
                """,
                (user_name, folder_name),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create folder | user={user_name} | folder={folder_name} | error={e}", exc_info=True)
        return False


async def rename_folder(user_name: str, old_folder_name: str, new_folder_name: str) -> bool:
    """Rename a folder and update all chats inside it."""
    try:
        conn = get_pool()
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE "Groups_folderName"
                SET folder_name = %s
                WHERE user_name = %s AND folder_name = %s
                """,
                (new_folder_name, user_name, old_folder_name),
            )
            cur.execute(
                """
                UPDATE chat_sessions
                SET group_name = %s
                WHERE user_name = %s AND group_name = %s
                """,
                (new_folder_name, user_name, old_folder_name),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to rename folder | user={user_name} | old={old_folder_name} | new={new_folder_name} | error={e}", exc_info=True)
        return False


async def delete_folder(user_name: str, folder_name: str) -> bool:
    """Delete a folder and all chats inside it."""
    try:
        conn = get_pool()
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM "Groups_folderName"
                WHERE user_name = %s AND folder_name = %s
                """,
                (user_name, folder_name),
            )
            cur.execute(
                """
                DELETE FROM chat_sessions
                WHERE user_name = %s AND group_name = %s
                """,
                (user_name, folder_name),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Failed to delete folder | user={user_name} | folder={folder_name} | error={e}", exc_info=True)
        return False


async def get_folders(user_name: str) -> list:
    """Get all folders for a user."""
    try:
        conn = get_pool()
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT folder_name FROM "Groups_folderName"
                WHERE user_name = %s
                ORDER BY created_at ASC
                """,
                (user_name,),
            )
            rows = cur.fetchall()
            conn.rollback()
            return [row[0] for row in rows]
    except Exception as e:
        logger.error(f"❌ Failed to get folders | user={user_name} | error={e}", exc_info=True)
        return []
