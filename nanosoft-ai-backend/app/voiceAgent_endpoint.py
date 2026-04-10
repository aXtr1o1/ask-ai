from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage, AIMessage

from app.models.schemas import ChatRequest
from app.prompts.system_prompt import get_system_prompt
from app.services.langchain_service import langchain_service


voice_agent_router = APIRouter(tags=["voice-agent"])


@voice_agent_router.post("/chat")
async def http_chat_endpoint(request: ChatRequest):
    """HTTP chat endpoint for voice/webhook bridge clients."""
    from app import main as main_app

    user_query = (request.query or "").strip()
    user_id = request.userId
    user_name = (request.userName or "").strip()
    session_id = (request.sessionId or "").strip()

    if not user_query:
        raise HTTPException(status_code=400, detail="query is required")
    if not user_name:
        raise HTTPException(status_code=400, detail="userName is required")
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId is required")

    memory_store = main_app.memory_store
    max_history = main_app.MAX_HISTORY
    logger = main_app.logger

    if session_id not in memory_store:
        memory_store[session_id] = {
            "lc_memory": [],
            "history": [],
            "user_name": user_name,
            "sub_user_name": user_name,
            "pending_transcription": None,
        }

    lc_memory = list(memory_store[session_id]["lc_memory"])
    messages = [get_system_prompt(user_name)] + lc_memory
    messages.append(HumanMessage(content=user_query))

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

    if len(memory_store[session_id]["history"]) > max_history:
        memory_store[session_id]["history"] = memory_store[session_id]["history"][-max_history:]
        memory_store[session_id]["lc_memory"] = memory_store[session_id]["lc_memory"][-(max_history * 2):]

    return {
        "session_id": session_id,
        "response": final_response_text,
        "done": True,
    }