from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from tools import ASSETS, COMPLAINTS, WORK_ORDERS
from system_prompt import system_prompt

import os
from dotenv import load_dotenv

import asyncio

from redis_connection import redis_client
import uuid
from datetime import datetime

import json



load_dotenv()
api_key = os.getenv("api_key")

# =====================================================
# ✅ FastAPI App
# =====================================================
app = FastAPI()

# =====================================================
# ✅ Allow Frontend Requests (CORS Fix)
# =====================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# ✅ Bind Tools to Gemini Model
# =====================================================
model_with_tools = ChatGoogleGenerativeAI(
    model="gemini-flash-latest",
    google_api_key=api_key
).bind_tools([ASSETS, COMPLAINTS, WORK_ORDERS])

# =====================================================
# ✅ Tool Map
# =====================================================
tool_map = {
    "ASSETS": ASSETS,
    "COMPLAINTS": COMPLAINTS,
    "WORK_ORDERS": WORK_ORDERS,
}

# =====================================================
# ✅ Chat Memory Store (Simple Global)
# =====================================================
chat_history = []


# =====================================================
# ✅ Request Schema
# =====================================================
class ChatRequest(BaseModel):
    query: str


# =====================================================
# ✅ Safe Chunk Extractor (Fixes Empty List Error)
# =====================================================
def extract_chunk_text(chunk):
    content = chunk.content

    # Case 1: Empty chunk
    if not content:
        return ""

    # Case 2: Gemini list format
    if isinstance(content, list):

        # Sometimes list is empty
        if len(content) == 0:
            return ""

        return content[0].get("text", "")

    # Case 3: Normal string
    if isinstance(content, str):
        return content

    return str(content)


#connection_checking 
if redis_client:
    print("connection sucessfull")

# =====================================================
# 🔧 CONFIG
# =====================================================
USER_NAME = "ram"
TTL_SECONDS = 86400
MAX_HISTORY = 10

# =====================================================
# 🆔 SESSION MEMORY (IN-RUNTIME)
# =====================================================
sessions = {}  
# sessions[session_id] = {
#   "lc_memory": [],
#   "redis_memory": []
# }

# =====================================================
# 📩 REQUEST SCHEMA
# =====================================================
class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None
    end_session: bool = False   # frontend sends true when chat ends

# =====================================================
# 🆔 CREATE SESSION
# =====================================================
def create_new_session():
    return str(uuid.uuid4())

# =====================================================
# 🔍 FETCH SESSION FROM REDIS (ONCE)
# =====================================================
def fetch_session_outputs(user, session_id, limit=MAX_HISTORY):
    key = f"user:{user}:session:{session_id}"
    data = redis_client.get(key)

    lc_memory = []
    redis_memory = []

    if data:
        records = json.loads(data)
        for item in records[-limit:]:
            lc_memory.append(HumanMessage(content=item["query"]))
            lc_memory.append(AIMessage(content=item["result"]))
            redis_memory.append(item)

    return lc_memory, redis_memory

# =====================================================
# 💾 SAVE SESSION TO REDIS (ONCE)
# =====================================================
def save_session_to_redis(user, session_id, redis_memory):
    key = f"user:{user}:session:{session_id}"
    redis_client.set(key, json.dumps(redis_memory))
    redis_client.expire(key, TTL_SECONDS)
    print(f"💾 Session saved: {key}")


# =====================================================
# 🚀 CHAT ENDPOINT
# =====================================================
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):

    user_query = request.query

    # -------------------------------------------------
    # 1️⃣ SESSION INIT
    # -------------------------------------------------
    session_id = request.session_id or create_new_session()

    if session_id not in sessions:
        lc_memory, redis_memory = fetch_session_outputs(
            USER_NAME, session_id, MAX_HISTORY
        )
        sessions[session_id] = {
            "lc_memory": lc_memory,
            "redis_memory": redis_memory
        }

    lc_memory = sessions[session_id]["lc_memory"]
    redis_memory = sessions[session_id]["redis_memory"]

    # -------------------------------------------------
    # 2️⃣ BUILD MESSAGES
    # -------------------------------------------------
    messages = [system_prompt]
    messages.extend(lc_memory)
    messages.append(HumanMessage(content=user_query))

    # -------------------------------------------------
    # 3️⃣ TOOL DETECTION
    # -------------------------------------------------
    ai_msg = model_with_tools.invoke(messages)

    if ai_msg.tool_calls:
        messages.append(ai_msg)

        for tool_call in ai_msg.tool_calls:
            tool_fn = tool_map[tool_call["name"]]
            tool_result = tool_fn.invoke(tool_call["args"])

            messages.append(
                ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call["id"]
                )
            )

    # -------------------------------------------------
    # 4️⃣ STREAM RESPONSE
    # -------------------------------------------------
    final_response_text = ""

    async for chunk in model_with_tools.astream(messages):
        text = extract_chunk_text(chunk)
        if text:
            final_response_text += text

    # -------------------------------------------------
    # 5️⃣ UPDATE MEMORY (IN RAM)
    # -------------------------------------------------
    lc_memory.append(HumanMessage(content=user_query))
    lc_memory.append(AIMessage(content=final_response_text))

    redis_memory.append({
        "query": user_query,
        "result": final_response_text,
        "timestamp": datetime.utcnow().isoformat()
    })

    # -------------------------------------------------
    # 6️⃣ END SESSION → SAVE TO REDIS
    # -------------------------------------------------
    if request.end_session:
        save_session_to_redis(USER_NAME, session_id, redis_memory)
        sessions.pop(session_id, None)

    return {
        "session_id": session_id,
        "response": final_response_text
    }

# =====================================================
# ▶ RUN
# =====================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("model:app", host="127.0.0.1", port=8001, reload=True)
