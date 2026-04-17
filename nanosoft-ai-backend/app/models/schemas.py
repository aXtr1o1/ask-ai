"""
models/schemas.py
──────────────────
Pydantic request/response models for the chatbot API.

Used by:
    main.py → FastAPI endpoints for validation + serialization

Models:
    ChatRequest            → HTTP POST /chat (not used by WebSocket but kept for compatibility)
    FrontendChatMessage    → shape of a single message when saving history
    SessionRequest         → POST /api/session (fetch sessions / save history)
    ClientInsertionRequest → POST /api/client_insertion (check if client exists)
"""

from pydantic import BaseModel
from typing import Optional, List


class ChatRequest(BaseModel):
    """
    Request schema for HTTP chat endpoint.

    Accepts both camelCase and snake_case variants for compatibility
    with different frontend implementations.
    """
    query:     Optional[str] = None
    userName:  Optional[str] = None    # camelCase from frontend
    user_name: Optional[str] = None    # snake_case alternative
    userId:    Optional[str] = None    # camelCase from frontend
    user_id:   Optional[str] = None    # snake_case alternative
    sessionId: Optional[str] = None    # camelCase from frontend
    session_id:Optional[str] = None    # snake_case alternative


class FrontendChatMessage(BaseModel):
    """
    Shape of a single chat message sent from frontend when saving session history.

    Used inside SessionRequest.chatHistory list.
    role: "user" or "ai"
    text: the message content (may be base64 audio string for audio messages)
    isAudio: True if this message is an audio recording
    """
    role:    str
    text:    str
    isAudio: bool = False


class SessionRequest(BaseModel):
    """
    Multi-purpose request schema for POST /api/session.

    Three use cases (determined by which fields are present):

    Case 1 — Save session history (chatHistory present):
        Frontend sends full chat history after session ends.
        userName + sessionId + chatHistory required.

    Case 2 — Fetch all sessions (no sessionId):
        Frontend requests session list for sidebar.
        Only userName required.

    Case 3 — Fetch chat history (sessionId present, no chatHistory):
        Frontend clicked on an old session to view it.
        userName + sessionId required.
    """
    userName:       str
    sessionId:      str = ""
    chatHistory:    Optional[List[FrontendChatMessage]] = None
    historyOnClick: bool = False


class ClientInsertionRequest(BaseModel):
    """
    Request schema for POST /api/client_insertion.

    Used to check if a client already exists in client_registry.
    New clients should be onboarded via POST /api/client/onboard/service instead.
    """
    userId:     str   # client's user ID
    clientName: str   # client's unique name (maps to client_name in DB)
    service:    str   # base_url of the client's API
    token:      str   # JWT token for the client's API