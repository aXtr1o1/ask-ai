# stream_handler.py

import json
import asyncio
import time
import logging
from typing import AsyncGenerator

# Import your agents
from app.api.advance.Understanding_Agent.agent import classify_query
from app.api.advance.analysis.agent import analyze_query
from app.api.advance.retrieval.retrieval import get_filtered_records
from app.api.advance.execution.agent import run_execution
from app.api.advance.Formatting_agent.agent import format_pipeline_response

logger = logging.getLogger("advance.stream_handler")

def get_agent_thought(agent_name: str, raw_data: dict) -> dict:
    """Extract strictly the native thinking context from the agent for frontend rendering."""
    payload = {
        "agent": agent_name,
        "summary": "",
        "details": [],
        "raw": raw_data or {},
    }

    if not raw_data:
        payload["summary"] = f"{agent_name} thinking context unavailable."
        return payload

    thought = raw_data.get("thought")
    if thought and str(thought).strip():
        full_thought = str(thought).strip()
        words = full_thought.split()
        if len(words) > 10:
            payload["summary"] = " ".join(words[:10]) + "..."
        else:
            payload["summary"] = full_thought
        payload["full_thought"] = full_thought
    else:
        payload["summary"] = ""
        payload["full_thought"] = ""

    return payload

async def run_query_stream(query: str, session_id: str = "default") -> AsyncGenerator[str, None]:
    loop = asyncio.get_running_loop()
    q = asyncio.Queue()

    # Helper to send thinking updates (FULL)
    def send_thinking(stage: str, thought: dict):
        msg = {
            "type": "thinking",
            "stage": stage,
            "detail": thought.get("summary", ""),
            "thinking_context": thought,
        }
        loop.call_soon_threadsafe(q.put_nowait, msg)

    # Helper to chunk the full thought and stream it word-by-word from the backend
    def send_thinking_chunked(stage: str, thought: dict):
        full = thought.get("full_thought", "")
        if not full:
            return
            
        # Send a "start" signal so the frontend knows a new agent is typing
        loop.call_soon_threadsafe(q.put_nowait, {
            "type": "thinking_start",
            "stage": stage
        })
        
        # Split into words and stream them one by one
        words = full.split()
        for word in words:
            loop.call_soon_threadsafe(q.put_nowait, {
                "type": "thinking_chunk",
                "stage": stage,
                "word": word + " "
            })
            time.sleep(0.06) # Slower delay (60ms per word) to simulate native human-readable streaming
            
        # Send an "end" signal
        loop.call_soon_threadsafe(q.put_nowait, {
            "type": "thinking_end",
            "stage": stage
        })

    def _worker():
        try:
            # --- STEP 1: UNDERSTANDING ---
            understanding = classify_query(query, session_id=session_id)
            thought = get_agent_thought("Understanding", understanding)
            send_thinking_chunked("Understanding Agent", thought)
            
            intent = understanding.get("intent")
            summary = understanding.get("query_summary", query)
            modules = understanding.get("modules", [])

            if intent in ["general", "web_search"]:
                time.sleep(0.5) # Simulate work
                loop.call_soon_threadsafe(q.put_nowait, {"type": "result", "data": {
                    "response_type": intent,
                    "layout": "PLAIN_TEXT",
                    "formatted_answer": understanding.get("general_response") or understanding.get("web_search_summary") or ""
                }})
                return

            # --- STEP 2: ANALYSIS ---
            analysis = analyze_query(summary, modules)
            thought = get_agent_thought("Analysis", analysis)
            send_thinking_chunked("Analysis Agent", thought)
            
            filter_values = analysis.get("filter_values", {})
            filter_fields = analysis.get("filter_fields", {})

            # --- STEP 3: RETRIEVAL ---
            flat_filter_values = {}
            for fv in filter_values.values():
                if isinstance(fv, dict): flat_filter_values.update(fv)
                
            filtered_records = get_filtered_records(
                modules=modules, filter_fields=filter_fields, 
                filter_values=flat_filter_values, module_filter_values=filter_values
            )
            
            total_records = sum(len(r) for r in filtered_records.values())

            if total_records == 0:
                loop.call_soon_threadsafe(q.put_nowait, {"type": "result", "data": {
                    "response_type": "no-data", "layout": "PLAIN_TEXT",
                    "formatted_answer": "No relevant data found."
                }})
                return

            # --- STEP 4: EXECUTION ---
            def exec_progress(update):
                if isinstance(update, dict) and update.get("type") == "execution_thought":
                    t = get_agent_thought("Execution", {"thought": update.get("thought")})
                    send_thinking_chunked("Execution Agent", t)
            
            result = run_execution(
                question=summary, filter_fields=filter_fields, 
                modules=modules, filtered_records=filtered_records,
                progress_callback=exec_progress
            )
            
            queue_plan = result.get("queue", [])
            # The thought was already sent via progress callback!
            
            final_answer = json.dumps(result.get("step_results", {}), default=str)

            # --- STEP 5: FORMATTING ---
            # ✅ FIX 1: Build a real execution trace from the actual queue plan
            trace_lines = []
            for i, step_item in enumerate(queue_plan):
                tool = step_item.get('tool', 'unknown')
                module = step_item.get('module', '')
                trace_lines.append(f"Step {i}: Used {tool} on module {module}")
            
            execution_trace_input = {
                "execution_trace": "\n".join(trace_lines),  # Real trace instead of ""
                "step_results": result.get("step_results", {})
            }

            try:
                formatted_result = format_pipeline_response(
                    execution_trace_input,
                    session_id=session_id,
                    user_query=query,
                    query_summary=summary
                )
                
                # ✅ FIX 2: Extract the actual final_value instead of dumping raw JSON
                last_step_key = f"step_{len(queue_plan) - 1}" if queue_plan else None
                final_val = ""
                if last_step_key:
                    last_step_data = result.get("step_results", {}).get(last_step_key, {})
                    final_val = last_step_data.get("final_value", "")
                
                # Use the clean value as the answer; fallback to JSON only if no value exists
                formatted_result["formatted_answer"] = str(final_val) if final_val else json.dumps(result.get("step_results", {}), default=str)
                formatted_result["step_results"] = result.get("step_results", {})
                
                thought = get_agent_thought("Formatting", formatted_result)
                send_thinking_chunked("Formatting Agent", thought)
                
                # Give the user 1 second to read the formatting agent's thought 
                # before the final result overwrites the screen.
                import time
                time.sleep(1)
                
                loop.call_soon_threadsafe(q.put_nowait, {"type": "result", "data": formatted_result})
                
            except Exception as e:
                logger.error(f"Formatting error: {e}")
                loop.call_soon_threadsafe(q.put_nowait, {"type": "error", "error": str(e)})
        except Exception as exc:
            logger.exception("Unexpected stream worker failure")
            loop.call_soon_threadsafe(q.put_nowait, {"type": "error", "error": str(exc)})

    asyncio.create_task(asyncio.to_thread(_worker))

    while True:
        item = await q.get()
        if item["type"] == "thinking":
            # This matches your frontend's "running" status check
            yield json.dumps({
                "status": "running", 
                "stage": item["stage"], 
                "detail": item["detail"],
                "thinking_context": item.get("thinking_context", {}),
            }) + "\n"
        elif item["type"] == "thinking_start":
            yield json.dumps({
                "status": "running_start",
                "stage": item["stage"]
            }) + "\n"
        elif item["type"] == "thinking_chunk":
            yield json.dumps({
                "status": "running_chunk",
                "stage": item["stage"],
                "word": item["word"]
            }) + "\n"
        elif item["type"] == "thinking_end":
            yield json.dumps({
                "status": "running_end",
                "stage": item["stage"]
            }) + "\n"
        elif item["type"] == "result":
            yield json.dumps({"status": "complete", "result": item["data"]}) + "\n"
            break
        elif item["type"] == "error":
            yield json.dumps({"status": "complete", "result": {"response_type": "error", "formatted_answer": item["error"]}}) + "\n"
            break
        