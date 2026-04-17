"""
app/handlers/ws_chat_handler.py
────────────────────────────────
Full WebSocket chat handler — all branching logic lives here.

Branches handled:
    BRANCH 1 → Pending transcription confirmation (audio yes/no reply)
    BRANCH 2 → New audio message
    BRANCH 3 → Normal text message

All branches converge at PROCESS QUERY which calls langchain_service.
"""

import asyncio
import base64
import json
import logging
import re as _re

from fastapi import WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage, AIMessage

from app.config import settings
from app.state import memory_store, MAX_HISTORY, frontend_saved_sessions
from app.constants import YES_WORDS, NO_WORDS, MAX_AUDIO_BYTES
from app.prompts.system_prompt import get_system_prompt
from app.services.ai.langchain_service import langchain_service
from app.services.quota.quota_service import quota_fallback_service
from app.user.profile_service import (
    update_usage_if_exists,
    get_credits_remaining,
    consume_audio_seconds_if_available,
    get_graph_count_and_limit,
    update_daily_history,
)
from app.user.audio_service import convert_audio_to_text, get_audio_duration_seconds
from app.utils.ws_utils import _init_session, _save_session_safe, _send
from app.utils.query_utils import _build_table_context
from app.utils.debug_utils import print_memory

logger = logging.getLogger("handlers.ws_chat_handler")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(ch)


async def ws_chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 [WS] WebSocket accepted")

    current_session_id = None

    try:
        while True:
            # ── Receive next message (with inactivity timeout) ─────────────────
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=settings.WS_SESSION_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.info(
                    "⏰ [WS] WebSocket timed out after %ds inactivity",
                    settings.WS_SESSION_TIMEOUT,
                )
                await websocket.close()
                if current_session_id:
                    await _save_session_safe(current_session_id)
                break

            # ── Keep-alive ping ────────────────────────────────────────────────
            if raw.strip() == "ping":
                await websocket.send_text("pong")
                continue

            # ── Parse payload ──────────────────────────────────────────────────
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "Invalid JSON"}))
                continue

            # ── Extract common fields ──────────────────────────────────────────
            user_name     = str(data.get("userName",    ""))
            sub_user_name = str(data.get("subUserName", ""))
            session_id    = str(data.get("sessionId",   ""))
            is_audio      = bool(data.get("isAudio",    False))
            is_graph      = bool(data.get("isGraph",    False))

            try:
                user_id = int(data.get("userId")) if data.get("userId") is not None else None
            except (ValueError, TypeError):
                user_id = None

            try:
                audio_seconds_request = int(float(
                    data.get("audioSeconds") or data.get("audio_seconds") or 0
                ))
            except Exception:
                audio_seconds_request = 0

            logger.info(
                "[WS] Frame | user=%s | sub=%s | session=%s | is_audio=%s | is_graph=%s",
                user_name, sub_user_name, session_id, is_audio, is_graph,
            )

            if not session_id:
                await websocket.send_text(json.dumps({"error": "Missing sessionId"}))
                continue

            current_session_id = session_id
            _init_session(session_id, user_name, sub_user_name)

            # ── Shared state for this frame ────────────────────────────────────
            audio_base64            = None
            query_to_store          = None
            audio_seconds_effective = 0
            user_query              = ""

            session_data = memory_store[session_id]

            # ==================================================================
            # BRANCH 1: Pending transcription confirmation (audio yes/no)
            # ==================================================================
            pending_transcription = session_data.get("pending_transcription")

            if pending_transcription:
                reply_text = data.get("query", "").strip().lower()

                if is_audio:
                    try:
                        audio_bytes = await asyncio.wait_for(
                            websocket.receive_bytes(),
                            timeout=settings.WS_SESSION_TIMEOUT,
                        )
                        if len(audio_bytes) > MAX_AUDIO_BYTES:
                            await _send(websocket, session_id,
                                        "Voice query is too long. Please keep it brief and try again.")
                            continue

                        computed = get_audio_duration_seconds(audio_bytes)
                        audio_seconds_effective = (
                            computed if (computed and computed > 0) else audio_seconds_request
                        )

                        if audio_seconds_effective > 0:
                            consumed = await asyncio.to_thread(
                                consume_audio_seconds_if_available,
                                name=sub_user_name,
                                audio_seconds_delta=audio_seconds_effective,
                            )
                            if consumed is False:
                                await _send(websocket, session_id,
                                            "Audio credits exhausted. Please recharge/upgrade your plan to continue.")
                                continue

                        transcribed = await convert_audio_to_text(audio_bytes)
                        raw_reply   = transcribed["transcription"].strip().lower()
                        reply_text  = _re.sub(r"[^\w\s]", "", raw_reply).strip()
                        logger.info("[WS] Audio confirmation reply: '%s'", reply_text)

                    except Exception as e:
                        logger.error("[WS] Confirmation audio failed | error=%s", e)
                        reply_text = ""

                session_data["pending_transcription"] = None

                reply_words = set(reply_text.split())
                is_yes = reply_text in YES_WORDS or bool(reply_words & YES_WORDS)
                is_no  = reply_text in NO_WORDS  or bool(reply_words & NO_WORDS)

                if is_yes:
                    user_query     = pending_transcription
                    query_to_store = reply_text
                    logger.info("[WS] Confirmed → running: '%s'", user_query)

                elif is_no:
                    msg = "No problem! Could you please tell me what you meant? I'll try again."
                    await _send(websocket, session_id, msg)
                    session_data["history"].append({
                        "query": pending_transcription, "assistant": msg,
                        "context": msg, "is_audio": is_audio,
                    })
                    continue

                else:
                    user_query     = data.get("query", "").strip() if not is_audio else reply_text
                    query_to_store = user_query
                    logger.info("[WS] Correction received → running: '%s'", user_query)

            # ==================================================================
            # BRANCH 2: Audio input (new audio message)
            # ==================================================================
            elif is_audio:
                logger.info("[WS] Audio path | user=%s | session=%s", sub_user_name, session_id)

                try:
                    audio_bytes = await asyncio.wait_for(
                        websocket.receive_bytes(),
                        timeout=settings.WS_SESSION_TIMEOUT,
                    )
                    logger.info("[WS] Audio bytes received | size=%d", len(audio_bytes))

                    if len(audio_bytes) > MAX_AUDIO_BYTES:
                        await _send(websocket, session_id,
                                    "Voice query is too long. Please keep it brief and try again.")
                        continue

                    # ── Check pending_table yes/no via audio ───────────────────
                    pending_table_audio = session_data.get("pending_table")
                    if pending_table_audio:
                        transcribed_reply = await convert_audio_to_text(audio_bytes)
                        raw_reply_table   = transcribed_reply["transcription"].strip().lower()
                        reply_table       = _re.sub(r"[^\w\s]", "", raw_reply_table).strip()

                        if reply_table in YES_WORDS:
                            pending_ctx    = session_data.get("pending_table_context") or "Here is the detailed table you requested."
                            table_response = json.dumps({"context_summary": pending_ctx, "records": pending_table_audio})
                            session_data["pending_table"]         = None
                            session_data["pending_table_context"] = None
                            await _send(websocket, session_id, table_response)
                            session_data["lc_memory"].append(HumanMessage(content=reply_table))
                            session_data["lc_memory"].append(AIMessage(content="Table displayed."))
                            session_data["history"].append({
                                "query": reply_table, "assistant": table_response,
                                "context": "Table displayed on user audio request.", "is_audio": True,
                            })
                            print_memory(session_id)
                            continue

                        elif reply_table in NO_WORDS:
                            session_data["pending_table"]         = None
                            session_data["pending_table_context"] = None
                            no_msg = "No problem! Let me know if you have any other questions."
                            await _send(websocket, session_id, no_msg)
                            session_data["lc_memory"].append(HumanMessage(content=reply_table))
                            session_data["lc_memory"].append(AIMessage(content=no_msg))
                            session_data["history"].append({
                                "query": reply_table, "assistant": no_msg,
                                "context": no_msg, "is_audio": True,
                            })
                            print_memory(session_id)
                            continue
                        else:
                            session_data["pending_table"]         = None
                            session_data["pending_table_context"] = None

                    # ── Audio credits check + consume ──────────────────────────
                    computed = get_audio_duration_seconds(audio_bytes)
                    audio_seconds_effective = (
                        computed if (computed and computed > 0) else audio_seconds_request
                    )

                    if audio_seconds_effective > 0:
                        consumed = await asyncio.to_thread(
                            consume_audio_seconds_if_available,
                            name=sub_user_name,
                            audio_seconds_delta=audio_seconds_effective,
                        )
                        if consumed is False:
                            msg = "Audio credits exhausted. Please recharge/upgrade your plan to continue."
                            await _send(websocket, session_id, msg)
                            session_data["history"].append({
                                "query": "", "assistant": msg, "context": msg, "is_audio": True,
                            })
                            continue

                        try:
                            await asyncio.to_thread(
                                update_daily_history,
                                external_user_id    = user_name,
                                name                = sub_user_name,
                                credits_delta       = 0,
                                audio_seconds_delta = int(audio_seconds_effective),
                                graph_delta         = 0,
                                request_delta       = 0,
                            )
                        except Exception as e:
                            logger.warning("[WS] update_daily_history (audio immediate) failed: %s", str(e)[:200])

                    audio_base64   = "data:audio/ogg;base64," + base64.b64encode(audio_bytes).decode("utf-8")
                    query_to_store = audio_base64

                    # ── Transcribe ─────────────────────────────────────────────
                    try:
                        transcription_result = await convert_audio_to_text(audio_bytes)
                    except Exception as e:
                        logger.error("[WS] Transcription failed | error=%s", e)
                        await _send(websocket, session_id,
                                    "Sorry, voice input is temporarily unavailable. Please type your message instead.")
                        continue

                    user_query             = transcription_result["transcription"]
                    needs_clarification    = transcription_result["needs_clarification"]
                    clarification_question = transcription_result["clarification_question"]

                    logger.info(
                        "[WS] Transcribed: '%s' | needs_clarification=%s",
                        user_query, needs_clarification,
                    )

                    if needs_clarification:
                        await websocket.send_text(json.dumps({
                            "session_id":          session_id,
                            "response":            clarification_question,
                            "needs_clarification": True,
                        }))
                        await websocket.send_text("[DONE]")
                        session_data["pending_transcription"] = user_query
                        session_data["history"].append({
                            "query":     query_to_store,
                            "assistant": clarification_question,
                            "context":   f"Confirmation asked for: {user_query}",
                            "is_audio":  True,
                        })
                        continue

                except asyncio.TimeoutError:
                    logger.warning("[WS] Timed out waiting for audio bytes")
                    await websocket.send_text(json.dumps({"error": "Timed out waiting for audio data"}))
                    continue
                except Exception as e:
                    logger.error("[WS] Audio processing failed | error=%s", e, exc_info=True)
                    await websocket.send_text(json.dumps({"error": "Audio processing failed. Please try again."}))
                    continue

            # ==================================================================
            # BRANCH 3: Normal text input
            # ==================================================================
            else:
                user_query     = data.get("query", "").strip()
                query_to_store = user_query

                if not user_query:
                    await websocket.send_text(json.dumps({"error": "Empty query"}))
                    continue

                logger.info(
                    "[WS] Text message | user=%s | session=%s | query=%s",
                    user_name, session_id, user_query,
                )

                # Reconstruct combined query if user is replying to an AI clarification
                pending_original = session_data.get("pending_original_query")
                if pending_original:
                    user_query = f"{pending_original} {user_query}".strip()
                    session_data["pending_original_query"] = None
                    logger.info("[WS] Reconstructed query: '%s'", user_query)

                # ── Quota fallback: user choosing which service to query ────────
                if session_data.get("waiting_for_table_choice"):
                    session_data["waiting_for_table_choice"] = False
                    final_response_text, context_summary = quota_fallback_service.handle_user_table_choice(
                        user_reply = user_query,
                        user_name  = user_name,
                        user_id    = user_id,
                    )
                    if final_response_text is None:
                        error_msg = "I couldn't determine which table you want. Please reply with the service name."
                        await _send(websocket, session_id, error_msg)
                        session_data["history"].append({
                            "query": query_to_store, "assistant": error_msg,
                            "context": error_msg, "is_audio": False,
                        })
                        continue

                    await _send(websocket, session_id, final_response_text)
                    session_data["lc_memory"].append(HumanMessage(content=user_query))
                    session_data["lc_memory"].append(AIMessage(content=context_summary))
                    session_data["history"].append({
                        "query": query_to_store, "assistant": final_response_text,
                        "context": context_summary, "is_audio": False,
                    })
                    print_memory(session_id)
                    continue

                # ── Two-step table: user replying yes/no ──────────────────────
                pending_table = session_data.get("pending_table")
                if pending_table:
                    reply = user_query.strip().lower()

                    if reply in YES_WORDS:
                        pending_ctx    = session_data.get("pending_table_context") or "Here is the detailed table you requested."
                        table_response = json.dumps({"context_summary": pending_ctx, "records": pending_table})
                        session_data["pending_table"]         = None
                        session_data["pending_table_context"] = None
                        await _send(websocket, session_id, table_response)
                        session_data["lc_memory"].append(HumanMessage(content=user_query))
                        session_data["lc_memory"].append(AIMessage(content="Table displayed."))
                        session_data["history"].append({
                            "query": query_to_store, "assistant": table_response,
                            "context": "Table displayed on user request.", "is_audio": False,
                        })
                        print_memory(session_id)
                        continue

                    elif reply in NO_WORDS:
                        session_data["pending_table"]         = None
                        session_data["pending_table_context"] = None
                        no_msg = "No problem! Let me know if you have any other questions."
                        await _send(websocket, session_id, no_msg)
                        session_data["lc_memory"].append(HumanMessage(content=user_query))
                        session_data["lc_memory"].append(AIMessage(content=no_msg))
                        session_data["history"].append({
                            "query": query_to_store, "assistant": no_msg,
                            "context": no_msg, "is_audio": False,
                        })
                        print_memory(session_id)
                        continue
                    else:
                        session_data["pending_table"]         = None
                        session_data["pending_table_context"] = None

            # ==================================================================
            # PROCESS QUERY — all branches converge here
            # ==================================================================
            logger.info("[WS] Processing query | session=%s | query='%s'", session_id, user_query)

            lc_memory = list(session_data["lc_memory"])
            messages  = [get_system_prompt(client_name=user_name, user_id=user_id)] + lc_memory
            messages.append(HumanMessage(content=user_query))

            final_response_text = ""
            context_summary     = ""
            graph_delta         = 0

            try:
                # ── Credits gate ───────────────────────────────────────────────
                try:
                    credits_remaining = await asyncio.to_thread(get_credits_remaining, sub_user_name)
                except Exception as e:
                    logger.warning("[WS] Credits check failed (continuing) | error=%s", str(e)[:200])
                    credits_remaining = None

                if credits_remaining == 0:
                    final_response_text = "You're out of credits. Please recharge/upgrade your plan to continue."
                    context_summary     = final_response_text

                else:
                    # ── Graph gate ─────────────────────────────────────────────
                    graph_info = None
                    if is_graph:
                        try:
                            graph_info = await asyncio.to_thread(get_graph_count_and_limit, sub_user_name)
                        except Exception as e:
                            logger.warning("[WS] Graph check failed (continuing) | error=%s", str(e)[:200])

                    if is_graph and graph_info is not None:
                        graph_count, graph_limit = graph_info
                        if graph_count >= graph_limit:
                            final_response_text = "Your graph credits are over. Please recharge/upgrade your plan to continue."
                            context_summary     = final_response_text
                            logger.info(
                                "[WS] Graph credits exhausted | user=%s | count=%d | limit=%d",
                                sub_user_name, graph_count, graph_limit,
                            )
                        else:
                            final_response_text, context_summary, _ = await langchain_service.process_query(
                                messages, user_name=user_name, user_id=user_id,
                                session_id=session_id, is_graph=is_graph,
                            )
                    else:
                        final_response_text, context_summary, _ = await langchain_service.process_query(
                            messages, user_name=user_name, user_id=user_id,
                            session_id=session_id, is_graph=is_graph,
                        )

                    logger.info(
                        "[WS] Response generated | session=%s | length=%d",
                        session_id, len(final_response_text or ""),
                    )

            except Exception as e:
                logger.error(
                    "[WS] Query processing error | session=%s | error=%s",
                    session_id, e, exc_info=True,
                )

                if quota_fallback_service.is_quota_error(e):
                    logger.warning("[WS] Quota error — showing fallback menu")
                    quota_message = quota_fallback_service.get_quota_exceeded_message(client_name=user_name)
                    session_data["waiting_for_table_choice"] = True
                    final_response_text = quota_message
                    context_summary     = "AI quota exceeded — waiting for user table choice"

                elif "timed out" in str(e).lower():
                    final_response_text = "The request is taking too long. Please try again."
                    context_summary     = final_response_text

                else:
                    final_response_text = "Sorry, something went wrong. Please try again."
                    context_summary     = final_response_text

            # ── Send response ──────────────────────────────────────────────────
            await _send(websocket, session_id, final_response_text)

            # ── Update usage counters ──────────────────────────────────────────
            tokens_delta = int(getattr(langchain_service, "_total_tokens", 0) or 0)

            if is_graph and isinstance(final_response_text, str):
                try:
                    payload = json.loads(final_response_text)
                    if isinstance(payload, dict) and payload.get("type") == "graph":
                        graph_delta = 1
                except Exception:
                    pass

            try:
                await asyncio.to_thread(
                    update_usage_if_exists,
                    name                = sub_user_name,
                    tokens_used_delta   = tokens_delta,
                    request_delta       = 1,
                    graph_delta         = graph_delta,
                    credits_per_request = 1,
                    audio_seconds_delta = audio_seconds_effective,
                )
            except Exception as e:
                logger.warning("[WS] user_profile update failed | error=%s", str(e)[:200])

            try:
                await asyncio.to_thread(
                    update_daily_history,
                    external_user_id    = user_name,
                    name                = sub_user_name,
                    credits_delta       = 1,
                    audio_seconds_delta = audio_seconds_effective,
                    graph_delta         = graph_delta,
                    request_delta       = 1,
                    tokens_delta        = tokens_delta,
                )
            except Exception as e:
                logger.warning("[WS] update_daily_history failed | error=%s", str(e)[:200])

            # ── Update lc_memory ───────────────────────────────────────────────
            session_data["lc_memory"].append(HumanMessage(content=user_query))
            session_data["lc_memory"].append(AIMessage(content=context_summary))

            # ── Detect AI clarification ────────────────────────────────────────
            clarification_keywords = [
                "do you mean", "please clarify", "fa complaints or bdm",
                r"ppm.*or.*sb", "could you clarify",
            ]
            is_clarification = any(
                _re.search(kw, final_response_text.lower()) for kw in clarification_keywords
            )
            if is_clarification:
                session_data["pending_original_query"] = query_to_store

            # ── Stash pending table for yes/no flow ────────────────────────────
            pending_table_new = getattr(langchain_service, "_last_pending_table", None)
            if pending_table_new:
                session_data["pending_table"]         = pending_table_new
                session_data["pending_table_context"] = _build_table_context(
                    context_summary, query_to_store
                )
                langchain_service._last_pending_table = None

            # ── Save to history ────────────────────────────────────────────────
            session_data["history"].append({
                "query":     query_to_store,
                "assistant": final_response_text,
                "context":   context_summary,
                "is_audio":  is_audio,
            })

            # ── Trim memory if over MAX_HISTORY ────────────────────────────────
            if len(session_data["history"]) > MAX_HISTORY:
                session_data["history"]   = session_data["history"][-MAX_HISTORY:]
                session_data["lc_memory"] = session_data["lc_memory"][-(MAX_HISTORY * 2):]

            print_memory(session_id)

    except WebSocketDisconnect:
        logger.info("🔌 [WS] WebSocket disconnected | session=%s", current_session_id)
        if current_session_id:
            if current_session_id not in frontend_saved_sessions:
                await _save_session_safe(current_session_id)
            else:
                logger.info(
                    "[WS] Skipping disconnect save — frontend already saved | session=%s",
                    current_session_id,
                )
                frontend_saved_sessions.discard(current_session_id)

    except Exception as e:
        logger.error(
            "❌ [WS] Unhandled error | session=%s | error=%s",
            current_session_id, e, exc_info=True,
        )
        try:
            await websocket.close()
        except Exception:
            pass
        if current_session_id:
            await _save_session_safe(current_session_id)