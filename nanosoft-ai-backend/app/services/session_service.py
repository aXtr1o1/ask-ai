"""
Session Service — Fetch sessions and chat history from PostgreSQL (chat_sessions).
"""
import logging
import json
import random
import string
import uuid
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
            SELECT session_id, title, created_at, updated_at,
                   COALESCE(is_pinned, FALSE)  AS is_pinned,
                   COALESCE(is_archived, FALSE) AS is_archived
            FROM chat_sessions
            WHERE user_name = %s
            ORDER BY COALESCE(is_pinned, FALSE) DESC, updated_at DESC
            """,
            (user_name,)
        )

        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        cursor.close()
        conn.rollback() # Finish the read-only transaction

        sessions = [
            {
                "session_id":  row[cols.index("session_id")],
                "title":       row[cols.index("title")],
                "created_at":  row[cols.index("created_at")].isoformat() if row[cols.index("created_at")] else None,
                "updated_at":  row[cols.index("updated_at")].isoformat() if row[cols.index("updated_at")] else None,
                "is_pinned":   bool(row[cols.index("is_pinned")]),
                "is_archived": bool(row[cols.index("is_archived")]),
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
        conn.rollback() # Finish the read-only transaction

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

# changes done by megnathan: Added share code generation and session cloning logic */

async def generate_share_code(session_id: str, user_name: str) -> str:
    """Generates a unique 5-digit share code for a session and stores it."""
    conn = None
    try:
        conn = get_pool()
        conn.rollback()
        
        # 1. Check if session already has a code
        with conn.cursor() as cur:
            cur.execute(
                "SELECT share_code FROM chat_sessions WHERE session_id = %s AND user_name = %s",
                (session_id, user_name)
            )
            row = cur.fetchone()
            if row and row[0]:
                return row[0]

            # 2. Generate unique code
            max_tries = 10
            for _ in range(max_tries):
                new_code = ''.join(random.choices(string.digits, k=5))
                # Check uniqueness
                cur.execute("SELECT 1 FROM chat_sessions WHERE share_code = %s", (new_code,))
                if not cur.fetchone():
                    # Store it
                    cur.execute(
                        "UPDATE chat_sessions SET share_code = %s WHERE session_id = %s AND user_name = %s",
                        (new_code, session_id, user_name)
                    )
                    
                    if cur.rowcount == 0:
                        # Case: Session doesn't exist in DB yet (e.g. empty new chat)
                        # We create it now so we can share it
                        logger.info(f"ℹ️ Session not found during share code generation. Creating new empty session | session_id={session_id}")
                        cur.execute(
                            """
                            INSERT INTO chat_sessions (session_id, user_name, chat_history, title, updated_at, share_code)
                            VALUES (%s, %s, %s::jsonb, %s, NOW(), %s)
                            """,
                            (session_id, user_name, json.dumps([]), "Shared Chat", new_code)
                        )
                        
                    conn.commit()
                    logger.info(f"✅ Share code generated and SAVED | code={new_code} | session_id={session_id}")
                    return new_code
            
            raise Exception("Failed to generate a unique share code after several attempts")

    except Exception as e:
        logger.error(f"❌ Failed to generate share code | session_id={session_id} | error={e}", exc_info=True)
        if conn: conn.rollback()
        return None

async def import_session_by_code(share_code: str, current_user: str) -> str:
    """Finds a session by share code and clones it for the current user."""
    conn = None
    logger.info(f"📥 [Import] Request received | code={share_code} | user={current_user}")
    try:
        conn = get_pool()
        conn.rollback()
        
        with conn.cursor() as cur:
            # 1. Find the source session
            logger.info(f"🔍 [Import] Searching for code '{share_code}' in database...")
            cur.execute(
                "SELECT chat_history, title FROM chat_sessions WHERE share_code = %s",
                (share_code,)
            )
            row = cur.fetchone()
            if not row:
                logger.warning(f"⚠️ [Import] INVALID CODE: No session found with share_code={share_code}")
                return None
            
            source_history, source_title = row
            new_session_id = str(uuid.uuid4())
            logger.info(f"✅ [Import] Source session found! Title: '{source_title}' | Messages: {len(source_history) if source_history else 0}")

            # 2. Clone it for the current user
            logger.info(f"💾 [Import] Cloning session for user '{current_user}' with new ID: {new_session_id}")
            cur.execute(
                """
                INSERT INTO chat_sessions (session_id, user_name, chat_history, title, updated_at)
                VALUES (%s, %s, %s::jsonb, %s, NOW())
                """,
                (new_session_id, current_user, json.dumps(source_history), source_title)
            )
            conn.commit()
            logger.info(f"🎉 [Import] SUCCESS: Session cloned successfully for {current_user}")
            return new_session_id

    except Exception as e:
        logger.error(f"❌ [Import] FATAL ERROR during cloning | code={share_code} | error={e}", exc_info=True)
        if conn: conn.rollback()
        return None