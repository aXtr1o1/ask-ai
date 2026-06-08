from fastapi import APIRouter, HTTPException
import logging
import asyncio
from app.models.schemas import SessionRequest, ClientInsertionRequest
from app.services.session_service import get_sessions_for_user, get_chat_history_for_session
from app.services.postgres_service import save_session_to_postgres_service
from app.state import frontend_saved_sessions
from app.api.database.postgres_client import get_pool
from app.services.sync.migrate_user import migrate_user
from app.services.user_profile_service import get_user_usage_stats

logger = logging.getLogger('app_endpoints')
app_endpoints_router = APIRouter()

@app_endpoints_router.post("/session")
async def sessions_endpoint(request: SessionRequest):
    user_name  = request.userName.strip()
    session_id = request.sessionId.strip()
    incoming_history = request.chatHistory or []

    if not user_name:
        logger.info("invalid user name")
        raise HTTPException(status_code=400, detail="userName is required")

    
    # ── Case 1: chatHistory present → save session to PostgreSQL ──
    if incoming_history:
        logger.info(f"💾 Saving chat history | user_name={user_name} | session_id={session_id} | messages={len(incoming_history)}")

        # Convert flat message list [{role,user/ai,text}] → [{query, assistant}] pairs
        history_pairs = []
        pending_query = None

        pending_is_audio = False
        for msg in incoming_history:
            role = (msg.role or "").lower()
            if role == "user":
                pending_query = msg.text or ""
                pending_is_audio = getattr(msg, "isAudio", False)
            elif role == "ai":
                if pending_query is not None:
                    history_pairs.append({
                        "query":     pending_query,
                        "assistant": msg.text or "",
                        "is_audio":  pending_is_audio,
                        "context":   msg.text or ""
                    })
                    pending_query    = None
                    pending_is_audio = False

        # If conversation ended with a user message but no assistant reply,
        # still persist it with empty assistant text so it's not lost.
        if pending_query:
            history_pairs.append({
                "query": pending_query,
                "assistant": ""
            })

        await save_session_to_postgres_service(
            session_id = session_id,
            user_name  = user_name,
            history    = history_pairs,
            group_name = request.group_name,
            is_space_booking = request.isSpaceBooking or False
        )
        #Mark this session as saved by frontend
        # So WebSocketDisconnect will NOT save it again
        frontend_saved_sessions.add(session_id)
        logger.info(f"🏷️ Marked session as frontend-saved | session={session_id}")

        return {
            "user_name":  user_name,
            "session_id": session_id,
            "type":       "saved",
            "messages":   len(history_pairs)
        }

    # ── Case 2: session_id is empty → return all sessions for user ──
    if not session_id:
        logger.info(f"📋 Fetching all sessions | user_name={user_name}")
        sessions = await get_sessions_for_user(user_name)
        return {
            "user_name": user_name,
            "type":      "sessions",
            "sessions":  sessions
        }

    # ── Case 3: session_id is provided → return chat history ──
    logger.info(f"💬 Fetching chat history | user_name={user_name} | session_id={session_id}")
    history = await get_chat_history_for_session(user_name, session_id)
    return {
        "user_name":     user_name,
        "session_id":    session_id,
        "type":          "history",
        "chat_history":  history
    }
#added by sudharshan for renmaing the session

@app_endpoints_router.post("/session/rename")
async def rename_session_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    session_id = str(payload.get("sessionId", "")).strip()
    title = str(payload.get("title", "")).strip()

    if not user_name or not session_id or not title:
        raise HTTPException(status_code=400, detail="userName, sessionId and title are required")

    from app.services.postgres_service import update_session_title
    ok = await update_session_title(session_id, user_name, title)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update session title")
    return {"status": "ok", "sessionId": session_id, "title": title}

#added by sudharshan for deleting the session
@app_endpoints_router.post("/session/delete")
async def delete_session_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    session_id = str(payload.get("sessionId", "")).strip()

    if not user_name or not session_id:
        raise HTTPException(status_code=400, detail="userName and sessionId are required")

    from app.services.postgres_service import delete_session_from_postgres
    ok = await delete_session_from_postgres(session_id, user_name)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete session")
    return {"status": "ok", "sessionId": session_id}
    
@app_endpoints_router.post("/sessions/pin")
async def pin_session_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    session_id = str(payload.get("sessionId", "")).strip()
    is_pinned = bool(payload.get("isPinned", False))

    if not user_name or not session_id:
        raise HTTPException(status_code=400, detail="userName and sessionId are required")

    from app.services.postgres_service import toggle_pin_session
    ok = await toggle_pin_session(session_id, user_name, is_pinned)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat session not found for this user")
    return {"status": "ok", "sessionId": session_id, "isPinned": is_pinned}

@app_endpoints_router.post("/sessions/archive")
async def archive_session_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    session_id = str(payload.get("sessionId", "")).strip()
    is_archived = bool(payload.get("isArchived", False))

    if not user_name or not session_id:
        raise HTTPException(status_code=400, detail="userName and sessionId are required")

    from app.services.postgres_service import toggle_archive_session
    ok = await toggle_archive_session(session_id, user_name, is_archived)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat session not found for this user")
    return {"status": "ok", "sessionId": session_id, "isArchived": is_archived}

@app_endpoints_router.post("/sessions/share")
async def share_session_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    session_id = str(payload.get("sessionId", "")).strip()
    is_public = bool(payload.get("isPublic", False))

    if not user_name or not session_id:
        raise HTTPException(status_code=400, detail="userName and sessionId are required")

    from app.services.postgres_service import toggle_session_public
    ok = await toggle_session_public(session_id, user_name, is_public)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat session not found for this user")
    return {"status": "ok", "sessionId": session_id, "isPublic": is_public}

#  changes done by megnathan: Added share code generation and import endpoints */
@app_endpoints_router.post("/sessions/generate-share-code")
async def generate_share_code_endpoint(payload: dict):
    session_id = str(payload.get("sessionId", "")).strip()
    user_name = str(payload.get("userName", "")).strip()
    if not session_id or not user_name:
        raise HTTPException(status_code=400, detail="sessionId and userName are required")
    from app.services.session_service import generate_share_code
    code = await generate_share_code(session_id, user_name)
    if not code:
        raise HTTPException(status_code=500, detail="Failed to generate share code")
    return {"status": "ok", "shareCode": code}

@app_endpoints_router.post("/sessions/import-by-code")
async def import_by_code_endpoint(payload: dict):
    share_code = str(payload.get("shareCode", "")).strip()
    current_user = str(payload.get("userName", "")).strip()
    if not share_code or not current_user:
        raise HTTPException(status_code=400, detail="shareCode and userName are required")
    from app.services.session_service import import_session_by_code
    new_session_id = await import_session_by_code(share_code, current_user)
    if not new_session_id:
        raise HTTPException(status_code=404, detail="Invalid share code or failed to import")
    return {"status": "ok", "newSessionId": new_session_id}


@app_endpoints_router.post("/folder/create")
async def create_folder_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    folder_name = str(payload.get("folderName", "")).strip()

    if not user_name or not folder_name:
        raise HTTPException(status_code=400, detail="userName and folderName are required")

    from app.services.postgres_service import create_folder
    ok = await create_folder(user_name, folder_name)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to create folder")
    return {"status": "ok", "folderName": folder_name}


@app_endpoints_router.post("/folder/rename")
async def rename_folder_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    old_folder_name = str(payload.get("oldFolderName", "")).strip()
    new_folder_name = str(payload.get("newFolderName", "")).strip()

    if not user_name or not old_folder_name or not new_folder_name:
        raise HTTPException(status_code=400, detail="userName, oldFolderName and newFolderName are required")

    from app.services.postgres_service import rename_folder
    ok = await rename_folder(user_name, old_folder_name, new_folder_name)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to rename folder")
    return {"status": "ok", "oldFolderName": old_folder_name, "newFolderName": new_folder_name}


@app_endpoints_router.post("/folder/delete")
async def delete_folder_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    folder_name = str(payload.get("folderName", "")).strip()

    if not user_name or not folder_name:
        raise HTTPException(status_code=400, detail="userName and folderName are required")

    from app.services.postgres_service import delete_folder
    ok = await delete_folder(user_name, folder_name)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete folder")
    return {"status": "ok", "folderName": folder_name}


@app_endpoints_router.get("/folders/{user_name}")
async def get_folders_endpoint(user_name: str):
    if not user_name:
        raise HTTPException(status_code=400, detail="userName is required")

    from app.services.postgres_service import get_folders
    folders = await get_folders(user_name)
    return {"status": "ok", "folders": folders}


@app_endpoints_router.get("/api/share/history")
async def get_shared_history(sessionId: str, owner: str = None):
    from app.services.postgres_service import get_public_chat_history
    history = await get_public_chat_history(sessionId, owner)
    if history is None:
        raise HTTPException(status_code=404, detail="Shared session not found or private")
    return {"status": "ok", "history": history}
    
@app_endpoints_router.post("/client_insertion")
async def client_insertion(request: ClientInsertionRequest):
    userId     = request.userId.strip()
    userName   = request.userName.strip()
    service    = request.service.strip()
    client_name = request.clientName.strip()
    token      = request.token.strip()

    if not userId or not userName:
        logger.info("invalid client insertion payload")
        raise HTTPException(status_code=400, detail="userId and userName are required")
    
    conn = None
    try:
        conn = get_pool()
        conn.rollback()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT client_name, base_url, user_id, user_name, jwt_token, last_synced_at
            FROM client_sync_config
            WHERE client_name = %s
            LIMIT 1
            """,
            (client_name,),
        )
        row = cursor.fetchone()
        cursor.close()

    except Exception as e:
        logger.error(
            f"❌ Failed to check client_sync_config | client_name = {client_name} | error={e}",
            exc_info=True,
        )
        try:
            if conn is not None and not getattr(conn, "closed", True):
                conn.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Database error while checking client configuration")

    # ── Old client — already exists ──
    if row:
        client_name, base_url, db_user_id, db_user_name, db_jwt_token, last_synced_at = row
        return {
            "client_type": "old",
            "exists": True,
            "client": {
                "client_name": client_name,
                "base_url":    base_url,
                "user_id":     db_user_id,
                "user_name":   db_user_name,
                "token":       db_jwt_token,
            },
        }

    # ── New client — call migrate_user which handles insert + full data sync ──
    try:
        result = await asyncio.to_thread(
            migrate_user,
            client_name = client_name,
            base_url    = service,
            user_id     = int(userId),
            user_name   = userName,
            jwt_token   = token,
        )
        logger.info(f"✅ migrate_user completed | client={client_name} | status={result.get('status')}")

        return {
            "client_type": "new",
            "exists":      False,
            "client": {
                "client_name": client_name,
                "base_url":    service,
                "user_id":     userId,
                "user_name":   userName,
                "service":     service,
                "token":       token,
            },
            "migration": result,
        }

    except Exception as e:
        logger.error(f"❌ migrate_user failed | client={client_name} | error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Client migration failed. Please try again.")


@app_endpoints_router.get("/usage/{external_user_id}/{user_name}", tags=["usage"])
async def get_usage_stats(external_user_id: str, user_name: str):

    if not external_user_id or not user_name:
        raise HTTPException(status_code=400, detail="external_user_id and user_name are required")

    try:
        stats = await asyncio.to_thread(
            get_user_usage_stats,
            external_user_id.strip(),  # ✅ pass both
            user_name.strip()
        )

        if not stats:
            raise HTTPException(
                status_code=404,
                detail=f"No usage data found for user: {user_name}"
            )

        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "❌ get_usage_stats failed | external_user_id=%s user_name=%s | error=%s",
            external_user_id, user_name, e
        )
        raise HTTPException(status_code=500, detail="Failed to fetch usage stats")

@app_endpoints_router.get("/health", tags=["Health"])
def api_health():
    return {"status": "ok", "service": "Facility Management AI Assistant"}

@app_endpoints_router.on_event("startup")
async def startup_event():
    conn = get_pool()
    logger.info("🚀 PostgreSQL client initialized during startup")
    try:
        conn.rollback()
        with conn.cursor() as cur:
            # Check if column is_space_booking exists in chat_sessions
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='chat_sessions' AND column_name='is_space_booking'
            """)
            if not cur.fetchone():
                logger.info("Adding column 'is_space_booking' to 'chat_sessions' table...")
                cur.execute("ALTER TABLE chat_sessions ADD COLUMN is_space_booking BOOLEAN DEFAULT FALSE")
                conn.commit()
                logger.info("Column 'is_space_booking' added successfully.")
            else:
                logger.info("Column 'is_space_booking' already exists in 'chat_sessions'.")
    except Exception as e:
        logger.error(f"Failed to migrate database: {e}", exc_info=True)
        if conn:
            conn.rollback()

@app_endpoints_router.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "Facility Management AI Assistant"}
