#voice agent endpoint added by sudharshan
import logging
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage, AIMessage

from app.models.schemas import ChatRequest
from app.services.langchain_service import langchain_service
from app.services.scoped_memory_service import build_scoped_messages
from app.state import memory_store, MAX_HISTORY, trim_session

logger = logging.getLogger("chatbot_app")
voice_agent_router = APIRouter(tags=["voice-agent"])


@voice_agent_router.post("/chat")
async def http_chat_endpoint(request: ChatRequest):
    """HTTP chat endpoint for voice/webhook bridge clients."""

    user_query = (request.query or "").strip()
    user_id = getattr(request, 'userId', None) or getattr(request, 'user_id', None)
    user_name = (getattr(request, 'userName', None) or getattr(request, 'user_name', None) or "").strip()
    session_id = (getattr(request, 'sessionId', None) or getattr(request, 'session_id', None) or "").strip()

    if not user_query:
        raise HTTPException(status_code=400, detail="query is required")
    if not user_name:
        raise HTTPException(status_code=400, detail="userName is required")
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId is required")

    if session_id not in memory_store:
        memory_store[session_id] = {
            "lc_memory": [],
            "history": [],
            "user_name": user_name,
            "sub_user_name": user_name,
            "pending_transcription": None,
        }

    messages = build_scoped_messages(
        user_name=user_name,
        current_query=user_query,
        session_data=memory_store[session_id],
        max_previous_turns=MAX_HISTORY,
    )

    try:
        final_response_text, context_summary, _ = await langchain_service.process_query(
            messages,
            user_name=user_name,
            user_id=user_id,
            session_id=session_id,
            is_graph=False,
        )
    except Exception as e:
        logger.error("❌ HTTP /chat error: %s", e, exc_info=True)
        final_response_text = "Sorry, something went wrong. Please try again."
        context_summary = final_response_text

    memory_store[session_id]["lc_memory"].append(HumanMessage(content=user_query))
    memory_store[session_id]["lc_memory"].append(AIMessage(content=context_summary))
    memory_store[session_id]["history"].append(
        {
            "query": user_query,
            "assistant": final_response_text,
            "context": context_summary,
            "is_audio": False,
        }
    )

    trim_session(memory_store[session_id], MAX_HISTORY)

    return {
        "session_id": session_id,
        "response": final_response_text,
        "done": True,
    }
