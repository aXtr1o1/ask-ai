"""
Facility Management AI Chatbot — Main App
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage
import logging
import json

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
# In-Memory Store
#
# Structure:
# {
#   "101": {
#     "lc_memory": [HumanMessage, AIMessage, ...],
#     "history": [
#       {"query": "...", "assistant": "..."},
#       ...
#     ]
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
    user_id = "101"  # Fixed for now — will come from frontend later

    # 1️⃣ Initialize user in memory if first time
    if user_id not in memory_store:
        memory_store[user_id] = {
            "lc_memory": [],
            "history": []
        }
        logger.info(f"🆕 Memory initialized for user_id: {user_id}")

    lc_memory = memory_store[user_id]["lc_memory"]
    history = memory_store[user_id]["history"]

    # 2️⃣ Build message context: system prompt + history as LangChain messages
    messages = [system_prompt] + lc_memory
    messages.append(HumanMessage(content=user_query))

    # 3️⃣ Process with LangChain
    try:
        final_response_text, _ = await langchain_service.process_query(messages)
        logger.info(f"✅ Response generated for user_id: {user_id}")
    except Exception as e:
        logger.error(f"❌ LangChain error: {e}", exc_info=True)
        final_response_text = "Sorry, something went wrong while processing your request."

    # 4️⃣ Update in-memory (keep last MAX_HISTORY interactions)
    lc_memory.append(HumanMessage(content=user_query))
    lc_memory.append(AIMessage(content=final_response_text))
    history.append({"query": user_query, "assistant": final_response_text})

    if len(history) > MAX_HISTORY:
        memory_store[user_id]["history"] = history[-MAX_HISTORY:]
        memory_store[user_id]["lc_memory"] = lc_memory[-(MAX_HISTORY * 2):]

    # 5️⃣ Print in-memory after every request
    print_memory(user_id)

    # 6️⃣ Return response
    return {
        "user_id": user_id,
        "response": final_response_text
    }


# =====================================================
# ✅ Run Application on port 8001
# =====================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:chatbot_app", host="0.0.0.0", port=8001, reload=True)
