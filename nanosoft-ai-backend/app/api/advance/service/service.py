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

logger = logging.getLogger("advance.service")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_initial_state(query: str, session_id: str, user_name: str, user_id: str) -> dict:
    return {
        # Input
        "query":                 query,
        "session_id":            session_id,
        "user_name":             user_name,
        "user_id":               user_id,
        # Understanding Agent defaults
        "intent":                "",
        "query_summary":         None,
        "modules":               [],
        "response_format":       "PLAIN_TEXT",
        "user_specified_format": False,
        "general_response":      None,
        "web_search_summary":    None,
        # Analysis Agent defaults
        "filter_fields":         {},
        "filter_values":         {},
        "limit":                 None,
    }


def _store_conversation_turn(
    session_id:  str,
    query:       str,
    final_state: dict,
    intent:      str,
) -> None:
    try:
        conversation_memory.add_turn(
            session_id       = session_id,
            user_query       = query,
            query_summary    = final_state.get("query_summary") or query,
            intent           = intent,
            modules          = final_state.get("modules", []),
            filter_fields    = final_state.get("filter_fields", {}),
            filter_values    = final_state.get("filter_values", {}),
            general_response = final_state.get("general_response"),
        )
    except Exception as exc:
        logger.warning("[service] Memory store failed: %s", exc)


# ── Non-streaming pipeline (LangGraph, kept for health-check / testing) ────────

async def run_advance_pipeline(query: str, session_id: str, user_name: str, user_id: str) -> dict:
    initial_state = _build_initial_state(query, session_id, user_name, user_id)
    final_state = await asyncio.to_thread(advance_pipeline.invoke, initial_state)
    intent = final_state.get("intent", "general")
    _store_conversation_turn(session_id, query, final_state, intent)
    return final_state


# ── Streaming pipeline ─────────────────────────────────────────────────────────

def _run_streaming_pipeline(query: str, session_id: str, user_name: str, user_id: str, stream_queue: _queue.Queue) -> None:
    """
    Runs both agents directly (no LangGraph) so thought_callback can push
    SSE events into the queue in real-time.
    """
    try:
        # ── Understanding Agent ───────────────────────────────────────────────
        stream_queue.put({"status": "running_start", "stage": "Understanding Agent"})

        understanding = classify_query(
            query            = query,
            session_id       = session_id,
            thought_callback = lambda chunk: stream_queue.put({"status": "running_chunk", "word": chunk}),
        )

        stream_queue.put({"status": "running_end", "stage": "Understanding Agent"})

        intent        = understanding.get("intent", "general")
        query_summary = understanding.get("query_summary")
        modules       = understanding.get("modules", [])
        filter_fields: dict = {}
        filter_values: dict = {}

        # ── Analysis Agent (db_query intent only) ─────────────────────────────
        if intent == "db_query":
            stream_queue.put({"status": "running_start", "stage": "Analysis Agent"})

            analysis = analyze_query(
                query_summary    = query_summary or query,
                modules          = modules,
                thought_callback = lambda chunk: stream_queue.put({"status": "running_chunk", "word": chunk}),
                last_db_turn     = conversation_memory.get_last_db_turn(session_id),
            )

            stream_queue.put({"status": "running_end", "stage": "Analysis Agent"})

            filter_fields = analysis.get("filter_fields", {})
            filter_values = analysis.get("filter_values", {})
            limit         = analysis.get("limit")
            
            # ── Retrieval Layer ───────────────────────────────────────────────────────
            stream_queue.put({"status": "running_start", "stage": "Retrieval Layer"})
            
            retrieved_data = run_retrieval_layer(
                user_name=user_name,
                user_id=user_id,
                modules=modules,
                filter_values=filter_values,
                filter_fields=filter_fields,
                limit=limit
            )
            
            stream_queue.put({"status": "running_end", "stage": "Retrieval Layer"})
            
            # ── Preprocessing Layer ───────────────────────────────────────────────────
            stream_queue.put({"status": "running_start", "stage": "Preprocessing Layer"})
            preprocessed_data = preprocess_records(retrieved_data)
            stream_queue.put({"status": "running_end", "stage": "Preprocessing Layer"})
            
            # TODO: Future execution layer will use preprocessed_data

        # ── Store turn in conversation memory ─────────────────────────────────
        _store_conversation_turn(
            session_id  = session_id,
            query       = query,
            final_state = {
                "query_summary":    query_summary,
                "modules":          modules,
                "intent":           intent,
                "filter_fields":    filter_fields,
                "filter_values":    filter_values,
                "general_response": understanding.get("general_response"),
            },
            intent = intent,
        )

        # ── Complete ──────────────────────────────────────────────────────────
        stream_queue.put({
            "status": "complete",
            "result": {
                "intent":             intent,
                "modules":            modules,
                "query_summary":      query_summary,
                "general_response":   understanding.get("general_response"),
                "web_search_summary": understanding.get("web_search_summary"),
                "filter_fields":      filter_fields,
                "filter_values":      filter_values,
            },
        })

    except Exception as exc:
        logger.error("[service] Streaming pipeline error: %s", exc, exc_info=True)
        stream_queue.put({"status": "error", "message": str(exc)})

    finally:
        stream_queue.put(None)  # sentinel — always emitted so the generator always terminates


async def stream_advance_pipeline(query: str, session_id: str, user_name: str, user_id: str):
    """
    Async generator that yields SSE-formatted strings.
    The heavy pipeline work runs in a daemon thread so the event loop stays free.
    """
    stream_queue: _queue.Queue = _queue.Queue()
    loop = asyncio.get_event_loop()

    thread = threading.Thread(
        target = _run_streaming_pipeline,
        args   = (query, session_id, user_name, user_id, stream_queue),
        daemon = True,
    )
    thread.start()

    while True:
        # Block in a thread-pool worker (non-blocking for the event loop)
        item = await loop.run_in_executor(None, lambda: stream_queue.get(timeout=60))

        if item is None:              # sentinel — pipeline finished
            yield "data: [DONE]\n\n"
            break

        yield f"data: {_json.dumps(item)}\n\n"