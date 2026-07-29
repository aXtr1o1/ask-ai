# stream_handler.py
"""
Stream Handler

Orchestrates the full query pipeline and streams agent thought tokens to the
frontend in real time via Server-Sent Events (ndjson).

REAL STREAMING ARCHITECTURE
─────────────────────────────────────────────────────────────────────────────
Each agent now uses google.genai generate_content_stream internally.

As the LLM generates thought tokens, each token is forwarded immediately
to the asyncio queue via loop.call_soon_threadsafe — the frontend receives
words the moment they arrive from the API, NOT after the agent finishes.

There are NO artificial time.sleep delays. The natural pace of the LLM
stream drives the word-by-word animation on the frontend.

SSE event types sent to the frontend:
  { status: "running_start", stage: "<agent name>" }
  { status: "running_chunk", stage: "<agent name>", word: "<word> " }
  { status: "running_end",   stage: "<agent name>" }
  { status: "complete",      result: { ... } }
"""
import json
import asyncio
import time
import logging
from typing import AsyncGenerator

from app.api.advance.Understanding_Agent.agent import classify_query
from app.api.advance.analysis.agent import analyze_query
from app.api.advance.Understanding_Agent.conversation_memory import conversation_memory
from app.api.advance.retrieval.retrieval import get_filtered_records
from app.api.advance.execution.agent import run_execution
from app.api.advance.Formatting_agent.agent import format_pipeline_response

logger = logging.getLogger("advance.stream_handler")

_DATA_HEAVY_FORMATS = {"TABLE", "GRAPH"}


async def run_query_stream(
    query:      str,
    session_id: str = "default",
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields ndjson lines.

    Each line is a JSON object with a `status` field:
      running_start / running_chunk / running_end / complete
    """
    loop = asyncio.get_running_loop()
    q:   asyncio.Queue = asyncio.Queue()

    # ── Callback factory ──────────────────────────────────────────────────────
    def _make_thought_cb(stage: str):
        """
        Returns (thought_cb, done_cb) for one agent stage.

        thought_cb(text: str)  — called by stream_with_thoughts with each
                                  thought chunk as it arrives from the Gemini API.
        done_cb()              — call after the agent returns to close the stage.
        """
        started = [False]

        def thought_cb(text: str):
            if not text or not text.strip():
                return
            if not started[0]:
                loop.call_soon_threadsafe(q.put_nowait, {
                    "type":  "thinking_start",
                    "stage": stage,
                })
                logger.info("[Stream] %-22s thinking started", stage)
                started[0] = True
            # Split into words so the frontend receives one word at a time.
            # No sleep — timing is driven by the LLM generation pace.
            for word in text.split():
                loop.call_soon_threadsafe(q.put_nowait, {
                    "type":  "thinking_chunk",
                    "stage": stage,
                    "word":  word + " ",
                })

        def done_cb():
            if started[0]:
                loop.call_soon_threadsafe(q.put_nowait, {
                    "type":  "thinking_end",
                    "stage": stage,
                })
                logger.info("[Stream] %-22s thinking done", stage)

        return thought_cb, done_cb

    # ── Worker (runs in a thread) ─────────────────────────────────────────────
    def _worker():
        try:
            # ── STEP 1: UNDERSTANDING ─────────────────────────────────────────
            u_cb, u_done = _make_thought_cb("Understanding Agent")
            understanding = classify_query(query, session_id, thought_callback=u_cb)
            u_done()

            intent                = understanding.get("intent")
            summary               = understanding.get("query_summary", query)
            modules               = understanding.get("modules", [])
            response_format       = understanding.get("response_format") or "PLAIN_TEXT"
            user_specified_format = understanding.get("user_specified_format", False)

            # Short-circuit for non-DB intents
            if intent in ("general", "web_search"):
                general_resp  = understanding.get("general_response") or ""
                web_resp      = understanding.get("web_search_summary") or ""
                # Fallback: LLM sometimes writes its answer in query_summary
                # instead of general_response. Use it rather than returning blank.
                fallback_resp = understanding.get("query_summary") or ""

                answer = general_resp or web_resp or fallback_resp or "I'm not sure how to answer that. Could you rephrase?"

                # ── Store structured turn — single write point ────────────────
                conversation_memory.add_turn(
                    session_id       = session_id,
                    user_query       = query,
                    query_summary    = summary,
                    intent           = intent,
                    modules          = [],
                    filter_fields    = {},
                    filter_values    = {},
                    general_response = answer,
                )

                loop.call_soon_threadsafe(q.put_nowait, {"type": "result", "data": {
                    "response_type":    intent,
                    "layout":           "PLAIN_TEXT",
                    "formatted_answer": answer,
                }})
                return

            # ── STEP 2: ANALYSIS ──────────────────────────────────────────────
            # Fetch the last db_query turn so the Analysis Agent can inherit
            # filter context for follow-up questions
            last_db_turn = conversation_memory.get_last_db_turn(session_id)

            a_cb, a_done = _make_thought_cb("Analysis Agent")
            analysis = analyze_query(
                summary,
                modules,
                thought_callback = a_cb,
                last_db_turn     = last_db_turn,
            )
            a_done()

            filter_values = analysis.get("filter_values", {})
            filter_fields = analysis.get("filter_fields", {})

            # ── STEP 3: RETRIEVAL ─────────────────────────────────────────────
            flat_filter_values: dict = {}
            for fv in filter_values.values():
                if isinstance(fv, dict):
                    flat_filter_values.update(fv)

            filtered_records = get_filtered_records(
                modules=analysis.get("modules", []),
                filter_fields=analysis.get("filter_fields", {}),
                filter_values={},
                module_filter_values=analysis.get("filter_values", {}),
                limit=analysis.get("limit"),
            )

            total_records = sum(len(r) for r in filtered_records.values())
            if total_records == 0:
                loop.call_soon_threadsafe(q.put_nowait, {"type": "result", "data": {
                    "response_type":    "no-data",
                    "layout":           "PLAIN_TEXT",
                    "formatted_answer": "No relevant data found for your query.",
                }})
                return

            # ── STEP 4: EXECUTION ─────────────────────────────────────────────
            e_cb, e_done = _make_thought_cb("Execution Agent")

            result = run_execution(
                question          = summary,
                filter_fields     = filter_fields,
                modules           = modules,
                filtered_records  = filtered_records,
                thought_callback  = e_cb,
                response_format   = response_format,
                user_specified    = user_specified_format,
            )
            e_done()

            queue_plan = result.get("queue", [])

            # ── STEP 5: FORMATTING ────────────────────────────────────────────
            f_cb, f_done = _make_thought_cb("Formatting Agent")

            try:
                formatted_result = format_pipeline_response(
                    result,
                    session_id     = session_id,
                    user_query     = query,
                    query_summary  = summary,
                    thought_callback = f_cb,
                )
                f_done()

                formatted_result["step_results"] = result.get("step_results", {})

                # For TABLE/GRAPH: attach actual data so the frontend can render it.
                # For PLAIN_TEXT etc.: the Formatting Agent already wrote the explanation.
                layout = formatted_result.get("layout", "PLAIN_TEXT")
                if layout in _DATA_HEAVY_FORMATS:
                    last_step_key = f"step_{len(queue_plan) - 1}" if queue_plan else None
                    final_val = None
                    if last_step_key:
                        last_step = result.get("step_results", {}).get(last_step_key, {})
                        final_val = last_step.get("final_value")
                    formatted_result["formatted_answer"] = json.dumps(
                        final_val if final_val is not None else result.get("step_results", {}),
                        default=str,
                    )

                logger.info("[Stream] pipeline complete — layout=%s", layout)

                # ── Store structured turn — single write point ────────────────
                # Stores query_summary (Understanding Agent's clean output) +
                # filter metadata (Analysis Agent's output) — NOT the formatted
                # answer text, which can be noisy JSON/table data.
                conversation_memory.add_turn(
                    session_id    = session_id,
                    user_query    = query,
                    query_summary = summary,
                    intent        = "db_query",
                    modules       = analysis.get("modules", []),
                    filter_fields = analysis.get("filter_fields", {}),
                    filter_values = analysis.get("filter_values", {}),
                )

                loop.call_soon_threadsafe(q.put_nowait, {"type": "result", "data": formatted_result})

            except Exception as e:
                f_done()
                logger.error("[Stream] Formatting error: %s", e)
                loop.call_soon_threadsafe(q.put_nowait, {"type": "error", "error": str(e)})

        except Exception as exc:
            logger.exception("[Stream] Unexpected worker failure")
            loop.call_soon_threadsafe(q.put_nowait, {"type": "error", "error": str(exc)})

    # ── Launch worker and consume queue ──────────────────────────────────────
    asyncio.create_task(asyncio.to_thread(_worker))

    while True:
        item = await q.get()
        t = item["type"]

        if t == "thinking_start":
            yield json.dumps({"status": "running_start", "stage": item["stage"]}) + "\n"

        elif t == "thinking_chunk":
            yield json.dumps({
                "status": "running_chunk",
                "stage":  item["stage"],
                "word":   item["word"],
            }) + "\n"

        elif t == "thinking_end":
            yield json.dumps({"status": "running_end", "stage": item["stage"]}) + "\n"

        elif t == "result":
            yield json.dumps({"status": "complete", "result": item["data"]}) + "\n"
            break

        elif t == "error":
            yield json.dumps({
                "status": "complete",
                "result": {
                    "response_type":    "error",
                    "layout":           "PLAIN_TEXT",
                    "formatted_answer": item["error"],
                },
            }) + "\n"
            break