"""
Facility Management AI Chatbot — Main App
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage
import logging

from app.models.schemas import ChatRequest
from app.config import settings
from app.services.langchain_service import langchain_service
from app.prompts.system_prompt import get_system_prompt

logger = logging.getLogger("chatbot_app")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)

# =====================================================
# App Init
# =====================================================
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

# =====================================================
# Valid Users
# =====================================================
VALID_USER_IDS = {"101", "102"}

# =====================================================
# In-Memory Store
#
# Structure:
# {
#   "session-abc-123": {
#     "lc_memory": [HumanMessage, AIMessage, ...],
#     "history": [...],
#     "user_id": "101"
#   }
# }
# =====================================================
MAX_HISTORY = 5
memory_store = {}


def print_memory(session_id: str):
    """Print current in-memory history for the session"""
    print("\n" + "=" * 50)
    print(f"🧠 IN-MEMORY STORE — session_id: {session_id}")
    print("=" * 50)
    session_data = memory_store.get(session_id, {})
    history = session_data.get("history", [])
    user_id = session_data.get("user_id", "N/A")
    print(f"  User ID : {user_id}")
    if not history:
        print("  (empty)")
    else:
        for i, item in enumerate(history, 1):
            print(f"  [{i}] Query    : {item['query']}")
            print(f"      Assistant : {item['assistant'][:100]}{'...' if len(item['assistant']) > 100 else ''}")
            print()
    print("=" * 50 + "\n")


# =====================================================
# Chat Endpoint
# =====================================================
@chatbot_app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    user_query = request.query
    user_id = request.userId  # constant from frontend; used for all processing and tool calls
    session_id = request.sessionId
    logger.info(f"Request | user_id={user_id} | session_id={session_id} | query={user_query}")

    # 1️⃣ Validate user ID
    if user_id not in VALID_USER_IDS:
        logger.warning(f"🚫 Invalid user_id attempted: '{user_id}'")
        raise HTTPException(
            status_code=403,
            detail=f"Invalid user ID '{user_id}'. Access denied."
        )

    logger.info(f"✅ Valid user: {user_id} | Session: {session_id}")

    # 2️⃣ Initialize session in memory if first time
    if session_id not in memory_store:
        memory_store[session_id] = {
            "lc_memory": [],
            "history": [],
            "user_id": user_id
        }
        logger.info(f"🆕 Memory initialized for session_id: {session_id}")

    # ✅ FIX — copy lc_memory, not a reference.
    # Prevents parallel requests from mutating the same list
    # and corrupting each other's message context.
    lc_memory = list(memory_store[session_id]["lc_memory"])

    # 3️⃣ Build message context: system prompt includes authenticated user_id so model never asks for it
    messages = [get_system_prompt(user_id)] + lc_memory
    messages.append(HumanMessage(content=user_query))

    # 4️⃣ Process with LangChain — same user_id used for all tool calls
    try:
        final_response_text, _ = await langchain_service.process_query(messages, user_id=user_id)
        logger.info(f"✅ Response generated for session_id: {session_id}")
    except Exception as e:
        logger.error(f"❌ LangChain error: {e}", exc_info=True)
        final_response_text = "Sorry, something went wrong while processing your request."

    # 5️⃣ Update in-memory directly on store (not on the copy).
    # Keep last MAX_HISTORY interactions per session.
    memory_store[session_id]["lc_memory"].append(HumanMessage(content=user_query))
    memory_store[session_id]["lc_memory"].append(AIMessage(content=final_response_text))
    memory_store[session_id]["history"].append({"query": user_query, "assistant": final_response_text})

    if len(memory_store[session_id]["history"]) > MAX_HISTORY:
        memory_store[session_id]["history"] = memory_store[session_id]["history"][-MAX_HISTORY:]
        memory_store[session_id]["lc_memory"] = memory_store[session_id]["lc_memory"][-(MAX_HISTORY * 2):]

    # 6️⃣ Print in-memory after every request
    print_memory(session_id)

    # 7️⃣ Return response
    return {
        "user_id": user_id,
        "session_id": session_id,
        "response": final_response_text
    }


# =====================================================
# ✅ Run Application on port 8001
# =====================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:chatbot_app", host="0.0.0.0", port=8001, reload=True)