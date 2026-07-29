"""
Facility Management AI Chatbot — Main App
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.routes.app_endpoints import app_endpoints_router
from app.services.chat_websocket_handler import chat_websocket_router
from app.voiceAgent_endpoint import voice_agent_router
from app.api.routes.advance import advance_router

logger = logging.getLogger("chatbot_app")


# =============================================================================
# LOGGING SETUP
#
# Why a startup event instead of module-level code:
#   Uvicorn calls logging.config.dictConfig() after importing the app.
#   Any handlers we attach at module-load time get wiped by uvicorn's config.
#   A startup event runs AFTER uvicorn finishes its own logging setup,
#   so our handlers survive.
#
# Why "advance" (parent) instead of individual child names:
#   Python logging is hierarchical. Registering the "advance" logger
#   automatically captures advance.analysis, advance.execution.agent,
#   advance.retrieval.bdm and every other advance.* child — no need to
#   list them individually.
# =============================================================================
_fmt = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)


def _configure_advance_logging() -> None:
    """Attach a StreamHandler to the 'advance' parent logger (and chatbot_app)."""

    def _ensure_handler(log: logging.Logger) -> None:
        if not any(isinstance(h, logging.StreamHandler) for h in log.handlers):
            h = logging.StreamHandler()
            h.setFormatter(_fmt)
            log.addHandler(h)

    # App logger
    logger.setLevel(logging.INFO)
    _ensure_handler(logger)

    # All advance.* loggers via single parent
    advance_log = logging.getLogger("advance")
    advance_log.setLevel(logging.INFO)
    _ensure_handler(advance_log)
    advance_log.propagate = False  # stop double-printing via root logger


chatbot_app = FastAPI(
    title="Facility Management AI Assistant",
    description="AI-powered chatbot for Assets, PPM, and BDM queries",
    version="3.0.0"
)

chatbot_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the routers
chatbot_app.include_router(chat_websocket_router, prefix="/api", tags=["websocket"])
chatbot_app.include_router(app_endpoints_router, prefix="/api", tags=["api"])
chatbot_app.include_router(voice_agent_router, prefix="/api", tags=["voice_agent"])
chatbot_app.include_router(advance_router, prefix="/api", tags=["advance_ai"])


@chatbot_app.on_event("startup")
async def on_startup() -> None:
    """
    Run AFTER uvicorn finishes its own logging.config.dictConfig() call.
    This ensures our StreamHandlers are not wiped by uvicorn's setup.
    """
    _configure_advance_logging()
    logger.info("=" * 60)
    logger.info("  Advance AI pipeline logging is ACTIVE")
    logger.info("  All advance.* logs will appear below")
    logger.info("=" * 60)
