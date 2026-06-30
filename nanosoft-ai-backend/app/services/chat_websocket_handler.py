from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import asyncio
import json
import re
import base64
from langchain_core.messages import HumanMessage, AIMessage
from app.config import settings
from app.services.langchain_service import langchain_service
from app.services.user_profile_service import update_usage_if_exists, get_credits_remaining, consume_audio_seconds_if_available, get_graph_count_and_limit, get_user_usage_stats, update_daily_history
from app.services.postgres_service import save_session_to_postgres_service
from app.services.audio_service import convert_audio_to_text, get_audio_duration_seconds
from app.services.quota_service import quota_fallback_service
from app.services.scoped_memory_service import build_scoped_messages
from app.state import memory_store, MAX_HISTORY, frontend_saved_sessions, lc_memory_for_model, trim_session
from app.services.space_booking_service import space_booking_service

logger = logging.getLogger('chat_websocket')
chat_websocket_router = APIRouter()

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

_TABLE_OFFER_MARKERS = (
    "would you like",
    "see the details",
    "see the full table",
    "see the detailed",
    "want to see",
    "show you the",
)


def _expand_affirmative_from_history(user_query: str, session_data: dict) -> str:
    """
    When MAX_HISTORY=0 the model only sees the current message. If the user replies
    'yes' after a data answer, replay the previous question as 'show me …'.
    """
    reply = (user_query or "").strip().lower()
    if reply not in YES_WORDS:
        return user_query
    history = session_data.get("history") or []
    if not history:
        return user_query
    last = history[-1]
    prev_query = (last.get("query") or "").strip()
    if not prev_query:
        return user_query
    prev_assistant = last.get("assistant") or last.get("context") or ""
    prev_text = (
        prev_assistant if isinstance(prev_assistant, str) else str(prev_assistant)
    ).lower()
    offered_more = any(m in prev_text for m in _TABLE_OFFER_MARKERS)
    prev_lower = prev_query.lower()
    was_facility_query = any(
        w in prev_lower
        for w in (
            "bdm", "fa", "complaint", "ppm", "sb", "asset",
            "how many", "show", "give", "list", "registered",
        )
    )
    if offered_more or was_facility_query:
        if not prev_lower.startswith(("show ", "give ", "list ", "display ")):
            expanded = f"show me {prev_query}"
            logger.info("🔁 Expanded '%s' → '%s' (from history; MAX_HISTORY may be 0)", user_query, expanded)
            return expanded
    return user_query


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


# ── Single words that signal "user chose a specific dataset" ──────────────────
_DATASET_SIGNAL_WORDS: set = {
    "assets", "asset", "ppm", "bdm", "fa", "sb",
    "preventive", "breakdown", "breakdowns", "facility",
    "schedule", "scheduled", "based", "maintenance",
    "audit", "audits", "equipment", "equipments",
    "device", "devices", "complaints", "complaint",
    "work", "orders", "order",
}

# ── STRONG all-meaning words — always signal "give me ALL datasets" ───────────
# These are unambiguous regardless of sentence length.
_ALL_MEANING_STRONG: set = {
    "all", "every", "everything", "each", "entire", "both",
}

# ── WEAK all-meaning words — only count when reply is SHORT (≤3 words) ────────
# "many" / "full" / "complete" are common in NEW questions ("how many X are there")
# so they only count as all-datasets when the user typed them as a SHORT reply.
_ALL_MEANING_WEAK: set = {
    "many", "complete", "full", "total",
}

# ── Multi-word phrases meaning "give me ALL datasets" ─────────────────────────
_ALL_PHRASE_RE = re.compile(
    r"all\s+of\s+(them|it|the)"
    r"|all\s+(five|5|data|datasets?|records?)"
    r"|(show|give|fetch|get|retrieve|want|need)\s+(me\s+)?all"
    r"|i\s+want\s+all|entire\s+data|full\s+data|complete\s+data",
    re.IGNORECASE,
)


def _is_all_datasets_reply(reply: str) -> bool:
    """
    True if user's reply means they want ALL datasets.

    STRONG words (all/every/everything/each/entire/both) → always all-datasets.
    WEAK words (many/full/complete/total) → only when reply is ≤3 words.
      e.g. "many"          (1 word)  → all-datasets ✅
           "how many X Y"  (5 words) → NOT all-datasets ✅ (new question)
    """
    words = re.findall(r"\b\w+\b", (reply or "").lower())
    word_set = set(words)
    if word_set & _ALL_MEANING_STRONG:
        return True
    if word_set & _ALL_MEANING_WEAK and len(words) <= 3:
        return True
    return bool(_ALL_PHRASE_RE.search(reply or ""))


def _is_dataset_reply(reply: str) -> bool:
    """
    True if reply contains ANY dataset-selection signal
    (specific dataset name OR all-meaning word/phrase).
    Uses the same length-gating for weak all-meaning words.
    """
    words = re.findall(r"\b\w+\b", (reply or "").lower())
    word_set = set(words)
    if word_set & (_DATASET_SIGNAL_WORDS | _ALL_MEANING_STRONG):
        return True
    if word_set & _ALL_MEANING_WEAK and len(words) <= 3:
        return True
    return bool(_ALL_PHRASE_RE.search(reply or ""))


def _should_break_pending(user_query: str) -> bool:
    """
    Return True  -> new question: forget the pending clarification.
    Return False -> clarification answer: keep it (merge and process).
    Uses positive detection with length-gating for weak all-meaning words.
    """
    if not user_query:
        return False
    if _is_dataset_reply(user_query):
        return False
    return True


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
 
    sent_to_model = lc_memory_for_model(lc_memory, settings.MAX_HISTORY)
    print(
        f"\n🤖 LC_MEMORY ({len(lc_memory) // 2} stored | "
        f"{len(sent_to_model) // 2} sent to model | MAX_HISTORY={settings.MAX_HISTORY})"
    )
    pairs = list(zip(sent_to_model[0::2], sent_to_model[1::2]))
    for i, (h, a) in enumerate(pairs, 1):
        h_content = (h.content or "")
        # ── lc_memory stores the transcribed text not base64
        # so no audio check needed here — just truncate normally
        print(f"  [{i}] Query:     {h_content[:100]}{'...' if len(h_content) > 100 else ''}")
        print(f"       Assistant: {(a.content or '')[:100]}")
 
    print()

@chat_websocket_router.websocket("/chat")
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
                        group_name = session_data.get("group_name"),
                        is_space_booking = session_data.get("is_space_booking", False)
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
            is_space_booking = bool(data.get("isSpaceBooking", False))
            is_advance_ask_ai = bool(data.get("isAdvanceAskAi", False))
            logger.info(f"🔍 isSpaceBooking flag received: {is_space_booking}")
            logger.info(f"🔍 isAdvanceAskAi flag received: {is_advance_ask_ai}")
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
                            pending_search_context = session_data_audio.get("pending_search_context")
                            table_response = json.dumps({
                                "type": "large_dataset",
                                "context_summary": pending_ctx,
                                "records": pending_table_audio,
                                "search_context": pending_search_context,
                            })
                            memory_store[session_id]["pending_table"] = None
                            memory_store[session_id]["pending_table_context"] = None
                            memory_store[session_id]["pending_search_context"] = None

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
                            trim_session(memory_store[session_id], MAX_HISTORY)
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
                            trim_session(memory_store[session_id], MAX_HISTORY)
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

                # All follow-up resolution (pronouns, bare affirmations, etc.) is handled
                # by the model via scoped_memory_service instructions — no Python interception.
                # ── Reconstruct full query if user is replying to a clarification ──
                session_data_check = memory_store.get(session_id, {})
                pending_original_query = session_data_check.get("pending_original_query")
                if pending_original_query:
                    # If user's reply already contains a dataset keyword (sb/fa/assets/ppm/bdm)
                    # it IS the answer to the clarification — merge so the service gets full context.
                    # _should_break_pending returns True for unrelated new questions (words NOT in
                    # the selection list), so we break only for those.
                    if _should_break_pending(user_query):
                        # User asked a completely new question — forget the old pending query
                        logger.info("🚫 Breaking pending clarification loop — user asked a new question")
                    else:
                        # Use set-based detection (immune to regex alternation-ordering bugs)
                        # Catches: "all", "many", "every", "everything", "each", "entire",
                        # "complete", "full", "give me all", "show everything", etc.
                        if _is_all_datasets_reply(user_query):
                            # User wants ALL datasets — reconstruct as "all: <original question>"
                            user_query = f"all: {pending_original_query}".strip()
                            logger.info(f"🌐 All-datasets clarification reply: '{user_query}'")
                            memory_store[session_id]["is_after_clarification"] = True
                            memory_store[session_id]["is_all_datasets"] = True
                        else:
                            # User replied with a specific dataset keyword
                            user_query = f"{user_query}: {pending_original_query}".strip()
                            logger.info(f"🔁 Reconstructed clarification reply: '{user_query}'")
                            memory_store[session_id]["is_after_clarification"] = True
                            memory_store[session_id]["is_all_datasets"] = False
                    # Always clear after one use — never carry it to a third turn
                    memory_store[session_id]["pending_original_query"] = None

                session_data = memory_store.get(session_id, {})
                # Do not expand before pending_table yes/no handling
                if not session_data.get("pending_table"):
                    user_query = _expand_affirmative_from_history(user_query, session_data)
                query_to_store = user_query

                # ✅ CHECK IF USER IS REPLYING TO QUOTA MENU
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
                    trim_session(memory_store[session_id], MAX_HISTORY)
                    print_memory(session_id)
                    continue

                # ✅ CHECK IF USER IS REPLYING TO QUOTA MENU
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
                    trim_session(memory_store[session_id], MAX_HISTORY)
                    print_memory(session_id)
                    continue  # ← CRITICAL: Skip process_query completely
                
                # ── TWO-STEP TABLE: check if user is replying yes/no to table question
                pending_table = session_data.get("pending_table")

                if pending_table:
                    reply = user_query.strip().lower()
                    logger.info(f"🔍 pending_table check | reply='{reply}' | in_YES_WORDS={reply in YES_WORDS} | in_NO_WORDS={reply in NO_WORDS}")

                    if reply in YES_WORDS:
                        pending_ctx = session_data.get("pending_table_context") or _build_table_context("", user_query)
                        pending_search_context = session_data.get("pending_search_context")
                        table_response = json.dumps({
                            "type": "large_dataset",
                            "context_summary": pending_ctx,
                            "records": pending_table,
                            "search_context": pending_search_context,
                        })
                        memory_store[session_id]["pending_table"] = None
                        memory_store[session_id]["pending_table_context"] = None
                        memory_store[session_id]["pending_search_context"] = None

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
                        trim_session(memory_store[session_id], MAX_HISTORY)
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
                        trim_session(memory_store[session_id], MAX_HISTORY)
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
                    "group_name": group_name,
                    "is_space_booking": is_space_booking,
                    "is_advance_ask_ai": is_advance_ask_ai
                }
                logger.info(f"🆕 Memory initialized for session_id: {session_id}")
            else:
                # Update group_name if it was passed
                if group_name:
                    memory_store[session_id]["group_name"] = group_name
                # Keep flags sticky
                if is_space_booking:
                    memory_store[session_id]["is_space_booking"] = True
                if is_advance_ask_ai:
                    memory_store[session_id]["is_advance_ask_ai"] = True

            messages = build_scoped_messages(
                user_name=user_name,
                current_query=user_query,
                session_data=memory_store[session_id],
                max_previous_turns=MAX_HISTORY,
            )

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
                    is_advance_ask_ai_active = memory_store[session_id].get("is_advance_ask_ai", False)

                    if is_space_booking:
                        logger.info("🚀 Routing query to SpaceBookingService")
                        final_response_text, context_summary, _ = await space_booking_service.handle_space_booking(
                            messages,
                            user_name=user_name,
                            sub_user_name=sub_user_name,
                            session_id=session_id
                        )
                    elif is_advance_ask_ai_active:
                        logger.info("🚀 Routing query to Advance Ask-AI Pipeline")
                        from app.agents.multi_agent_graph import run_agent_pipeline
                        
                        agent_history = []
                        for turn in memory_store[session_id].get("history", []):
                            if turn.get("query"):
                                agent_history.append({"role": "user", "content": turn["query"]})
                            ast = turn.get("context") or turn.get("assistant")
                            if ast:
                                agent_history.append({"role": "assistant", "content": ast})
                        
                        final_state = await run_agent_pipeline(
                            user_query=user_query,
                            conversation_history=agent_history,
                            user_name=user_name,
                            user_id=user_id
                        )
                        
                        final_response_text = final_state.get("formatted_answer") or final_state.get("final_answer") or "No answer produced."
                        context_summary = final_response_text
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
                                is_after_clarification=memory_store[session_id].get("is_after_clarification", False),
                                is_all_datasets=memory_store[session_id].get("is_all_datasets", False),
                            )
                        else:
                            final_response_text, context_summary, _ = await langchain_service.process_query(
                                messages,
                                user_name=user_name,
                                user_id=user_id,
                                session_id=session_id,
                                is_graph=is_graph,
                                is_after_clarification=memory_store[session_id].get("is_after_clarification", False),
                                is_all_datasets=memory_store[session_id].get("is_all_datasets", False),
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
                

            # Convert final_response_text and context_summary to string if they are lists/dicts (defensive parsing)
            final_text_str = ""
            if isinstance(final_response_text, list):
                parts = []
                for item in final_response_text:
                    if isinstance(item, dict) and "text" in item:
                        parts.append(str(item["text"]))
                    else:
                        parts.append(str(item))
                final_text_str = " ".join(parts)
            elif isinstance(final_response_text, dict):
                final_text_str = json.dumps(final_response_text)
            else:
                final_text_str = str(final_response_text or "")

            context_sum_str = ""
            if isinstance(context_summary, list):
                parts = []
                for item in context_summary:
                    if isinstance(item, dict) and "text" in item:
                        parts.append(str(item["text"]))
                    else:
                        parts.append(str(item))
                context_sum_str = " ".join(parts)
            elif isinstance(context_summary, dict):
                context_sum_str = json.dumps(context_summary)
            else:
                context_sum_str = str(context_summary or "")

            final_response_text = final_text_str
            context_summary = context_sum_str

            # ── TWO SEPARATE MEMORIES
            # ── lc_memory → context_summary pairs; only last MAX_HISTORY turns are kept
            # ──             (sent to model). MAX_HISTORY=0 → no prior turns in prompt.
            # ── history   → full transcript (final_response_text); never trimmed by MAX_HISTORY;
            # ──             saved to DB on session end / used when frontend POSTs session.
            memory_store[session_id]["lc_memory"].append(HumanMessage(content=user_query))
            memory_store[session_id]["lc_memory"].append(AIMessage(content=context_summary))
            logger.info(f"🧠 lc_memory updated with context_summary | session={session_id}")

            # ── If model asked clarification (no tool ran) → save original query ──
            # Only set when the response is a genuine clarification question:
            # BOTH a clarification phrase AND a dataset list must be present.
            # This prevents data responses that mention dataset names (e.g. "SB Work Orders")
            # from accidentally re-triggering the pending loop.
            import re as _re
            _resp_lower = final_response_text.lower()
            is_large_dataset_response = (
                final_response_text.strip().startswith('{"type": "large_dataset"')
                or final_response_text.strip().startswith('{"type": "multiple_datasets"')
                or final_response_text.strip().startswith('{"type": "graph"')
            )
            is_table_offer = "would you like" in _resp_lower
            _has_clar_phrase = bool(_re.search(
                r"please clarify|do you mean|could you clarify|which kind of data",
                _resp_lower,
            ))
            _has_dataset_list = bool(_re.search(
                r"assets,\s*ppm|ppm,\s*bdm|bdm,\s*fa|fa,\s*or\s*sb",
                _resp_lower,
            ))
            is_clarification = (
                not is_large_dataset_response
                and not is_table_offer
                and _has_clar_phrase
                and _has_dataset_list
            )
            if is_clarification:
                memory_store[session_id]["pending_original_query"] = query_to_store
                logger.info(f"💾 Saved pending_original_query: '{query_to_store}'")
            # ── Always clear the clarification flags after each processed turn ──
            memory_store[session_id]["is_after_clarification"] = False
            memory_store[session_id]["is_all_datasets"] = False
            # ── Stash pending table data if response ends with table question
            # ── langchain_service stores p_list_for_model on self for this purpose
            pending_table = getattr(langchain_service, "_last_pending_table", None)
            if pending_table:
                memory_store[session_id]["pending_table"] = pending_table
                memory_store[session_id]["pending_table_context"] = _build_table_context(context_summary, query_to_store)
                memory_store[session_id]["pending_search_context"] = getattr(
                    langchain_service, "_last_search_context", None
                )
                langchain_service._last_pending_table = None  # clear after stashing
                langchain_service._last_search_context = None
                logger.info(f"📋 Stashed pending_table | records={len(pending_table)} | context_saved=True")



            memory_store[session_id]["history"].append({
                "query":     query_to_store,
                "assistant": final_response_text,  # full data → DB → frontend display
                "context":   context_summary,         # short summary → title generation only
                "is_audio":  is_audio #flag for rendering
            
            })
            logger.info(f"💾 history updated with full response | session={session_id}")

            trim_session(memory_store[session_id], MAX_HISTORY)

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
                    group_name = session_data.get("group_name"),
                    is_space_booking = session_data.get("is_space_booking", False)
                )
                logger.info(f"✅ Saved on disconnect | session={current_session_id}")
                
            else:
                logger.info(f"⏭️ Skipping disconnect save — frontend already saved | session={current_session_id}")
                frontend_saved_sessions.discard(current_session_id)  # cleanup

        logger.info("🔌 WebSocket client disconnected")
        
