"""
Facility Management AI Chatbot — Main App
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage
import logging
import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect

from app.models.schemas import ChatRequest
from app.config import settings
from app.services.langchain_service import langchain_service
from app.prompts.system_prompt import get_system_prompt
from app.services.postgres_service import save_session_to_supabase 

from app.api.database.supabase_client import get_supabase_client
from app.api.database.postgres_client import get_pool

from app.services.session_service import get_sessions_for_user, get_chat_history_for_session
from app.models.schemas import SessionRequest




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
MAX_HISTORY =  settings.MAX_HISTORY
memory_store = {}


def print_memory(session_id: str):
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


# @chatbot_app.post("/chat")
# async def chat_endpoint(request: ChatRequest):
#     user_query = request.query
#     user_id = request.userId
#     session_id = request.sessionId
#     logger.info(f"Request | user_id={user_id} | session_id={session_id} | query={user_query}")

#     if user_id not in VALID_USER_IDS:
#         logger.warning(f"🚫 Invalid user_id attempted: '{user_id}'")
#         raise HTTPException(status_code=403, detail=f"Invalid user ID '{user_id}'. Access denied.")

#     logger.info(f"✅ Valid user: {user_id} | Session: {session_id}")

#     if session_id not in memory_store:
#         memory_store[session_id] = {"lc_memory": [], "history": [], "user_id": user_id}
#         logger.info(f"🆕 Memory initialized for session_id: {session_id}")

    # lc_memory = list(memory_store[session_id]["lc_memory"])
    # messages = [get_system_prompt(user_id)] + lc_memory
    # messages.append(HumanMessage(content=user_query))

    # try:
    #     final_response_text, _ = await langchain_service.process_query(messages, user_id=user_id,session_id=session_id)
    #     logger.info(f"✅ Response generated for session_id: {session_id}")
    # except Exception as e:
    #     logger.error(f"❌ LangChain error: {e}", exc_info=True)
    #     final_response_text = "Sorry, something went wrong while processing your request."

    # memory_store[session_id]["lc_memory"].append(HumanMessage(content=user_query))
    # memory_store[session_id]["lc_memory"].append(AIMessage(content=final_response_text))
    # memory_store[session_id]["history"].append({"query": user_query, "assistant": final_response_text})

    # if len(memory_store[session_id]["history"]) > MAX_HISTORY:
    #     memory_store[session_id]["history"] = memory_store[session_id]["history"][-MAX_HISTORY:]
    #     memory_store[session_id]["lc_memory"] = memory_store[session_id]["lc_memory"][-(MAX_HISTORY * 2):]

    # print_memory(session_id)

    # return {"user_id": user_id, "session_id": session_id, "response": final_response_text}


# =====================================================
# WebSocket Chat Endpoint  /ws/chat
@chatbot_app.websocket("/ws/chat")
async def ws_chat_endpoint(websocket: WebSocket):

    await websocket.accept()
    logger.info("🔌 WebSocket connection accepted")

    current_session_id = None  # track session so we can save on disconnect

    try:
        while True:
            try:
                # Wait for next message; timeout = WS_SESSION_TIMEOUT (default 30 min)
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=settings.WS_SESSION_TIMEOUT
                )
            except asyncio.TimeoutError:
                logger.info(f"⏰ WebSocket auto-closed after {settings.WS_SESSION_TIMEOUT}s inactivity")
                await websocket.close()
                # ✅ Save to Supabase on timeout disconnect
                if current_session_id:
                    session_data = memory_store.get(current_session_id, {})
                    await save_session_to_supabase(
                        session_id = current_session_id,
                        user_id    = session_data.get("user_id", ""),
                        history    = session_data.get("history", [])
                    )
                break

            # ── Ping / pong keep-alive ──────────────────────────────────
            if raw.strip() == "ping":
                await websocket.send_text("pong")
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "Invalid JSON"}))
                continue

            user_query = data.get("query", "").strip()
            user_id    = str(data.get("userId", ""))
            session_id = str(data.get("sessionId", ""))

            logger.info(f"WS Request | user_id={user_id} | session_id={session_id} | query={user_query}")

            if user_id not in VALID_USER_IDS:
                logger.info("invalid user id")
                await websocket.send_text(json.dumps({"error": "Invalid user ID"}))
                continue

            if not user_query:
                logger.info("invalid user query")
                await websocket.send_text(json.dumps({"error": "Empty query"}))
                continue

            if not session_id:
                logger.info("invalid session id")
                await websocket.send_text(json.dumps({"error": "Missing sessionId"}))
                continue

            #  Track current session_id for disconnect save
            current_session_id = session_id

            if session_id not in memory_store:
                memory_store[session_id] = {
                    "lc_memory": [],
                    "history":   [],
                    "user_id":   user_id
                }
                logger.info(f"🆕 Memory initialized for session_id: {session_id}")

            lc_memory = list(memory_store[session_id]["lc_memory"])
            messages  = [get_system_prompt(user_id)] + lc_memory
            messages.append(HumanMessage(content=user_query))

            try:
                final_response_text, _ = await langchain_service.process_query(
                    messages,
                    user_id=user_id,
                    session_id=session_id
                )
                logger.info(f"✅ Response generated for session_id: {session_id}")

            except Exception as e:
                logger.error(f"❌ LangChain error: {e}", exc_info=True)
                final_response_text = "Sorry, something went wrong."

            await websocket.send_text(json.dumps({
                "session_id": session_id,
                "response":   final_response_text
            }))
            await websocket.send_text("[DONE]")

            memory_store[session_id]["lc_memory"].append(HumanMessage(content=user_query))
            memory_store[session_id]["lc_memory"].append(AIMessage(content=final_response_text))
            memory_store[session_id]["history"].append({
                "query":     user_query,
                "assistant": final_response_text
            })

            if len(memory_store[session_id]["history"]) > MAX_HISTORY:
                memory_store[session_id]["history"]   = memory_store[session_id]["history"][-MAX_HISTORY:]
                memory_store[session_id]["lc_memory"] = memory_store[session_id]["lc_memory"][-(MAX_HISTORY * 2):]

            print_memory(session_id)

    except WebSocketDisconnect:
        if current_session_id:
            session_data = memory_store.get(current_session_id, {})
            await save_session_to_supabase(
                session_id = current_session_id,
                user_id    = session_data.get("user_id", ""),
                history    = session_data.get("history", [])
            )
        logger.info("🔌 WebSocket client disconnected")
        
@chatbot_app.post("/sessions")
async def sessions_endpoint(request: SessionRequest):
    user_id    = request.userId.strip()
    session_id = request.sessionId.strip()

    if not user_id:
        logger.info("invalid user id")
        raise HTTPException(status_code=400, detail="userId is required")

    if user_id not in VALID_USER_IDS:
        
        raise HTTPException(status_code=403, detail=f"Invalid user ID '{user_id}'. Access denied.")

    # ── Case 1: session_id is empty → return all sessions for user ──
    if not session_id:
        logger.info(f"📋 Fetching all sessions | user_id={user_id}")
        sessions = await get_sessions_for_user(user_id)
        return {
            "user_id":  user_id,
            "type":     "sessions",
            "sessions": sessions
        }

    # ── Case 2: session_id is provided → return chat history ──
    logger.info(f"💬 Fetching chat history | user_id={user_id} | session_id={session_id}")
    history = await get_chat_history_for_session(user_id, session_id)
    return {
        "user_id":      user_id,
        "session_id":   session_id,
        "type":         "history",
        "chat_history": history
    }


@chatbot_app.on_event("startup")
async def startup_event():
    get_supabase_client()
    await get_pool()
    logger.info("🚀 Supabase and PostgreSQL clients initialized during startup")

@chatbot_app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "Facility Management AI Assistant"}