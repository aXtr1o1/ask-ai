"""
app/utils/ws_utils.py
──────────────────────
WebSocket utility helpers used by the chat handler.

Functions:
    _init_session()       → initialise memory_store entry for a new session
    _save_session_safe()  → save session to DB, swallowing all errors
    _send()               → send response + [DONE] marker to frontend
"""

import json
import logging
from fastapi import WebSocket
from app.state import memory_store
from app.services.data.postgres_service import save_session_to_postgres_service

logger = logging.getLogger("utils.ws_utils")


def _init_session(session_id: str, user_name: str, sub_user_name: str) -> None:
    """Initialise memory_store entry for a new session if not already present."""
    if session_id not in memory_store:
        memory_store[session_id] = {
            "lc_memory":               [],
            "history":                 [],
            "user_name":               user_name,
            "sub_user_name":           sub_user_name,
            "pending_transcription":   None,
            "pending_table":           None,
            "pending_table_context":   None,
            "pending_original_query":  None,
            "waiting_for_table_choice": False,
        }
        logger.info(
            "🆕 [WS] Session initialised | session_id=%s | user=%s",
            session_id, user_name,
        )


async def _save_session_safe(session_id: str) -> None:
    """Save session to DB — swallows all errors so disconnect never crashes."""
    try:
        session_data = memory_store.get(session_id, {})
        await save_session_to_postgres_service(
            session_id = session_id,
            user_name  = session_data.get("sub_user_name") or session_data.get("user_name", ""),
            history    = session_data.get("history", []),
        )
        logger.info("✅ [WS] Session saved | session_id=%s", session_id)
    except Exception as e:
        logger.error(
            "❌ [WS] Session save failed | session_id=%s | error=%s",
            session_id, e,
        )


async def _send(ws: WebSocket, session_id: str, response: str) -> None:
    """Send response + [DONE] marker to frontend."""
    await ws.send_text(json.dumps({"session_id": session_id, "response": response}))
    await ws.send_text("[DONE]")