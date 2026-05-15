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
from app.services.sync.migrate_user import migrate_user

from app.models.schemas import ChatRequest
import re
import base64 
from app.config import settings
from app.services.langchain_service import langchain_service
from app.services.user_profile_service import (
    update_usage_if_exists,
    get_credits_remaining,
    consume_audio_seconds_if_available,
    get_graph_count_and_limit,
    get_user_usage_stats,      
    update_daily_history,      
)
from app.prompts.system_prompt import get_system_prompt
from app.services.postgres_service import save_session_to_postgres_service
from app.api.database.postgres_client import get_pool

from app.services.session_service import get_sessions_for_user, get_chat_history_for_session
from app.models.schemas import SessionRequest, ClientInsertionRequest
from app.services.audio_service import convert_audio_to_text, get_audio_duration_seconds
from app.services.quota_service import quota_fallback_service
from app.voiceAgent_endpoint import voice_agent_router
from app.state import memory_store, MAX_HISTORY, frontend_saved_sessions

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

MAX_AUDIO_BYTES = 500 * 1024  # 500 KB

YES_WORDS = {
    "yes", "yeah", "yep", "yup", "ya", "y",
    "correct", "right", "true", "exactly","give me",
    "ok", "okay", "okey", "k", "kk","kkkk",
    "sure", "surely", "of course",
    "confirmed", "confirm", "confirmation",
    "proceed", "go ahead", "continue",
    "please proceed", "you can proceed",
    "yes please", "go on", "carry on",
    "that's right", "thats right",
    "yes that's correct", "yes thats correct",
    "sounds good", "looks good", "all good",
    "fine", "works", "works for me",
    "perfect", "great", "nice",
    "yess", "yea", "yaah", "yup yup",
    "indeed", "absolutely", "definitely",
    "affirmative", "roger", "approved",
    "do it", "let's go", "lets go"
}

NO_WORDS = {
    "no", "nope", "nah", "n",
    "wrong", "incorrect", "not correct", "not right",
    "that's wrong", "thats wrong",
    "no that's wrong", "no thats wrong",
    "not really", "not exactly",
    "don't", "do not", "dont",
    "stop", "hold on", "wait",
    "cancel", "abort", "skip",
    "no thanks", "no thank you",
    "negative", "decline", "rejected",
    "not good", "bad", "doesn't work", "doesnt work",
    "not fine", "not okay", "not ok",
    "change it", "modify", "edit this",
    "try again", "redo", "recheck",
    "nah bro", "no way", "never",
    "i disagree", "disagree", "not agreed"
}


def _has_date_keyword(text: str) -> bool:
    if not text:
        return False
    q = text.lower()
    keywords = (
        "today", "yesterday", "last week", "this week", "last month", "this month",
        "last year", "this year", "week", "month", "year", "day", "days", "date"
    )
    if any(keyword in q for keyword in keywords):
        return True
    return bool(re.search(r"\b\d{4}-\d{2}-\d{2}\b", q))


def _build_table_context(context_summary: str, user_query: str) -> str:
    # """Keep the table context short, and default to last 7 days when no date is mentioned."""
    """Keep the table context short."""
    summary = (context_summary or "").strip()

    # Remove the follow-up question if it was included in the summary.
    lines = [line.strip() for line in summary.splitlines() if line.strip()]
    lines = [line for line in lines if "would you like to see" not in line.lower()]
    summary = " ".join(lines).strip()

    if not _has_date_keyword(user_query):
        # summary = "Here is the last 7 days data you requested."
        summary = "Here is the data you requested."
        return summary

    if not summary:
        summary = "Here is the detailed table you requested."

    return summary

#Track sessions already saved by frontend HTTP POST
# So WebSocketDisconnect does NOT save again (prevents double save)
# frontend_saved_sessions now imported from app.state


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
                        user_name  = session_data.get("sub_user_name") or session_data.get("user_name", ""),
                        history    = session_data.get("history", []),
                        group_name = session_data.get("group_name")
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
            logger.info(f"📊 user_name={user_name}")
            sub_user_name = str(data.get("subUserName", ""))
            logger.info(f"📊 sub_user_name={sub_user_name}")
            try:
                user_id = int(data.get("userId")) if data.get("userId") is not None else None
            except (ValueError, TypeError):
                user_id = None
            logger.info(f"📊 user_id={user_id}")
            session_id = str(data.get("sessionId", ""))
            is_audio   = bool(data.get("isAudio", False))  # ── NEW: audio flag
            logger.info(f"📊 isAudio flag received: {is_audio}")
            is_graph = bool(data.get("isGraph", False))
            logger.info(f"📊 isGraph flag received: {is_graph}")
            group_name = data.get("group_name") or data.get("groupName")
            logger.info(f"📊 group_name={group_name}")


# Changes done by sanjeevan

            # Client should send audio length for correct quota enforcement.
            # Accept both `audioSeconds` and `audio_seconds`.
            try:
                audio_seconds_request = int(float(data.get("audioSeconds") or data.get("audio_seconds") or 0))
            except Exception:
                audio_seconds_request = 0
            logger.info(f"📊 audio_seconds_request={audio_seconds_request}")


            if not session_id:
                logger.info("invalid session id")
                await websocket.send_text(json.dumps({"error": "Missing sessionId"}))
                continue

            #  Track current session_id for disconnect save
            current_session_id = session_id
            audio_base64   = None   # will hold base64 string if audio
            query_to_store = None
            audio_seconds_effective = 0
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
                        
# Changes done by sanjeevan
                        # ── Size guard ─────────────────────────────────────────
                        if len(audio_bytes) > MAX_AUDIO_BYTES:
                            await websocket.send_text(json.dumps({
                                "error": "Voice query is too long. Please keep it brief and try again."
                            }))
                            await websocket.send_text("[DONE]")
                            continue

                        # ── Audio credits check + consume ───────────────────────
                        computed_audio_seconds = get_audio_duration_seconds(audio_bytes)
                        audio_seconds_effective = (
                            computed_audio_seconds
                            if computed_audio_seconds is not None and computed_audio_seconds > 0
                            else audio_seconds_request
                        )
                        logger.info(
                            "📊 audio_seconds_effective=%s (client=%s, computed=%s)",
                            audio_seconds_effective,
                            audio_seconds_request,
                            computed_audio_seconds,
                        )

                        if audio_seconds_effective and audio_seconds_effective > 0:
                            consumed = await asyncio.to_thread(
                                consume_audio_seconds_if_available,
                                name=sub_user_name,
                                audio_seconds_delta=audio_seconds_effective,
                            )
                            if consumed is False:
                                msg = "Audio credits exhausted. Please recharge/upgrade your plan to continue."
                                await websocket.send_text(json.dumps({
                                    "session_id": session_id,
                                    "response": msg
                                }))
                                await websocket.send_text("[DONE]")
                                continue

                        transcribed = await convert_audio_to_text(audio_bytes)
                        raw_reply   = transcribed["transcription"].strip().lower()
                        
                        reply_text  = re.sub(r'[^\w\s]', '', raw_reply).strip()
                        logger.info(f"🎙️ Audio confirmation reply: '{reply_text}' (raw='{raw_reply}')")
                        
                    except Exception as e:
                        logger.error(f"❌ Confirmation audio failed: {e}")
                        reply_text = ""

                logger.info(f"🔁 Confirmation reply: '{reply_text}' | pending='{pending_transcription}'")

                # Clear pending immediately
                memory_store[session_id]["pending_transcription"] = None
                # ── Check if reply contains any yes/no word ──
                reply_words = set(reply_text.split())
                is_yes = reply_text in YES_WORDS or bool(reply_words & YES_WORDS)
                is_no  = reply_text in NO_WORDS  or bool(reply_words & NO_WORDS)

                if is_yes:
                    user_query     = pending_transcription
                    query_to_store = reply_text
                    logger.info(f"✅ User confirmed → running: '{user_query}'")

                elif is_no:
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
                    user_query     = data.get("query", "").strip() if not is_audio else reply_text
                    query_to_store = user_query
                    logger.info(f"🔄 User gave correction → running: '{user_query}'")

            # ==================================================================
            #----------------- audio integration by mega-----------------
            
            # ── NEW: AUDIO PATH — isAudio = true then convert it into the text and send to  process query function
            
            elif is_audio:
                logger.info(f"🎙️ Audio message | user={sub_user_name} | session={session_id}")

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

                    # ── Check if user is replying yes/no to pending_table via audio ──
                    session_data_audio = memory_store.get(session_id, {})
                    pending_table_audio = session_data_audio.get("pending_table")

                    if pending_table_audio:
                        # Transcribe the audio reply
                        transcribed_reply = await convert_audio_to_text(audio_bytes)
                        raw_reply_table   = transcribed_reply["transcription"].strip().lower()
                        reply_table       = re.sub(r'[^\w\s]', '', raw_reply_table).strip()
                        logger.info(f"🎙️ Audio table reply: '{reply_table}' (raw='{raw_reply_table}')")

                        if reply_table in YES_WORDS:
                            pending_ctx = session_data_audio.get("pending_table_context") or _build_table_context("", pending_transcription)
                            table_response = json.dumps({
                                "context_summary": pending_ctx,
                                "records": pending_table_audio
                            })
                            memory_store[session_id]["pending_table"] = None
                            memory_store[session_id]["pending_table_context"] = None

                            await websocket.send_text(json.dumps({
                                "session_id": session_id,
                                "response": table_response
                            }))
                            await websocket.send_text("[DONE]")

                            memory_store[session_id]["lc_memory"].append(HumanMessage(content=reply_table))
                            memory_store[session_id]["lc_memory"].append(AIMessage(content="Table displayed."))
                            memory_store[session_id]["history"].append({
                                "query":     reply_table,
                                "assistant": table_response,
                                "context":   "Table displayed on user audio request.",
                                "is_audio":  True
                            })
                            logger.info("✅ Table sent on user audio YES | records=%d", len(pending_table_audio))
                            print_memory(session_id)
                            continue

                        elif reply_table in NO_WORDS:
                            memory_store[session_id]["pending_table"] = None
                            memory_store[session_id]["pending_table_context"] = None
                            no_msg = "No problem! Let me know if you have any other questions."

                            await websocket.send_text(json.dumps({
                                "session_id": session_id,
                                "response": no_msg
                            }))
                            await websocket.send_text("[DONE]")

                            memory_store[session_id]["lc_memory"].append(HumanMessage(content=reply_table))
                            memory_store[session_id]["lc_memory"].append(AIMessage(content=no_msg))
                            memory_store[session_id]["history"].append({
                                "query":     reply_table,
                                "assistant": no_msg,
                                "context":   no_msg,
                                "is_audio":  True
                            })
                            logger.info("✅ User declined table via audio")
                            print_memory(session_id)
                            continue

                        else:
                            # Not yes/no — clear pending table and treat as new audio query
                            memory_store[session_id]["pending_table"] = None
                            memory_store[session_id]["pending_table_context"] = None
                            logger.info("⚠️ Audio reply not yes/no — clearing pending_table, processing as new query")

                    

# Changes done by sanjeevan
                    # ── Audio credits check + consume ───────────────────────
                    computed_audio_seconds = get_audio_duration_seconds(audio_bytes)
                    audio_seconds_effective = (
                        computed_audio_seconds
                        if computed_audio_seconds is not None and computed_audio_seconds > 0
                        else audio_seconds_request
                    )
                    logger.info(
                        "📊 audio_seconds_effective=%s (client=%s, computed=%s)",
                        audio_seconds_effective,
                        audio_seconds_request,
                        computed_audio_seconds,
                    )

                    if audio_seconds_effective and audio_seconds_effective > 0:
                        consumed = await asyncio.to_thread(
                            consume_audio_seconds_if_available,
                            name=sub_user_name,
                            audio_seconds_delta=audio_seconds_effective,
                        )
                        if consumed is False:
                            msg = "Audio credits exhausted. Please recharge/upgrade your plan to continue."
                            await websocket.send_text(json.dumps({
                                "session_id": session_id,
                                "response": msg
                            }))
                            await websocket.send_text("[DONE]")

                            if session_id not in memory_store:
                                memory_store[session_id] = {
                                    "lc_memory": [],
                                    "history": [],
                                    "user_name": user_name,
                                    "group_name": group_name,
                                    "pending_transcription": None,
                                }
                            memory_store[session_id]["history"].append({
                                "query": "",
                                "assistant": msg,
                                "context": msg,
                                "is_audio": True,
                            })
                            continue

                        # ✅ Update usage_history immediately when audio is sent
                        try:
                            await asyncio.to_thread(
                                update_daily_history,
                                external_user_id=user_name,
                                name=sub_user_name,
                                credits_delta=0,
                                audio_seconds_delta=int(audio_seconds_effective),
                                graph_delta=0,
                                request_delta=0,
                            )
                            logger.info("✅ usage_history audio saved immediately | audio=%s", audio_seconds_effective)
                        except Exception as e:
                            logger.warning("⚠️ update_daily_history audio failed: %s", str(e)[:200])
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
                                "user_name": user_name,
                                "group_name": group_name
                            }

                        # ── Save original transcription for yes/no handling ───
                        memory_store[session_id]["pending_transcription"] = user_query
                        memory_store[session_id]["pending_audio_seconds"] = audio_seconds_effective
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

                # ── Reconstruct full query if user is replying to a clarification ──
                session_data_check = memory_store.get(session_id, {})
                pending_original_query = session_data_check.get("pending_original_query")
                if pending_original_query:
                    user_query = f"{pending_original_query} {user_query}".strip()
                    memory_store[session_id]["pending_original_query"] = None
                    logger.info(f"🔁 Reconstructed query: '{user_query}'")
                
                # ✅ CHECK IF USER IS REPLYING TO QUOTA MENU
                session_data = memory_store.get(session_id, {})
                waiting_for_choice = session_data.get("waiting_for_table_choice", False)
                
                # ── QUOTA FALLBACK: user is choosing which table to query ──
                if waiting_for_choice:
                    logger.info(f"🔄 User replying to quota menu | reply: '{user_query}'")
                    
                    # Clear the flag immediately
                    memory_store[session_id]["waiting_for_table_choice"] = False
                    
                    # Handle the user's table choice
                    final_response_text, context_summary = quota_fallback_service.handle_user_table_choice(
                        user_reply=user_query,
                        user_name=user_name
                    )
                    
                    if final_response_text is None:
                        # Could not parse table type — ask again
                        error_msg = (
                            "I couldn't determine which table you want. "
                            "Please reply with one of: **assets**, **ppm**, **bdm**, **fa**, or **sb**."
                        )
                        await websocket.send_text(json.dumps({
                            "session_id": session_id,
                            "response": error_msg
                        }))
                        await websocket.send_text("[DONE]")
                        
                        memory_store[session_id]["history"].append({
                            "query": query_to_store,
                            "assistant": error_msg,
                            "context": error_msg,
                            "is_audio": is_audio
                        })
                        logger.info("⚠️ Could not parse table choice — asked user again")
                        continue
                    
                    # Successfully retrieved data — send to user
                    await websocket.send_text(json.dumps({
                        "session_id": session_id,
                        "response": final_response_text
                    }))
                    await websocket.send_text("[DONE]")
                    
                    memory_store[session_id]["lc_memory"].append(HumanMessage(content=user_query))
                    memory_store[session_id]["lc_memory"].append(AIMessage(content=context_summary))
                    memory_store[session_id]["history"].append({
                        "query": query_to_store,
                        "assistant": final_response_text,
                        "context": context_summary,
                        "is_audio": is_audio
                    })
                    
                    logger.info(f"✅ Quota fallback response sent | context: {context_summary}")
                    print_memory(session_id)
                    continue  # ← CRITICAL: Skip process_query completely
                
                # ── TWO-STEP TABLE: check if user is replying yes/no to table question
                pending_table = session_data.get("pending_table")

                if pending_table:
                    reply = user_query.strip().lower()
                    logger.info(f"🔍 pending_table check | reply='{reply}' | in_YES_WORDS={reply in YES_WORDS} | in_NO_WORDS={reply in NO_WORDS}")

                    if reply in YES_WORDS:
                        pending_ctx = session_data.get("pending_table_context") or _build_table_context("", user_query)
                        table_response = json.dumps({
                            "context_summary": pending_ctx,
                            "records": pending_table
                        })
                        memory_store[session_id]["pending_table"] = None
                        memory_store[session_id]["pending_table_context"] = None

                        await websocket.send_text(json.dumps({
                            "session_id": session_id,
                            "response": table_response
                        }))
                        await websocket.send_text("[DONE]")

                        memory_store[session_id]["lc_memory"].append(HumanMessage(content=user_query))
                        memory_store[session_id]["lc_memory"].append(AIMessage(content="Table displayed."))
                        memory_store[session_id]["history"].append({
                            "query":     query_to_store,
                            "assistant": table_response,
                            "context":   "Table displayed on user request.",
                            "is_audio":  is_audio
                        })
                        logger.info("✅ Table sent on user YES | records=%d", len(pending_table))
                        print_memory(session_id)
                        continue

                    elif reply in NO_WORDS:
                        memory_store[session_id]["pending_table"] = None
                        memory_store[session_id]["pending_table_context"] = None
                        no_msg = "No problem! Let me know if you have any other questions."

                        await websocket.send_text(json.dumps({
                            "session_id": session_id,
                            "response": no_msg
                        }))
                        await websocket.send_text("[DONE]")

                        memory_store[session_id]["lc_memory"].append(HumanMessage(content=user_query))
                        memory_store[session_id]["lc_memory"].append(AIMessage(content=no_msg))
                        memory_store[session_id]["history"].append({
                            "query":     query_to_store,
                            "assistant": no_msg,
                            "context":   no_msg,
                            "is_audio":  is_audio
                        })
                        logger.info("✅ User declined table")
                        print_memory(session_id)
                        continue

                    else:
                        # User sent a new query — clear pending and fall through
                        memory_store[session_id]["pending_table"] = None
                        memory_store[session_id]["pending_table_context"] = None
                        logger.info("⚠️ Non-yes/no after table question — clearing pending_table, processing as new query")
            
            # ── Continue to normal query processing ──
            logger.info(f"WS Request | user_name={user_name} | session_id={session_id} | query={user_query}")
            
        
                
            if session_id not in memory_store:
                memory_store[session_id] = {
                    "lc_memory": [],
                    "history":   [],
                    "user_name":     user_name,
                    "sub_user_name": sub_user_name,
                    "pending_transcription": None,
                    "group_name": group_name
                }
                logger.info(f"🆕 Memory initialized for session_id: {session_id}")
            else:
                # Update group_name if it was passed
                if group_name:
                    memory_store[session_id]["group_name"] = group_name

            lc_memory = list(memory_store[session_id]["lc_memory"])
            messages  = [get_system_prompt(user_name)] + lc_memory
            messages.append(HumanMessage(content=user_query))

# Changes done by sanjeevan
            try:
                # ── Credits gate: if credits_remaining == 0, skip model ───────
                try:
                    credits_remaining = await asyncio.to_thread(get_credits_remaining, sub_user_name)  # TODO: swap to real external user id from auth
                except Exception as e:
                    logger.warning("⚠️ credits check failed (continuing): %s", str(e)[:200])
                    credits_remaining = None

                if credits_remaining == 0:
                    final_response_text = "You’re out of credits. Please recharge/upgrade your plan to continue."
                    context_summary = final_response_text
                    logger.info("⛔ Credits exhausted | name=%s", sub_user_name)
                else:
                    # ── Graph gate: if graph_count > graph_limit, skip model ───
                    try:
                        if is_graph:
                            graph_info = await asyncio.to_thread(get_graph_count_and_limit, sub_user_name)
                        else:
                            graph_info = None
                    except Exception as e:
                        logger.warning("⚠️ graph check failed (continuing): %s", str(e)[:200])
                        graph_info = None

                    if is_graph and graph_info is not None:
                        graph_count, graph_limit = graph_info
                        # If graph_count already reached the allowed limit, block the model call.
                        # This avoids "count crosses the limit in the same request" behavior.
                        if graph_count >= graph_limit:
                            final_response_text = "Your graph credits is over. Please recharge/upgrade your plan to continue."
                            context_summary = final_response_text
                            logger.info(
                                "⛔ Graph exhausted | name=%s graph_count=%s graph_limit=%s",
                                user_name,
                                graph_count,
                                graph_limit,
                            )
                        else:
                            final_response_text, context_summary, _ = await langchain_service.process_query(
                            messages,
                            user_name=user_name,
                            user_id=user_id,
                            session_id=session_id,
                            is_graph=is_graph,
                        )
                    else:
                        final_response_text, context_summary, _ = await langchain_service.process_query(
                            messages,
                            user_name=user_name,
                            user_id=user_id,
                            session_id=session_id,
                            is_graph=is_graph,
                        )

                    logger.info(f"✅ Response generated for session_id: {session_id}")
                    logger.info(f"🧠 context_summary for lc_memory: {context_summary[:80]}")

            except Exception as e:
                logger.error(f"❌ LangChain error: {e}", exc_info=True)
                # ✅ Send specific message based on error type
                if quota_fallback_service.is_quota_error(e):
                    logger.warning("⚠️ Quota error caught in main.py - showing menu to user")
                    
                    # Get the quota exceeded message
                    quota_message = quota_fallback_service.get_quota_exceeded_message()
                    
                    # Mark this session as waiting for user's table choice
                    if session_id not in memory_store:
                        memory_store[session_id] = {
                            "lc_memory": [],
                            "history": [],
                            "user_name": user_name,
                            "pending_transcription": None
                        }
                    
                    # Set flag to indicate we're waiting for table choice
                    memory_store[session_id]["waiting_for_table_choice"] = True
                    
                    final_response_text = quota_message
                    context_summary = "AI quota exceeded - waiting for user table choice"
                    
                    logger.info("✅ Quota exceeded message sent to user")
                
                # Handle other errors
                elif "timed out" in str(e).lower():
                    final_response_text = "The request is taking too long. Please try again."
                    context_summary = final_response_text
                else:
                    final_response_text = "Sorry, something went wrong. Please try again."
                    context_summary = final_response_text
                
                context_summary = final_response_text

            await websocket.send_text(json.dumps({
                "session_id": session_id,
                "response":   final_response_text
            }))
            await websocket.send_text("[DONE]")
            
# Changes done by sanjeevan

            # ── Update user_profile usage counters after each response ───────
            try:
                tokens_delta = int(getattr(langchain_service, "_total_tokens", 0) or 0)
                is_graph_response = False
                graph_delta = 0
                # Graph responses are JSON with {"type":"graph", ...}
                if bool(is_graph) and isinstance(final_response_text, str):
                    try:
                        payload = json.loads(final_response_text)
                        is_graph_response = isinstance(payload, dict) and payload.get("type") == "graph"
                    except Exception:
                        is_graph_response = False
                if is_graph_response:
                    graph_delta = 1
                
                await asyncio.to_thread(
                    update_usage_if_exists,
                    name=sub_user_name,  # TODO: swap to real external user id from auth
                    tokens_used_delta=tokens_delta,
                    request_delta=1,
                    graph_delta=graph_delta,
                    credits_per_request=1,
                    audio_seconds_delta=audio_seconds_effective,
                )
            except Exception as e:
                logger.warning("⚠️ user_profile update failed: %s", str(e)[:200])
             # ── Update daily history for trend charts ─────────────
            try:
                await asyncio.to_thread(
                    update_daily_history,
                    external_user_id=user_name,
                    name=sub_user_name,
                    credits_delta=1,
                    audio_seconds_delta=audio_seconds_effective,
                    graph_delta=graph_delta,
                    request_delta=1,
                    tokens_delta=tokens_delta,
                )
            except Exception as e:
                logger.warning("⚠️ update_daily_history failed: %s", str(e)[:200])
                

            # ── CHANGED: TWO SEPARATE MEMORIES
            # ── lc_memory → stores context_summary ONLY (sent to model as past context)
            # ──             prevents token limit errors for large datasets / markdown tables
            # ── history   → stores final_response_text (full data: markdown table / large JSON)
            # ──             saved to DB on session end, loaded by frontend for display
            memory_store[session_id]["lc_memory"].append(HumanMessage(content=user_query))
            memory_store[session_id]["lc_memory"].append(AIMessage(content=context_summary))
            logger.info(f"🧠 lc_memory updated with context_summary | session={session_id}")

            # ── If model asked clarification (no tool ran) → save original query ──
            # Detected by checking if response contains clarification keywords
            clarification_keywords = ["do you mean", "please clarify", "fa complaints or bdm", "ppm.*or.*sb", "could you clarify"]
            import re as _re
            is_clarification = any(_re.search(kw, final_response_text.lower()) for kw in clarification_keywords)
            if is_clarification:
                memory_store[session_id]["pending_original_query"] = query_to_store
                logger.info(f"💾 Saved pending_original_query: '{query_to_store}'")
            # ── Stash pending table data if response ends with table question
            # ── langchain_service stores p_list_for_model on self for this purpose
            pending_table = getattr(langchain_service, "_last_pending_table", None)
            if pending_table:
                memory_store[session_id]["pending_table"] = pending_table
                memory_store[session_id]["pending_table_context"] = _build_table_context(context_summary, query_to_store)
                langchain_service._last_pending_table = None  # clear after stashing
                logger.info(f"📋 Stashed pending_table | records={len(pending_table)} | context_saved=True")

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
                    user_name  = session_data.get("sub_user_name") or session_data.get("user_name", ""),
                    history    = session_data.get("history", []),
                    group_name = session_data.get("group_name")
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
            history    = history_pairs,
            group_name = request.group_name
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
#added by sudharshan for renmaing the session

@api_router.post("/session/rename")
async def rename_session_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    session_id = str(payload.get("sessionId", "")).strip()
    title = str(payload.get("title", "")).strip()

    if not user_name or not session_id or not title:
        raise HTTPException(status_code=400, detail="userName, sessionId and title are required")

    from app.services.postgres_service import update_session_title
    ok = await update_session_title(session_id, user_name, title)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update session title")
    return {"status": "ok", "sessionId": session_id, "title": title}

#added by sudharshan for deleting the session
@api_router.post("/session/delete")
async def delete_session_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    session_id = str(payload.get("sessionId", "")).strip()

    if not user_name or not session_id:
        raise HTTPException(status_code=400, detail="userName and sessionId are required")

    from app.services.postgres_service import delete_session_from_postgres
    ok = await delete_session_from_postgres(session_id, user_name)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete session")
    return {"status": "ok", "sessionId": session_id}
    
@api_router.post("/sessions/pin")
async def pin_session_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    session_id = str(payload.get("sessionId", "")).strip()
    is_pinned = bool(payload.get("isPinned", False))

    if not user_name or not session_id:
        raise HTTPException(status_code=400, detail="userName and sessionId are required")

    from app.services.postgres_service import toggle_pin_session
    ok = await toggle_pin_session(session_id, user_name, is_pinned)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat session not found for this user")
    return {"status": "ok", "sessionId": session_id, "isPinned": is_pinned}

@api_router.post("/sessions/archive")
async def archive_session_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    session_id = str(payload.get("sessionId", "")).strip()
    is_archived = bool(payload.get("isArchived", False))

    if not user_name or not session_id:
        raise HTTPException(status_code=400, detail="userName and sessionId are required")

    from app.services.postgres_service import toggle_archive_session
    ok = await toggle_archive_session(session_id, user_name, is_archived)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat session not found for this user")
    return {"status": "ok", "sessionId": session_id, "isArchived": is_archived}

@api_router.post("/sessions/share")
async def share_session_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    session_id = str(payload.get("sessionId", "")).strip()
    is_public = bool(payload.get("isPublic", False))

    if not user_name or not session_id:
        raise HTTPException(status_code=400, detail="userName and sessionId are required")

    from app.services.postgres_service import toggle_session_public
    ok = await toggle_session_public(session_id, user_name, is_public)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat session not found for this user")
    return {"status": "ok", "sessionId": session_id, "isPublic": is_public}

#  changes done by megnathan: Added share code generation and import endpoints */
@api_router.post("/sessions/generate-share-code")
async def generate_share_code_endpoint(payload: dict):
    session_id = str(payload.get("sessionId", "")).strip()
    user_name = str(payload.get("userName", "")).strip()
    if not session_id or not user_name:
        raise HTTPException(status_code=400, detail="sessionId and userName are required")
    from app.services.session_service import generate_share_code
    code = await generate_share_code(session_id, user_name)
    if not code:
        raise HTTPException(status_code=500, detail="Failed to generate share code")
    return {"status": "ok", "shareCode": code}

@api_router.post("/sessions/import-by-code")
async def import_by_code_endpoint(payload: dict):
    share_code = str(payload.get("shareCode", "")).strip()
    current_user = str(payload.get("userName", "")).strip()
    if not share_code or not current_user:
        raise HTTPException(status_code=400, detail="shareCode and userName are required")
    from app.services.session_service import import_session_by_code
    new_session_id = await import_session_by_code(share_code, current_user)
    if not new_session_id:
        raise HTTPException(status_code=404, detail="Invalid share code or failed to import")
    return {"status": "ok", "newSessionId": new_session_id}


@api_router.post("/folder/create")
async def create_folder_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    folder_name = str(payload.get("folderName", "")).strip()

    if not user_name or not folder_name:
        raise HTTPException(status_code=400, detail="userName and folderName are required")

    from app.services.postgres_service import create_folder
    ok = await create_folder(user_name, folder_name)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to create folder")
    return {"status": "ok", "folderName": folder_name}


@api_router.post("/folder/rename")
async def rename_folder_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    old_folder_name = str(payload.get("oldFolderName", "")).strip()
    new_folder_name = str(payload.get("newFolderName", "")).strip()

    if not user_name or not old_folder_name or not new_folder_name:
        raise HTTPException(status_code=400, detail="userName, oldFolderName and newFolderName are required")

    from app.services.postgres_service import rename_folder
    ok = await rename_folder(user_name, old_folder_name, new_folder_name)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to rename folder")
    return {"status": "ok", "oldFolderName": old_folder_name, "newFolderName": new_folder_name}


@api_router.post("/folder/delete")
async def delete_folder_endpoint(payload: dict):
    user_name = str(payload.get("userName", "")).strip()
    folder_name = str(payload.get("folderName", "")).strip()

    if not user_name or not folder_name:
        raise HTTPException(status_code=400, detail="userName and folderName are required")

    from app.services.postgres_service import delete_folder
    ok = await delete_folder(user_name, folder_name)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete folder")
    return {"status": "ok", "folderName": folder_name}


@api_router.get("/folders/{user_name}")
async def get_folders_endpoint(user_name: str):
    if not user_name:
        raise HTTPException(status_code=400, detail="userName is required")

    from app.services.postgres_service import get_folders
    folders = await get_folders(user_name)
    return {"status": "ok", "folders": folders}


@chatbot_app.get("/api/share/history")
async def get_shared_history(sessionId: str, owner: str = None):
    from app.services.postgres_service import get_public_chat_history
    history = await get_public_chat_history(sessionId, owner)
    if history is None:
        raise HTTPException(status_code=404, detail="Shared session not found or private")
    return {"status": "ok", "history": history}
    
@api_router.post("/client_insertion")
async def client_insertion(request: ClientInsertionRequest):
    userId     = request.userId.strip()
    userName   = request.userName.strip()
    service    = request.service.strip()
    client_name = request.clientName.strip()
    token      = request.token.strip()

    if not userId or not userName:
        logger.info("invalid client insertion payload")
        raise HTTPException(status_code=400, detail="userId and userName are required")
    
    conn = None
    try:
        conn = get_pool()
        conn.rollback()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT client_name, base_url, user_id, user_name, jwt_token, last_synced_at
            FROM client_sync_config
            WHERE client_name = %s
            LIMIT 1
            """,
            (client_name,),
        )
        row = cursor.fetchone()
        cursor.close()

    except Exception as e:
        logger.error(
            f"❌ Failed to check client_sync_config | client_name = {client_name} | error={e}",
            exc_info=True,
        )
        try:
            if conn is not None and not getattr(conn, "closed", True):
                conn.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Database error while checking client configuration")

    # ── Old client — already exists ──
    if row:
        client_name, base_url, db_user_id, db_user_name, db_jwt_token, last_synced_at = row
        return {
            "client_type": "old",
            "exists": True,
            "client": {
                "client_name": client_name,
                "base_url":    base_url,
                "user_id":     db_user_id,
                "user_name":   db_user_name,
                "token":       db_jwt_token,
            },
        }

    # ── New client — call migrate_user which handles insert + full data sync ──
    try:
        result = await asyncio.to_thread(
            migrate_user,
            client_name = client_name,
            base_url    = service,
            user_id     = int(userId),
            user_name   = userName,
            jwt_token   = token,
        )
        logger.info(f"✅ migrate_user completed | client={client_name} | status={result.get('status')}")

        return {
            "client_type": "new",
            "exists":      False,
            "client": {
                "client_name": client_name,
                "base_url":    service,
                "user_id":     userId,
                "user_name":   userName,
                "service":     service,
                "token":       token,
            },
            "migration": result,
        }

    except Exception as e:
        logger.error(f"❌ migrate_user failed | client={client_name} | error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Client migration failed. Please try again.")


@api_router.get("/usage/{external_user_id}/{user_name}", tags=["usage"])
async def get_usage_stats(external_user_id: str, user_name: str):

    if not external_user_id or not user_name:
        raise HTTPException(status_code=400, detail="external_user_id and user_name are required")

    try:
        stats = await asyncio.to_thread(
            get_user_usage_stats,
            external_user_id.strip(),  # ✅ pass both
            user_name.strip()
        )

        if not stats:
            raise HTTPException(
                status_code=404,
                detail=f"No usage data found for user: {user_name}"
            )

        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "❌ get_usage_stats failed | external_user_id=%s user_name=%s | error=%s",
            external_user_id, user_name, e
        )
        raise HTTPException(status_code=500, detail="Failed to fetch usage stats")

@api_router.get("/health", tags=["Health"])
def api_health():
    return {"status": "ok", "service": "Facility Management AI Assistant"}
#voice agent endpoint added by sudharshan
chatbot_app.include_router(api_router)
chatbot_app.include_router(voice_agent_router)

@chatbot_app.on_event("startup")
async def startup_event():
    get_pool()
    logger.info("🚀 PostgreSQL client initialized during startup")

@chatbot_app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "Facility Management AI Assistant"}