# stream_handler.py

import json
import asyncio
import time
import logging
from typing import AsyncGenerator

from app.api.advance.Understanding_Agent.agent import classify_query
from app.api.advance.analysis.agent import analyze_query
from app.api.advance.retrieval.retrieval import get_filtered_records
from app.api.advance.execution.agent import run_execution
from app.api.advance.Formatting_agent.agent import format_pipeline_response

logger = logging.getLogger("advance.stream_handler")

_DATA_HEAVY_FORMATS = {"TABLE", "GRAPH"}


def get_agent_thought(agent_name: str, raw_data: dict) -> dict:
    """Extract strictly the native thinking context from the agent for frontend rendering."""
    payload = {
        "agent":   agent_name,
        "summary": "",
        "details": [],
        "raw":     raw_data or {},
    }

    if not raw_data:
        payload["summary"] = f"{agent_name} thinking context unavailable."
        return payload

    thought = raw_data.get("thought")
    if thought and str(thought).strip():
        full_thought = str(thought).strip()
        words = full_thought.split()
        payload["summary"]    = " ".join(words[:10]) + "..." if len(words) > 10 else full_thought
        payload["full_thought"] = full_thought
    else:
        payload["summary"]    = ""
        payload["full_thought"] = ""

    return payload


async def run_query_stream(query: str, session_id: str = "default") -> AsyncGenerator[str, None]:
    loop = asyncio.get_running_loop()
    q    = asyncio.Queue()

    def send_thinking_chunked(stage: str, thought: dict):
        full = thought.get("full_thought", "")
        if not full:
            return

        loop.call_soon_threadsafe(q.put_nowait, {
            "type":  "thinking_start",
            "stage": stage,
        })

        for word in full.split():
            loop.call_soon_threadsafe(q.put_nowait, {
                "type":  "thinking_chunk",
                "stage": stage,
                "word":  word + " ",
            })
            time.sleep(0.06)

        loop.call_soon_threadsafe(q.put_nowait, {
            "type":  "thinking_end",
            "stage": stage,
        })

    def _worker():
        try:
            # ── STEP 1: UNDERSTANDING ──────────────────────────────────────
            understanding = classify_query(query, session_id=session_id)
            send_thinking_chunked("Understanding Agent", get_agent_thought("Understanding", understanding))

            intent  = understanding.get("intent")
            summary = understanding.get("query_summary", query)
            modules = understanding.get("modules", [])
            response_format      = understanding.get("response_format") or "PLAIN_TEXT"
            user_specified_format = understanding.get("user_specified_format", False)

            if intent in ("general", "web_search"):
                loop.call_soon_threadsafe(q.put_nowait, {"type": "result", "data": {
                    "response_type":    intent,
                    "layout":           "PLAIN_TEXT",
                    "formatted_answer": understanding.get("general_response") or understanding.get("web_search_summary") or "",
                }})
                return

            # ── STEP 2: ANALYSIS ───────────────────────────────────────────
            analysis = analyze_query(summary, modules)
            send_thinking_chunked("Analysis Agent", get_agent_thought("Analysis", analysis))

            filter_values = analysis.get("filter_values", {})
            filter_fields = analysis.get("filter_fields", {})

            # ── STEP 3: RETRIEVAL ──────────────────────────────────────────
            flat_filter_values = {}
            for fv in filter_values.values():
                if isinstance(fv, dict):
                    flat_filter_values.update(fv)

            filtered_records = get_filtered_records(
                modules=modules,
                filter_fields=filter_fields,
                filter_values=flat_filter_values,
                module_filter_values=filter_values,
            )

            total_records = sum(len(r) for r in filtered_records.values())
            if total_records == 0:
                loop.call_soon_threadsafe(q.put_nowait, {"type": "result", "data": {
                    "response_type":    "no-data",
                    "layout":           "PLAIN_TEXT",
                    "formatted_answer": "No relevant data found.",
                }})
                return

            # ── STEP 4: EXECUTION ──────────────────────────────────────────
            def exec_progress(update):
                if isinstance(update, dict) and update.get("type") == "execution_thought":
                    t = get_agent_thought("Execution", {"thought": update.get("thought")})
                    send_thinking_chunked("Execution Agent", t)

            result = run_execution(
                question         = summary,
                filter_fields    = filter_fields,
                modules          = modules,
                filtered_records = filtered_records,
                progress_callback= exec_progress,
                response_format  = response_format,
                user_specified   = user_specified_format,
            )

            queue_plan = result.get("queue", [])

            # ── STEP 5: FORMATTING ─────────────────────────────────────────
            try:
                formatted_result = format_pipeline_response(
                    result,
                    session_id    = session_id,
                    user_query    = query,
                    query_summary = summary,
                )

                # For TABLE/GRAPH: attach actual data so the frontend can render it.
                # For other formats: the Formatting Agent already wrote the explanation.
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

                formatted_result["step_results"] = result.get("step_results", {})

                # Use the explanation as the streaming thought for the Formatting Agent
                formatted_result["thought"] = formatted_result.get("explanation", "")
                send_thinking_chunked("Formatting Agent", get_agent_thought("Formatting", formatted_result))

                loop.call_soon_threadsafe(q.put_nowait, {"type": "result", "data": formatted_result})

            except Exception as e:
                logger.error("Formatting error: %s", e)
                loop.call_soon_threadsafe(q.put_nowait, {"type": "error", "error": str(e)})

        except Exception as exc:
            logger.exception("Unexpected stream worker failure")
            loop.call_soon_threadsafe(q.put_nowait, {"type": "error", "error": str(exc)})

    asyncio.create_task(asyncio.to_thread(_worker))

    while True:
        item = await q.get()
        t = item["type"]
        if t == "thinking_start":
            yield json.dumps({"status": "running_start", "stage": item["stage"]}) + "\n"
        elif t == "thinking_chunk":
            yield json.dumps({"status": "running_chunk", "stage": item["stage"], "word": item["word"]}) + "\n"
        elif t == "thinking_end":
            yield json.dumps({"status": "running_end", "stage": item["stage"]}) + "\n"
        elif t == "result":
            yield json.dumps({"status": "complete", "result": item["data"]}) + "\n"
            break
        elif t == "error":
            yield json.dumps({"status": "complete", "result": {"response_type": "error", "formatted_answer": item["error"]}}) + "\n"
            break