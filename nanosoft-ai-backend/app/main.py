"""
Facility Management AI Chatbot — Main App
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.routes.app_endpoints import app_endpoints_router
from app.services.chat_websocket_handler import chat_websocket_router
from app.voiceAgent_endpoint import voice_agent_router

logger = logging.getLogger("chatbot_app")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)

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
