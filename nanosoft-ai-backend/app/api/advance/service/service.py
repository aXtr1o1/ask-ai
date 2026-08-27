import json as _json
import logging
import asyncio
import queue as _queue
import threading

from app.api.advance.pipeline import advance_pipeline
from app.api.advance.Understanding_Agent.agent import classify_query
from app.api.advance.Understanding_Agent.conversation_memory import conversation_memory
from app.api.advance.analysis.agent import analyze_query
from app.api.advance.retrieval.layer import run_retrieval_layer
from app.api.advance.preprocessing.layer import preprocess_records
from app.api.advance.execution_agent.agent.agent import run_execution
from app.api.advance.execution_agent.output.context_builder import build_formatting_context
from app.api.advance.Formatting_agent.agent import format_response

# Change this import path only if user_profile_service.py is located elsewhere.
from app.services.user_profile_service import (
    calculate_credits,
    update_usage_if_exists,
    update_daily_history,
    get_profile_name_by_external_user_id,
)

logger = logging.getLogger("advance.service")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_initial_state(
    query: str,
    session_id: str,
    user_name: str,
    user_id: str,
) -> dict:
    return {
        # Input
        "query": query,
        "session_id": session_id,
        "user_name": user_name,
        "user_id": user_id,

        # Understanding Agent defaults
        "intent": "",
        "query_summary": None,
        "modules": [],
        "response_format": "PLAIN_TEXT",
        "user_specified_format": False,
        "general_response": None,
        "web_search_summary": None,

        # Analysis Agent defaults
        "filter_fields": {},
        "filter_values": {},
        "limit": None,
    }


def _store_conversation_turn(
    session_id: str,
    query: str,
    final_state: dict,
    intent: str,
) -> None:
    try:
        conversation_memory.add_turn(
            session_id=session_id,
            user_query=query,
            query_summary=final_state.get("query_summary") or query,
            intent=intent,
            modules=final_state.get("modules", []),
            filter_fields=final_state.get("filter_fields", {}),
            filter_values=final_state.get("filter_values", {}),
            general_response=final_state.get("general_response"),
        )
    except Exception as exc:
        logger.warning("[service] Memory store failed: %s", exc)


# ── Non-streaming pipeline (LangGraph, kept for health-check / testing) ────────

async def run_advance_pipeline(
    query: str,
    session_id: str,
    user_name: str,
    user_id: str,
) -> dict:
    initial_state = _build_initial_state(
        query,
        session_id,
        user_name,
        user_id,
    )

    final_state = await asyncio.to_thread(
        advance_pipeline.invoke,
        initial_state,
    )

    intent = final_state.get("intent", "general")

    _store_conversation_turn(
        session_id,
        query,
        final_state,
        intent,
    )

    return final_state


# ── Streaming pipeline ─────────────────────────────────────────────────────────

def _run_streaming_pipeline(
    query: str,
    session_id: str,
    user_name: str,
    user_id: str,
    stream_queue: _queue.Queue,
) -> None:
    """
    Runs the active Advance pipeline directly so thought callbacks can
    push SSE events into the queue in real time.

    Token usage is collected from every LLM-backed agent:
        UA + AA + EA + FA = TT

    Credits are calculated once, after the full request has completed.
    """

    try:
        # ── Token usage accumulators ─────────────────────────────────────────

        ua_total_tokens = 0
        aa_total_tokens = 0
        ea_total_tokens = 0
        fa_total_tokens = 0

        # ── Understanding Agent ──────────────────────────────────────────────

        stream_queue.put({
            "status": "running_start",
            "stage": "Understanding Agent",
        })

        understanding = classify_query(
            query=query,
            session_id=session_id,
            thought_callback=lambda chunk: stream_queue.put({
                "status": "running_chunk",
                "word": chunk,
            }),
        )

        stream_queue.put({
            "status": "running_end",
            "stage": "Understanding Agent",
        })

        ua_token_usage = understanding.get("token_usage", {}) or {}

        ua_total_tokens = int(
            ua_token_usage.get("total_tokens", 0) or 0
        )

        intent = understanding.get("intent", "general")
        query_summary = understanding.get("query_summary")
        modules = understanding.get("modules", [])

        filter_fields: dict = {}
        filter_values: dict = {}
        limit = None

        # These remain zero for general/web_search because
        # Analysis and Execution Agents are not executed there.
        aa_total_tokens = 0
        ea_total_tokens = 0

        # ── Analysis + Retrieval + Execution ─────────────────────────────────

        if intent == "db_query":

            # ── Analysis Agent ───────────────────────────────────────────────

            stream_queue.put({
                "status": "running_start",
                "stage": "Analysis Agent",
            })

            analysis = analyze_query(
                query_summary=query_summary or query,
                modules=modules,
                thought_callback=lambda chunk: stream_queue.put({
                    "status": "running_chunk",
                    "word": chunk,
                }),
                last_db_turn=conversation_memory.get_last_db_turn(
                    session_id
                ),
            )

            stream_queue.put({
                "status": "running_end",
                "stage": "Analysis Agent",
            })

            aa_token_usage = analysis.get("token_usage", {}) or {}

            aa_total_tokens = int(
                aa_token_usage.get("total_tokens", 0) or 0
            )

            filter_fields = analysis.get("filter_fields", {})
            filter_values = analysis.get("filter_values", {})
            limit = analysis.get("limit")

            # ── Retrieval Layer ─────────────────────────────────────────────

            stream_queue.put({
                "status": "running_start",
                "stage": "Retrieval Layer",
            })

            for mod in modules:
                stream_queue.put({
                    "status": "running_chunk",
                    "word": f"Fetching {mod} data...",
                })

            retrieved_data = run_retrieval_layer(
                user_name=user_name,
                user_id=user_id,
                modules=modules,
                filter_values=filter_values,
                filter_fields=filter_fields,
                limit=limit,
            )

            stream_queue.put({
                "status": "running_end",
                "stage": "Retrieval Layer",
            })

            # ── Preprocessing Layer ─────────────────────────────────────────

            stream_queue.put({
                "status": "running_start",
                "stage": "Preprocessing Layer",
            })

            preprocessed_data = preprocess_records(retrieved_data)

            stream_queue.put({
                "status": "running_end",
                "stage": "Preprocessing Layer",
            })

            # ── Execution Agent ─────────────────────────────────────────────

            stream_queue.put({
                "status": "running_start",
                "stage": "Execution Agent",
            })

            response_format = understanding.get(
                "response_format",
                "PLAIN_TEXT",
            )

            user_specified = understanding.get(
                "user_specified_format",
                False,
            )

            execution_result = run_execution(
                question=query_summary or query,
                filter_fields=filter_fields,
                modules=modules,
                filtered_records=preprocessed_data,
                thought_callback=lambda chunk: stream_queue.put({
                    "status": "running_chunk",
                    "word": chunk,
                }),
                response_format=response_format,
                user_specified=user_specified,
            )

            ea_token_usage = execution_result.get(
                "token_usage",
                {},
            ) or {}

            ea_total_tokens = int(
                ea_token_usage.get("total_tokens", 0) or 0
            )

            formatting_context = build_formatting_context(
                execution_result=execution_result,
                suggested_format=response_format,
                user_specified=user_specified,
            )

            stream_queue.put({
                "status": "running_end",
                "stage": "Execution Agent",
            })

        else:
            # No Analysis / Retrieval / Execution for general or web_search.
            execution_result = {}
            formatting_context = {}

            if intent == "web_search":
                web_summary = (
                    understanding.get("web_search_summary") or ""
                )

                stream_queue.put({
                    "status": "running_start",
                    "stage": "Formatting Agent",
                })

                formatting_context = {
                    "response_format": "WEB_SEARCH",
                    "planned_steps": [
                        {
                            "step": "web_search",
                            "description": (
                                "Live web search results retrieved by "
                                "the Understanding Agent"
                            ),
                        }
                    ],
                    "shape_descriptor": {
                        "shape": "web_search_result",
                        "reason": "External web search result",
                    },
                    "final_answer": web_summary,
                    "dashboard": [],
                }

        # ── Formatting Agent ─────────────────────────────────────────────────

        # IMPORTANT:
        # The original service was invoking FA once inside db_query and then
        # again below. We now call it exactly once for every intent.

        if intent == "general":
            # General queries still go through FA so their tokens are counted
            # and their response follows the same accounting model.
            formatting_context = {
                "response_format": "PLAIN_TEXT",
                "planned_steps": [],
                "shape_descriptor": {
                    "shape": "general_response",
                    "reason": "General conversational request",
                },
                "final_answer": understanding.get(
                    "general_response"
                ),
                "dashboard": [],
            }

        formatted_result = format_response(
            formatting_context=formatting_context,
            query_summary=query_summary or query,
            thought_callback=lambda chunk: stream_queue.put({
                "status": "running_chunk",
                "word": chunk,
            }),
        )

        fa_token_usage = formatted_result.get(
            "token_usage",
            {},
        ) or {}

        fa_total_tokens = int(
            fa_token_usage.get("total_tokens", 0) or 0
        )

        stream_queue.put({
            "status": "running_end",
            "stage": "Formatting Agent",
        })

        # ── Final token accounting ───────────────────────────────────────────

        total_tokens = (
            ua_total_tokens
            + aa_total_tokens
            + ea_total_tokens
            + fa_total_tokens
        )

        credits_delta = calculate_credits(total_tokens)

        logger.info(
            "[service] 📊 TOKEN USAGE | "
            "UA=%s AA=%s EA=%s FA=%s TT=%s",
            ua_total_tokens,
            aa_total_tokens,
            ea_total_tokens,
            fa_total_tokens,
            total_tokens,
        )

        logger.info(
            "[service] 💳 CREDIT USAGE | "
            "tokens=%s | credits=%s",
            total_tokens,
            credits_delta,
        )

        # ── Persist usage ────────────────────────────────────────────────────

        # Keep these at zero here because this Advance service does not
        # currently receive the audio/graph counters that the older path had.
        graph_delta = 0
        audio_seconds_effective = 0

        # The Advance/retrieval layer currently carries the external user ID
        # in `user_name` (for example: external_user_id="poc"), while
        # user_profile.name contains the display/profile name (for example:
        # name="vishal"). Resolve the profile name before updating billing.
        profile_name = get_profile_name_by_external_user_id(user_name)

        if profile_name:
            try:
                update_usage_if_exists(
                    name=profile_name,
                    tokens_used_delta=total_tokens,
                    request_delta=1,
                    graph_delta=graph_delta,
                    credits_delta=credits_delta,
                    audio_seconds_delta=audio_seconds_effective,
                )
            except Exception as exc:
                logger.warning(
                    "[service] update_usage_if_exists failed: %s",
                    str(exc)[:200],
                )

            try:
                update_daily_history(
                    external_user_id=user_name,
                    name=profile_name,
                    credits_delta=credits_delta,
                    audio_seconds_delta=audio_seconds_effective,
                    graph_delta=graph_delta,
                    request_delta=1,
                    tokens_delta=total_tokens,
                )
            except Exception as exc:
                logger.warning(
                    "[service] update_daily_history failed: %s",
                    str(exc)[:200],
                )
        else:
            logger.warning(
                "[service] Billing profile not found | external_user_id=%s",
                user_name,
            )

        # ── Conversation memory ──────────────────────────────────────────────

        _store_conversation_turn(
            session_id=session_id,
            query=query,
            final_state={
                "query_summary": query_summary,
                "modules": modules,
                "intent": intent,
                "filter_fields": filter_fields,
                "filter_values": filter_values,
                "general_response": understanding.get(
                    "general_response"
                ),
            },
            intent=intent,
        )

        # ── Complete — send only what the frontend renders ───────────────────

        if intent == "db_query":
            result_payload = {
                "formatted_result": formatted_result,
            }

        elif intent == "web_search":
            result_payload = {
                "formatted_result": formatted_result,
            }

        else:
            result_payload = {
                "general_response": (
                    formatted_result.get("explanation")
                    or understanding.get("general_response")
                ),
            }

        stream_queue.put({
            "status": "complete",
            "result": result_payload,
        })

    except Exception as exc:
        logger.error(
            "[service] Streaming pipeline error: %s",
            exc,
            exc_info=True,
        )

        stream_queue.put({
            "status": "error",
            "message": str(exc),
        })

    finally:
        # Always terminate the SSE stream.
        stream_queue.put(None)

    

# ── SSE generator ───────────────────────────────────────────────────────────────

async def stream_advance_pipeline(
    query: str,
    session_id: str,
    user_name: str,
    user_id: str,
):
    """
    Async generator that yields SSE-formatted strings.

    The heavy pipeline work runs in a daemon thread so the event loop
    stays free.
    """

    stream_queue: _queue.Queue = _queue.Queue()
    loop = asyncio.get_event_loop()

    thread = threading.Thread(
        target=_run_streaming_pipeline,
        args=(
            query,
            session_id,
            user_name,
            user_id,
            stream_queue,
        ),
        daemon=True,
    )

    thread.start()

    while True:
        try:
            item = await loop.run_in_executor(
                None,
                lambda: stream_queue.get(timeout=120),
            )

        except _queue.Empty:
            logger.warning(
                "[service] Stream queue timed out — "
                "pipeline thread did not finish in time."
            )

            error_payload = {
                "status": "error",
                "message": "Pipeline timeout — please try again.",
            }

            yield f"data: {_json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"
            break

        if item is None:
            yield "data: [DONE]\n\n"
            break

        yield f"data: {_json.dumps(item)}\n\n"