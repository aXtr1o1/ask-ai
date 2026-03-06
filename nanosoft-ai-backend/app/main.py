"""
Facility Management AI Chatbot — Main App
"""
from fastapi import FastAPI, HTTPException, APIRouter
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
from app.services.postgres_service import save_session_to_postgres_service
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

# API router — all backend endpoints under /api for nginx routing
api_router = APIRouter(prefix="/api", tags=["api"])

VALID_USERNAMES = {"v4demo", "poc"}

# =====================================================
# In-Memory Store
#
# Structure:
# {
#   "session-abc-123": {
#     "lc_memory": [HumanMessage, AIMessage, ...],
#     "history": [...],
#     "user_name": "v4demo"
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
    user_name = session_data.get("user_name", "N/A")
    print(f"  User name : {user_name}")
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

@api_router.websocket("/chat")
async def ws_chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 WebSocket connection accepted")

    current_session_id = None  # track session so we can save on disconnect

    try:
        while True:
            try:
                # Wait for next message; timeout = WS_SESSION_TIMEOUT
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=settings.WS_SESSION_TIMEOUT
                )
            except asyncio.TimeoutError:
                logger.info(f"⏰ WebSocket auto-closed after {settings.WS_SESSION_TIMEOUT}s inactivity")
                await websocket.close()
                if current_session_id:
                    session_data = memory_store.get(current_session_id, {})
                    await save_session_to_postgres_service(
                        session_id = current_session_id,
                        user_name  = session_data.get("user_name", ""),
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
            user_name  = str(data.get("userName", ""))
            session_id = str(data.get("sessionId", ""))

            logger.info(f"WS Request | user_name={user_name} | session_id={session_id} | query={user_query}")

            if user_name not in VALID_USERNAMES:
                logger.info("invalid user name")
                await websocket.send_text(json.dumps({"error": "Invalid user name"}))
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
                    "user_name": user_name
                }
                logger.info(f"🆕 Memory initialized for session_id: {session_id}")

            lc_memory = list(memory_store[session_id]["lc_memory"])
            messages  = [get_system_prompt(user_name)] + lc_memory
            messages.append(HumanMessage(content=user_query))

            try:
                final_response_text, _ = await langchain_service.process_query(
                    messages,
                    user_name=user_name,
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
            await save_session_to_postgres_service(
                session_id = current_session_id,
                user_name = session_data.get("user_name", ""),
                history   = session_data.get("history", [])
            )
        logger.info("🔌 WebSocket client disconnected")
        
@api_router.post("/session")
async def sessions_endpoint(request: SessionRequest):
    user_name  = request.userName.strip()
    session_id = request.sessionId.strip()
    incoming_history = request.chatHistory or []

    if not user_name:
        logger.info("invalid user name")
        raise HTTPException(status_code=400, detail="userName is required")

    if user_name not in VALID_USERNAMES:
        raise HTTPException(status_code=403, detail=f"Invalid user name '{user_name}'. Access denied.")

    # ── Case 1: chatHistory present → save session to PostgreSQL ──
    if incoming_history:
        logger.info(f"💾 Saving chat history | user_name={user_name} | session_id={session_id} | messages={len(incoming_history)}")

        # Convert flat message list [{role,user/ai,text}] → [{query, assistant}] pairs
        history_pairs = []
        pending_query = None

        for msg in incoming_history:
            role = (msg.role or "").lower()
            if role == "user":
                pending_query = msg.text or ""
            elif role == "ai":
                if pending_query is not None:
                    history_pairs.append({
                        "query": pending_query,
                        "assistant": msg.text or ""
                    })
                    pending_query = None

        # If conversation ended with a user message but no assistant reply,
        # still persist it with empty assistant text so it's not lost.
        if pending_query:
            history_pairs.append({
                "query": pending_query,
                "assistant": ""
            })

        await save_session_to_postgres_service(
            session_id = session_id,
            user_name  = user_name,
            history    = history_pairs
        )

        return {
            "user_name":  user_name,
            "session_id": session_id,
            "type":       "saved",
            "messages":   len(history_pairs)
        }

    # ── Case 2: session_id is empty → return all sessions for user ──
    if not session_id:
        logger.info(f"📋 Fetching all sessions | user_name={user_name}")
        sessions = await get_sessions_for_user(user_name)
        return {
            "user_name": user_name,
            "type":      "sessions",
            "sessions":  sessions
        }

    # ── Case 3: session_id is provided → return chat history ──
    logger.info(f"💬 Fetching chat history | user_name={user_name} | session_id={session_id}")
    history = await get_chat_history_for_session(user_name, session_id)
    return {
        "user_name":     user_name,
        "session_id":    session_id,
        "type":          "history",
        "chat_history":  history
    }


@api_router.get("/health", tags=["Health"])
def api_health():
    return {"status": "ok", "service": "Facility Management AI Assistant"}


chatbot_app.include_router(api_router)

@chatbot_app.on_event("startup")
async def startup_event():
    get_pool()
    logger.info("🚀 PostgreSQL client initialized during startup")

@chatbot_app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "Facility Management AI Assistant"}
