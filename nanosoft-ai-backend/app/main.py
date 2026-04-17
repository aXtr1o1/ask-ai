"""
main.py
────────
Facility Management AI Chatbot — FastAPI Application Entry Point.

Responsibilities (slim — only what belongs here):
    - App creation + CORS middleware
    - Router includes
    - Startup: validate config + initialize DB pool
    - Shutdown: graceful pool close
    - Top-level /health check

All endpoint logic lives in:
    app/api/routes/__init__.py       → master router (WebSocket + REST)
    app/handlers/ws_chat_handler.py  → full WebSocket chat logic
    app/endpoints/session_endpoint.py
    app/endpoints/client_endpoint.py
    app/endpoints/usage_endpoint.py

All helper logic lives in:
    app/utils/query_utils.py   → _has_date_keyword, _build_table_context
    app/utils/debug_utils.py   → print_memory
    app/utils/ws_utils.py      → _init_session, _save_session_safe, _send
    app/constants.py           → YES_WORDS, NO_WORDS, MAX_AUDIO_BYTES
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.database.postgres_client import init_pool, close_pool
from app.api.routes import api_router
from app.dynamic.onboarding.routes import router as dynamic_router

# ── Logger ────────────────────────────────────────────────────────────────────
logger = logging.getLogger("chatbot_app")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(ch)


# ══════════════════════════════════════════════════════════════════════════════
# APP CREATION
# ══════════════════════════════════════════════════════════════════════════════

chatbot_app = FastAPI(
    title       = "Facility Management AI Assistant",
    description = "AI-powered chatbot for Assets, PPM, BDM and dynamic client services",
    version     = "4.0.0",
)

chatbot_app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
chatbot_app.include_router(api_router)
chatbot_app.include_router(dynamic_router)


# ══════════════════════════════════════════════════════════════════════════════
# STARTUP / SHUTDOWN
# ══════════════════════════════════════════════════════════════════════════════

@chatbot_app.on_event("startup")
async def startup_event():
    try:
        init_pool()
        logger.info("🚀 [MAIN] PostgreSQL pool initialised during startup")
    except Exception as e:
        logger.critical("❌ [MAIN] Startup failed — DB pool init error | error=%s", e)
        raise


@chatbot_app.on_event("shutdown")
async def shutdown_event():
    """Gracefully close DB pool on app shutdown."""
    close_pool()
    logger.info("🛑 [MAIN] App shutdown — DB pool closed")


# ══════════════════════════════════════════════════════════════════════════════
# TOP-LEVEL HEALTH
# ══════════════════════════════════════════════════════════════════════════════

@chatbot_app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "Facility Management AI Assistant"}