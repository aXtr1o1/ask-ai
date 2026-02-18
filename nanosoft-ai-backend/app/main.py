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
from app.prompts.system_prompt import system_prompt

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
#   "101": {
#     "lc_memory": [HumanMessage, AIMessage, ...],
#     "history": [...],
#     "session_id": "abc-123"
#   }
# }
# =====================================================
MAX_HISTORY = 10
memory_store = {}


def print_memory(user_id: str):
    """Print current in-memory history for the user"""
    print("\n" + "=" * 50)
    print(f"🧠 IN-MEMORY STORE — user_id: {user_id}")
    print("=" * 50)
    user_data = memory_store.get(user_id, {})
    history = user_data.get("history", [])
    session_id = user_data.get("session_id", "N/A")
    print(f"  Session ID : {session_id}")
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
    user_id = request.userId
    session_id = request.sessionId
    
    print(f"{user_id}---------{user_query}-------{session_id}")

    # 1️⃣ Validate user ID
    if user_id not in VALID_USER_IDS:
        logger.warning(f"🚫 Invalid user_id attempted: '{user_id}'")
        raise HTTPException(
            status_code=403,
            detail=f"Invalid user ID '{user_id}'. Access denied."
        )

    logger.info(f"✅ Valid user: {user_id} | Session: {session_id}")

    # 2️⃣ Initialize user in memory if first time
    if user_id not in memory_store:
        memory_store[user_id] = {
            "lc_memory": [],
            "history": [],
            "session_id": session_id
        }
        logger.info(f"🆕 Memory initialized for user_id: {user_id}")
    else:
        # Update session_id if a new session started
        memory_store[user_id]["session_id"] = session_id

    lc_memory = memory_store[user_id]["lc_memory"]
    history = memory_store[user_id]["history"]

    # 3️⃣ Build message context: system prompt + history as LangChain messages
    messages = [system_prompt] + lc_memory
    messages.append(HumanMessage(content=user_query))

    # 4️⃣ Process with LangChain — pass real user_id so tools use it
    try:
        final_response_text, _ = await langchain_service.process_query(messages, user_id=user_id)
        logger.info(f"✅ Response generated for user_id: {user_id}")
    except Exception as e:
        logger.error(f"❌ LangChain error: {e}", exc_info=True)
        final_response_text = "Sorry, something went wrong while processing your request."

    # 5️⃣ Update in-memory (keep last MAX_HISTORY interactions)
    lc_memory.append(HumanMessage(content=user_query))
    lc_memory.append(AIMessage(content=final_response_text))
    history.append({"query": user_query, "assistant": final_response_text})

    if len(history) > MAX_HISTORY:
        memory_store[user_id]["history"] = history[-MAX_HISTORY:]
        memory_store[user_id]["lc_memory"] = lc_memory[-(MAX_HISTORY * 2):]

    # 6️⃣ Print in-memory after every request
    print_memory(user_id)

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