"""
AI Chatbot FastAPI Application
Main entry point for the Facility Management AI Assistant
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage

from app.models.schemas import ChatRequest
from app.config import settings
from app.services.redis_service import redis_service
from app.services.langchain_service import langchain_service
from app.prompts.system_prompt import system_prompt

# =====================================================
# ✅ FastAPI App Initialization
# =====================================================
chatbot_app = FastAPI(
    title="Facility Management AI Assistant",
    description="AI-powered chatbot for facility management queries",
    version="2.0.0"
)

# =====================================================
# ✅ CORS Configuration
# =====================================================
chatbot_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# ✅ In-Memory Session Storage
# =====================================================
sessions = {}

# =====================================================
# ✅ Main Chat Endpoint
# =====================================================
@chatbot_app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    user_query = request.query
    print(user_query)
    
    # 1️⃣ Session Initialization
    session_id = request.session_id or redis_service.create_session_id()
    if session_id not in sessions:
        lc_memory, redis_memory = redis_service.fetch_session_history(
            settings.DEFAULT_USER,
            session_id
        )
        sessions[session_id] = {
            "lc_memory": lc_memory,
            "redis_memory": redis_memory
        }

    lc_memory = sessions[session_id]["lc_memory"]
    redis_memory = sessions[session_id]["redis_memory"]

    # 2️⃣ Build Message Context
    messages = [system_prompt] + lc_memory
    messages.append(HumanMessage(content=user_query))

    # 3️⃣ Process with LangChain
    final_response_text, _ = await langchain_service.process_query(messages)

    # 4️⃣ Update In-Memory Session
    lc_memory.append(HumanMessage(content=user_query))
    lc_memory.append(AIMessage(content=final_response_text))
    redis_memory = redis_service.add_to_memory(redis_memory, user_query, final_response_text)

    # 5️⃣ Save Session if Ended
    if request.end_session:
        redis_service.save_session(settings.DEFAULT_USER, session_id, redis_memory)
        sessions.pop(session_id, None)
        print(f"Session ended: {session_id}")

    # 6️⃣ Return Response
    return {
        "session_id": session_id,
        "response": final_response_text
    }


# =====================================================
# ✅ Run Application on port 8001
# =====================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:chatbot_app",
        host="127.0.0.1",
        port=8001,
        reload=True
    )
