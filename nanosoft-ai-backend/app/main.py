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
import time

from app.models.schemas import ChatRequest
import base64
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

# =====================================================
# In-Memory Store with TTL cleanup
#
# Structure:
# {
#   "session-abc-123": {
#     "lc_memory": [HumanMessage, AIMessage, ...],
#     "history": [...],
#     "user_name": "v4demo",
#     "last_activity": timestamp
#   }
# }
# =====================================================
MAX_HISTORY = settings.MAX_HISTORY
memory_store = {}
MAX_AUDIO_BYTES = 500 * 1024  # 500 KB

YES_WORDS = {"yes", "yeah", "yep", "yup", "correct", "right",
             "ok", "okay", "sure", "confirmed", "proceed", "go ahead",
             "that's right", "thats right", "yes that's correct"}

NO_WORDS  = {"no", "nope", "nah", "wrong", "incorrect", "not right",
             "that's wrong", "thats wrong", "not correct"}

#Track sessions already saved by frontend HTTP POST
# So WebSocketDisconnect does NOT save again (prevents double save)
frontend_saved_sessions: set = set()

#chat memory for debugging purpose. 
def print_memory(session_id: str):
    session_data = memory_store.get(session_id, {})
    history      = session_data.get("history", [])
    lc_memory    = session_data.get("lc_memory", [])
 
    print(f"\n🧠 SESSION: {session_id} | user: {session_data.get('user_name', 'N/A')}")
 
    print(f"\n💾 HISTORY ({len(history)} entries)")
    for i, item in enumerate(history, 1):
        # ── If audio query → show [AUDIO] instead of base64 encoded string
        raw_query = item.get("query", "")
        is_audio  = item.get("is_audio", False)
        if is_audio or (isinstance(raw_query, str) and raw_query.startswith("data:audio")):
            display_query = "[AUDIO 🎙️]"
        else:
            display_query = raw_query[:100] + ("..." if len(raw_query) > 100 else "")
 
        print(f"  [{i}] Query:     {display_query}")
        print(f"       Assistant: {item['assistant'][:100]}{'...' if len(item['assistant']) > 100 else ''}")
 
    print(f"\n🤖 LC_MEMORY ({len(lc_memory) // 2} pairs | last {settings.MAX_HISTORY} sent to model)")
    pairs = list(zip(lc_memory[0::2], lc_memory[1::2]))
    for i, (h, a) in enumerate(pairs, 1):
        h_content = (h.content or "")
        # ── lc_memory stores the transcribed text not base64
        # so no audio check needed here — just truncate normally
        print(f"  [{i}] Query:     {h_content[:100]}{'...' if len(h_content) > 100 else ''}")
        print(f"       Assistant: {(a.content or '')[:100]}")
 
    print()

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


            if not session_id:
                logger.info("invalid session id")
                await websocket.send_text(json.dumps({"error": "Missing sessionId"}))
                continue

            #  Track current session_id for disconnect save
            current_session_id = session_id

            # Periodic cleanup of expired sessions (every 10th request)
            if hash(session_id) % 10 == 0:
                cleanup_expired_sessions()

            # Update session activity
            update_session_activity(session_id)
            audio_base64   = None   # will hold base64 string if audio
            query_to_store = None
            # ==================================================================
            # ── CONFIRMATION REPLY CHECK
            # ── If pending_transcription exists → user is replying yes/no
            # ==================================================================
            pending_transcription = memory_store.get(session_id, {}).get("pending_transcription")

            if pending_transcription:
                reply_text = data.get("query", "").strip().lower()

                # If reply is audio → transcribe it first
                if is_audio:
                    try:
                        audio_bytes = await asyncio.wait_for(
                            websocket.receive_bytes(),
                            timeout=settings.WS_SESSION_TIMEOUT
                        )
                        transcribed = await convert_audio_to_text(audio_bytes)
                        reply_text  = transcribed["transcription"].strip().lower()
                        logger.info(f"🎙️ Audio confirmation reply: '{reply_text}'")
                    except Exception as e:
                        logger.error(f"❌ Confirmation audio failed: {e}")
                        reply_text = ""

                logger.info(f"🔁 Confirmation reply: '{reply_text}' | pending='{pending_transcription}'")

                # Clear pending immediately
                memory_store[session_id]["pending_transcription"] = None

                if reply_text in YES_WORDS:
                    # User confirmed → run original transcription
                    user_query     = pending_transcription
                    query_to_store =  reply_text
                    logger.info(f"✅ User confirmed → running: '{user_query}'")

                elif reply_text in NO_WORDS:
                    # User said no → ask to rephrase
                    msg = "No problem! Could you please tell me what you meant? I'll try again."
                    await websocket.send_text(json.dumps({
                        "session_id": session_id,
                        "response":   msg
                    }))
                    await websocket.send_text("[DONE]")
                    memory_store[session_id]["history"].append({
                        "query":     pending_transcription,
                        "assistant": msg,
                        "context":   msg,
                        "is_audio":  is_audio
                    })
                    logger.info("🔄 User said no — asked to rephrase")
                    continue

                else:
                    # User gave corrected query directly
                    user_query     = data.get("query", "").strip() if not is_audio else reply_text
                    query_to_store = user_query
                    logger.info(f"🔄 User gave correction → running: '{user_query}'")

            # ==================================================================
            #----------------- audio integration by mega-----------------
            
            # ── NEW: AUDIO PATH — isAudio = true then convert it into the text and send to  process query function
            elif is_audio:
                logger.info(f"🎙️ Audio message | user={user_name} | session={session_id}")

                try:
                    # ── Receive audio bytes ──────────────────────────────────
                    audio_bytes = await asyncio.wait_for(
                        websocket.receive_bytes(),
                        timeout=settings.WS_SESSION_TIMEOUT
                    )
                    logger.info(f"📦 Audio bytes received: {len(audio_bytes)} bytes")

                    # ── Size guard ───────────────────────────────────────────
                    if len(audio_bytes) > MAX_AUDIO_BYTES:
                        await websocket.send_text(json.dumps({
                            "error": "Voice query is too long. Please keep it brief and try again."
                        }))
                        continue

                    audio_base64   = "data:audio/ogg;base64," + base64.b64encode(audio_bytes).decode("utf-8")
                    query_to_store = audio_base64

                    # ── STEP 1: Transcribe + Validate in ONE call ────────────
                    # Returns:
                    # {
                    #   "transcription":          str,
                    #   "uncertain_terms":        list,
                    #   "needs_clarification":    bool,
                    #   "clarification_question": str
                    # }
                    try:
                        transcription_result = await convert_audio_to_text(audio_bytes)
                    except Exception as e:
                        logger.error(f"❌ Transcription failed: {e}")
                        await websocket.send_text(json.dumps({
                            "response": "Sorry, voice input is temporarily unavailable. Please type your message instead."
                        }))
                        await websocket.send_text("[DONE]")
                        continue

                    user_query             = transcription_result["transcription"]
                    uncertain_terms        = transcription_result["uncertain_terms"]
                    needs_clarification    = transcription_result["needs_clarification"]
                    clarification_question = transcription_result["clarification_question"]

                    logger.info(f"📝 Transcribed: '{user_query}' | uncertain={uncertain_terms} | needs_clarification={needs_clarification}")

                    # ── STEP 2: Check if clarification needed ────────────────
                    if needs_clarification:
                        logger.info(f"🔍 Clarification needed: '{clarification_question}'")

                        # ── Send clarification question to frontend ───────────
                        await websocket.send_text(json.dumps({
                            "session_id":          session_id,
                            "response":            clarification_question,
                            "needs_clarification": True
                        }))
                        await websocket.send_text("[DONE]")

                        # ── Store in history ─────────────────────────────────
                        if session_id not in memory_store:
                            memory_store[session_id] = {
                                "lc_memory": [],
                                "history":   [],
                                "user_name": user_name
                            }

                        # ── Save original transcription for yes/no handling ───
                        memory_store[session_id]["pending_transcription"] = user_query
                        logger.info(f"💾 Saved pending_transcription: '{user_query}'")

                        memory_store[session_id]["history"].append({
                            "query":                 query_to_store,
                            "assistant":             clarification_question,
                            "context":               f"Confirmation asked for: {user_query}",
                            "is_audio":              True,
                            "pending_transcription": user_query
                        })

                        # ── Stop here — user reply comes as next message ──────
                        continue

                    else:
                        logger.info(f"✅ Audio validated — PROCEED | query='{user_query}'")

                    # ── user_query is clean and ready ─────────────────────────
                    # Fall through to process_query below

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
            elif not pending_transcription:
                user_query = data.get("query", "").strip()
                query_to_store = user_query
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
                    "user_name": user_name,
                    "pending_transcription": None
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
                # ✅ Send specific message based on error type
                if "timed out" in str(e).lower():
                    final_response_text = " The request is taking too long. Please try again in a moment."
                elif "quota" in str(e).lower() or "429" in str(e):
                    final_response_text = " Service is temporarily busy due to high demand. Please try again in a few seconds."
                else:
                    final_response_text = " Sorry, something went wrong. Please try again."
                
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
                "query":     query_to_store,
                "assistant": final_response_text,  # full data → DB → frontend display
                "context":   context_summary,         # short summary → title generation only
                "is_audio":  is_audio #flag for rendering
            
            })
            logger.info(f"💾 history updated with full response | session={session_id}")

            if len(memory_store[session_id]["history"]) > MAX_HISTORY:
                memory_store[session_id]["history"]   = memory_store[session_id]["history"][-MAX_HISTORY:]
                memory_store[session_id]["lc_memory"] = memory_store[session_id]["lc_memory"][-(MAX_HISTORY * 2):]

            print_memory(session_id)

    except WebSocketDisconnect:
        if current_session_id:
            # Only save on disconnect if frontend has NOT already saved via HTTP POST
            if current_session_id not in frontend_saved_sessions:
                session_data = memory_store.get(current_session_id, {})
                await save_session_to_postgres_service(
                    session_id = current_session_id,
                    user_name  = session_data.get("user_name", ""),
                    history    = session_data.get("history", [])
                )
                logger.info(f"✅ Saved on disconnect | session={current_session_id}")
            else:
                logger.info(f"⏭️ Skipping disconnect save — frontend already saved | session={current_session_id}")
                frontend_saved_sessions.discard(current_session_id)  # cleanup

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

        pending_is_audio = False
        for msg in incoming_history:
            role = (msg.role or "").lower()
            if role == "user":
                pending_query = msg.text or ""
                pending_is_audio = getattr(msg, "isAudio", False)
            elif role == "ai":
                if pending_query is not None:
                    history_pairs.append({
                        "query":     pending_query,
                        "assistant": msg.text or "",
                        "is_audio":  pending_is_audio,
                        "context":   msg.text or ""
                    })
                    pending_query    = None
                    pending_is_audio = False

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
        #Mark this session as saved by frontend
        # So WebSocketDisconnect will NOT save it again
        frontend_saved_sessions.add(session_id)
        logger.info(f"🏷️ Marked session as frontend-saved | session={session_id}")

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
    client_name = request.clientName.strip()
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
        (client_name, service, userId, userName, token),
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

