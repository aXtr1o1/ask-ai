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
from app.models.schemas import SessionRequest, ClientInsertionRequest
from app.services.audio_service import convert_audio_to_text




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

# VALID_USERNAMES = {"v4demo", "poc"}

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

#chat memory for debugging purpose. 
def print_memory(session_id: str):
    session_data = memory_store.get(session_id, {})
    history      = session_data.get("history", [])
    lc_memory    = session_data.get("lc_memory", [])

    print(f"\n🧠 SESSION: {session_id} | user: {session_data.get('user_name', 'N/A')}")

    print(f"\n💾 HISTORY ({len(history)} entries)")
    for i, item in enumerate(history, 1):
        print(f"  [{i}] Query: {item['query']}")
        print(f"       Assitant: {item['assistant'][:100]}{'...' if len(item['assistant']) > 100 else ''}")

    print(f"\n🤖 LC_MEMORY ({len(lc_memory) // 2} pairs | last {settings.MAX_HISTORY} sent to model)")
    pairs = list(zip(lc_memory[0::2], lc_memory[1::2]))
    for i, (h, a) in enumerate(pairs, 1):
        print(f"  [{i}] Query: {(h.content or '')[:100]}")
        print(f"       Assitant: {(a.content or '')[:100]}")

    print()

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
            
            user_name  = str(data.get("userName", ""))
            session_id = str(data.get("sessionId", ""))
            is_audio   = bool(data.get("isAudio", False))  # ── NEW: audio flag
            logger.info(f"📊 isAudio flag received: {is_audio}")
            is_graph = bool(data.get("isGraph", False))
            logger.info(f"📊 isGraph flag received: {is_graph}")

            

            if user_name not in VALID_USERNAMES:
                logger.info("invalid user name")
                await websocket.send_text(json.dumps({"error": "Invalid user name"}))
                continue
            

            if not session_id:
                logger.info("invalid session id")
                await websocket.send_text(json.dumps({"error": "Missing sessionId"}))
                continue

            #  Track current session_id for disconnect save
            current_session_id = session_id
            #----------------- audio integration by mega-----------------
            
            # ── NEW: AUDIO PATH — isAudio = true then convert it into the text and send to  process query function
            if is_audio:
                logger.info(f" Audio message received | user={user_name} | session={session_id}")

                try:
                    # ── Receive raw binary OGG audio bytes ───────────────────
                    audio_bytes = await asyncio.wait_for(
                        websocket.receive_bytes(),
                        timeout=settings.WS_SESSION_TIMEOUT
                    )
                    logger.info(f"📦 Audio bytes received: {len(audio_bytes)} bytes")

                    # ── Convert audio → text via Gemini ─────────────────────
                    user_query = await convert_audio_to_text(audio_bytes)
                    logger.info(f"📝 Audio transcribed: {user_query}")

                except asyncio.TimeoutError:
                    logger.warning("⏰ Timed out waiting for audio bytes")
                    await websocket.send_text(json.dumps({"error": "Timed out waiting for audio data"}))
                    continue

                except Exception as e:
                    logger.error(f"❌ Audio processing failed: {e}", exc_info=True)
                    await websocket.send_text(json.dumps({"error": "Audio processing failed. Please try again."}))
                    continue

            # ==================================================================
            # ── NORMAL TEXT PATH — isAudio = false
            # ==================================================================
            else:
                user_query = data.get("query", "").strip()
                logger.info(f"💬 Text message | user={user_name} | session={session_id} | query={user_query}")

                if not user_query:
                    logger.info("empty user query")
                    await websocket.send_text(json.dumps({"error": "Empty query"}))
                    continue
            
            logger.info(f"WS Request | user_name={user_name} | session_id={session_id} | query={user_query}")
                
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
                # ── CHANGED: process_query now returns 3-tuple (final_response_text, context_summary, messages)
                # ── final_response_text → full data (sent to frontend + stored in history for DB)
                # ── context_summary     → short sentence (stored in lc_memory for model — no token error)
                # langchain_service will use this flag to decide:
                # if is_graph=True AND aggregate query → return graph JSON
                # if is_graph=False → return normal markdown table (unchanged)

                final_response_text, context_summary, _ = await langchain_service.process_query(
                    messages,
                    user_name=user_name,
                    session_id=session_id,
                     is_graph   = is_graph  # graph flag passed here

                )
                logger.info(f"✅ Response generated for session_id: {session_id}")
                logger.info(f"🧠 context_summary for lc_memory: {context_summary[:80]}")

            except Exception as e:
                logger.error(f"❌ LangChain error: {e}", exc_info=True)
                final_response_text = "Sorry, something went wrong."
                # ── CHANGED: fallback context_summary on error
                context_summary = final_response_text

            await websocket.send_text(json.dumps({
                "session_id": session_id,
                "response":   final_response_text
            }))
            await websocket.send_text("[DONE]")

            # ── CHANGED: TWO SEPARATE MEMORIES
            # ── lc_memory → stores context_summary ONLY (sent to model as past context)
            # ──             prevents token limit errors for large datasets / markdown tables
            # ── history   → stores final_response_text (full data: markdown table / large JSON)
            # ──             saved to DB on session end, loaded by frontend for display
            memory_store[session_id]["lc_memory"].append(HumanMessage(content=user_query))
            memory_store[session_id]["lc_memory"].append(AIMessage(content=context_summary))
            logger.info(f"🧠 lc_memory updated with context_summary | session={session_id}")

            memory_store[session_id]["history"].append({
                "query":     user_query,
                "assistant": final_response_text  # full data → DB → frontend display
            })
            logger.info(f"💾 history updated with full response | session={session_id}")

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
    
from app.services.sync.engine import run_sync
@api_router.post("/client_insertion")
async def client_insertion(request: ClientInsertionRequest):
    userId = request.userId.strip()
    userName = request.userName.strip()
    service = request.service.strip()
    token = request.token.strip()
    if not userId or not userName:
        logger.info("invalid client insertion payload")
        raise HTTPException(status_code=400, detail="userId and userName are required")

    conn = None
    try:
        conn = get_pool()
        conn.rollback()  # clear any previous failed transaction
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT client_name, base_url, user_id, user_name, jwt_token, last_synced_at
            FROM client_sync_config
            WHERE user_id = %s AND user_name = %s
            LIMIT 1
            """,
            (userId, userName),
        )

        row = cursor.fetchone()

    except Exception as e:
        logger.error(
            f"❌ Failed to check client_sync_config | user_id={userId} | user_name={userName} | error={e}",
            exc_info=True,
        )
        try:
            if conn is not None and not getattr(conn, "closed", True):
                conn.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Database error while checking client configuration")

    if row:
        client_name, base_url, db_user_id, db_user_name, db_jwt_token, last_synced_at = row
        cursor.close()
        return {
            "client_type": "old",
            "exists": True,
            "client": {
                "client_name": client_name,
                "base_url": base_url,
                "user_id": db_user_id,
                "user_name": db_user_name,
                "token": db_jwt_token,
            },
        }

    # No existing client — insert new row into client_sync_config
    cursor.execute(
        """
        INSERT INTO client_sync_config
        (client_name, base_url, user_id, user_name, jwt_token, last_synced_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        RETURNING id, client_name, base_url, user_id, user_name, jwt_token, last_synced_at
        """,
        (userName, service, userId, userName, token),
    )

    new_row = cursor.fetchone()
    conn.commit()
    cursor.close()

    new_id, client_name, base_url, db_user_id, db_user_name, db_jwt_token, last_synced_at = new_row

    return {
        "client_type": "new",
        "exists": False,
        "client": {
            "id": new_id,
            "client_name": client_name,
            "base_url": base_url,
            "user_id": db_user_id,
            "user_name": db_user_name,
            "service": service,
            "token": db_jwt_token,
        },
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