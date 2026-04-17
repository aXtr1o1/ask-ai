"""
app/endpoints/session_endpoint.py
───────────────────────────────────
Session REST endpoints:
    POST /api/session         → save / fetch sessions / fetch history
    POST /api/session/rename  → rename a session
    POST /api/session/delete  → delete a session
"""

import logging
from fastapi import APIRouter, HTTPException

from app.models.schemas import SessionRequest
from app.state import frontend_saved_sessions
from app.services.data.session_service import (
    get_sessions_for_user,
    get_chat_history_for_session,
)
from app.services.data.postgres_service import (
    save_session_to_postgres_service,
    update_session_title,
    delete_session_from_postgres,
)

logger = logging.getLogger("endpoints.session")

router = APIRouter(tags=["session"])


@router.post("/session")
async def sessions_endpoint(request: SessionRequest):
    user_name        = request.userName.strip()
    session_id       = request.sessionId.strip()
    incoming_history = request.chatHistory or []

    if not user_name:
        raise HTTPException(status_code=400, detail="userName is required")

    # ── Case 1: Save session ───────────────────────────────────────────────────
    if incoming_history:
        history_pairs  = []
        pending_query  = None
        pending_audio  = False

        for msg in incoming_history:
            role = (msg.role or "").lower()
            if role == "user":
                pending_query = msg.text or ""
                pending_audio = getattr(msg, "isAudio", False)
            elif role == "ai" and pending_query is not None:
                history_pairs.append({
                    "query":     pending_query,
                    "assistant": msg.text or "",
                    "is_audio":  pending_audio,
                    "context":   msg.text or "",
                })
                pending_query = None
                pending_audio = False

        if pending_query:
            history_pairs.append({"query": pending_query, "assistant": ""})

        await save_session_to_postgres_service(
            session_id = session_id,
            user_name  = user_name,
            history    = history_pairs,
        )
        frontend_saved_sessions.add(session_id)
        return {
            "user_name":  user_name,
            "session_id": session_id,
            "type":       "saved",
            "messages":   len(history_pairs),
        }

    # ── Case 2: Fetch all sessions ─────────────────────────────────────────────
    if not session_id:
        sessions = await get_sessions_for_user(user_name)
        return {"user_name": user_name, "type": "sessions", "sessions": sessions}

    # ── Case 3: Fetch chat history for one session ─────────────────────────────
    history = await get_chat_history_for_session(user_name, session_id)
    return {
        "user_name":    user_name,
        "session_id":   session_id,
        "type":         "history",
        "chat_history": history,
    }


@router.post("/session/rename")
async def rename_session_endpoint(payload: dict):
    user_name  = str(payload.get("userName",  "")).strip()
    session_id = str(payload.get("sessionId", "")).strip()
    title      = str(payload.get("title",     "")).strip()

    if not user_name or not session_id or not title:
        raise HTTPException(status_code=400, detail="userName, sessionId and title are required")

    ok = await update_session_title(session_id, user_name, title)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update session title")
    return {"status": "ok", "sessionId": session_id, "title": title}


@router.post("/session/delete")
async def delete_session_endpoint(payload: dict):
    user_name  = str(payload.get("userName",  "")).strip()
    session_id = str(payload.get("sessionId", "")).strip()

    if not user_name or not session_id:
        raise HTTPException(status_code=400, detail="userName and sessionId are required")

    ok = await delete_session_from_postgres(session_id, user_name)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete session")
    return {"status": "ok", "sessionId": session_id}