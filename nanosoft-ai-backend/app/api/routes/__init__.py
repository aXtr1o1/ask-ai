"""
app/api/routes/__init__.py
───────────────────────────
Master API router — combines all sub-routers under /api prefix.

Includes:
    WebSocket /api/chat         → ws_chat_handler
    POST      /api/session      → session_endpoint
    POST      /api/client_*     → client_endpoint
    GET       /api/usage        → usage_endpoint
    GET       /api/health       → usage_endpoint
"""

from fastapi import APIRouter
from app.handlers.ws_chat_handler import ws_chat_endpoint
from app.endpoints.session_endpoint import router as session_router
from app.endpoints.client_endpoint import router as client_router
from app.endpoints.usage_endpoint import router as usage_router

api_router = APIRouter(prefix="/api", tags=["api"])

# ── WebSocket endpoint ─────────────────────────────────────────────────────────
api_router.add_api_websocket_route("/chat", ws_chat_endpoint)

# ── REST endpoints ─────────────────────────────────────────────────────────────
api_router.include_router(session_router)
api_router.include_router(client_router)
api_router.include_router(usage_router)