"""
Full Pipeline Test — Interactive Mode

Flow:
  User types a query
    → Step 1 — Understanding Agent : intent + query_summary + modules
    → Step 2 — Analysis Agent      : filter_fields + filter_values
                                     (receives only the selected modules' metadata)
    → Step 3 — Retrieval Layer     : filtered DB records per module
    → Step 4 — Execution Agent     : runs tools on records → final answer

Usage:
  cd D:\\nonosoft_client_demo\\ask-ai\\nanosoft-ai-backend
  python -m app.api.advance.test_pipeline
"""
import json
import logging
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from langchain_core.messages import HumanMessage

from app.api.advance.Understanding_Agent.agent import classify_query
from app.api.advance.analysis.agent import analyze_query
from app.api.advance.retrieval.retrieval import get_filtered_records
from app.api.advance.execution.agent import run_execution
from app.api.advance.Formatting_agent.agent import format_pipeline_response


# =============================================================================
# LOGGING — only show our own pipeline logs, suppress all library/route noise
# =============================================================================
LOG_FILE = Path(__file__).parent / "advance_agent.log"

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
logging.getLogger("advance").setLevel(logging.INFO)

# Suppress noisy library loggers
for _name in [
    "httpx", "httpcore", "google", "langchain", "langgraph",
    "assets_route", "bdm_route", "ppm_route", "fa_route", "sb_route",
    "postgres_client",
]:
    logging.getLogger(_name).setLevel(logging.WARNING)

logger = logging.getLogger("advance")

LINE = "=" * 62
DASH = "-" * 50


# =============================================================================
# BUILD SCHEMA MESSAGE — for display/logging only (NOT sent to execution agent)
# The execution agent receives schema via run_execution(), not a HumanMessage.
# =============================================================================
def _schema_summary(filter_fields: dict) -> str:
    """Return a compact string summarising the schema for display."""
    parts = []
    for mod, fields in filter_fields.items():
        if isinstance(fields, dict):
            parts.append(f"  [{mod}] {list(fields.keys())}")
    return "\n".join(parts) if parts else "  (no schema)"


# =============================================================================
# LATENCY HELPERS
# =============================================================================
def _build_latency_dict(
    understanding: dict,
    analysis: dict,
    execution: dict,
    grand_total: float,
) -> dict:
    """Build the unified latency payload that is returned to the caller."""
    return {
        "understanding": {
            "llm_time":        understanding.get("llm_time",        0),
            "web_search_time": understanding.get("web_search_time", 0),
            "total_time":      understanding.get("total_time",      0),
        },
        "analysis": {
            "llm_time":   analysis.get("llm_time",   0),
            "total_time": analysis.get("total_time", 0),
        },
        "execution": {
            "llm_time":       execution.get("llm_time",       0),
            "execution_time": execution.get("execution_time", 0),
            "total_time":     execution.get("total_time",     0),
        },
        "grand_total": round(grand_total, 2),
    }


def _print_latency_summary(
    understanding: dict,
    analysis: dict,
    execution: dict,
    grand_total: float,
) -> None:
    """Print a concise latency summary table to stdout."""
    u_llm   = understanding.get("llm_time",        0)
    u_ws    = understanding.get("web_search_time", 0)
    u_tot   = understanding.get("total_time",      0)
    a_llm   = analysis.get("llm_time",   0)
    a_tot   = analysis.get("total_time", 0)
    e_llm   = execution.get("llm_time",       0)
    e_exec  = execution.get("execution_time", 0)
    e_tot   = execution.get("total_time",     0)

    print(f"\n{LINE}")
    print(f"  LATENCY SUMMARY")
    print(f"  {DASH}")
    print(f"  Understanding Agent  LLM: {u_llm:.2f}s  WebSearch: {u_ws:.2f}s  Total: {u_tot:.2f}s")
    if analysis:
        print(f"  Analysis Agent       LLM: {a_llm:.2f}s  Total: {a_tot:.2f}s")
    if execution:
        print(f"  Execution Agent      LLM: {e_llm:.2f}s  ToolExec: {e_exec:.2f}s  Total: {e_tot:.2f}s")
    print(f"  {DASH}")
    print(f"  GRAND TOTAL          {grand_total:.2f}s")
    print(f"{LINE}\n")



# =============================================================================
# PRINT EXECUTION RESULT
# =============================================================================
def print_result(result: dict):
    """Print the planned queue and each step's tool output."""
    queue        = result.get("queue", [])
    step_results = result.get("step_results", {})
    status       = result.get("status", "?")
    tools_called = result.get("tools_called", 0)
    queue_total  = result.get("queue_total", 0)

    print(f"\n  [PLANNED QUEUE]  ({len(queue)} steps)")
    print(f"  {DASH}")
    for step in queue:
        print(f"    Step {step['step']}: {step['tool']}  args={step.get('args', {})}")

    print(f"\n  [EXECUTION TRACE]")
    print(f"  {DASH}")
    for step in queue:
        step_key  = f"step_{step['step']}"
        tool_name = step["tool"]
        output    = step_results.get(step_key, {})
        print(f"\n  Step {step['step']}: {tool_name}")
        print(f"     Args   : {step.get('args', {})}")
        print(f"     Output :")
        for line in json.dumps(output, indent=6, default=str).split("\n"):
            print(f"     {line}")

    print(f"\n  [STATUS] {status}  |  {tools_called}/{queue_total} steps")

    latency = result.get("latency")
    if latency:
        print(f"  [LATENCY] Total: {latency.get('total_time', 0):.2f}s | LLM Plan: {latency.get('llm_time', 0):.2f}s | Tool Exec: {latency.get('execution_time', 0):.2f}s")

    if step_results:
        last_key    = f"step_{len(queue) - 1}"
        last_output = step_results.get(last_key, {})
        final_value = last_output.get("final_value", last_output)
        print(f"\n  [FINAL ANSWER]")
        print(f"  {DASH}")
        print(f"    {json.dumps(final_value, indent=4, default=str)}")



# =============================================================================
# FULL PIPELINE RUN FOR ONE QUERY
# =============================================================================
def run_query(query: str, sample_rows: int = 3):
    print(f"\n{LINE}")
    print(f"  [RAW QUERY] : {query}")
    print(f"{LINE}\n")

    run_start = time.perf_counter()          # grand-total wall clock
    latency_understanding = {}
    latency_analysis      = {}
    latency_execution     = {}

    # ------------------------------------------------------------------
    # Step 1: Understanding Agent
    # ------------------------------------------------------------------
    understanding = classify_query(query)
    latency_understanding = understanding.get("latency", {})
    intent  = understanding.get("intent")
    summary = understanding.get("query_summary", query)

    print(f"  INTENT      : {intent}")
    print(f"  SUMMARY     : {summary}\n")
    print(f"  [UNDERSTANDING] LLM: {latency_understanding.get('llm_time', 0):.2f}s | Total: {latency_understanding.get('total_time', 0):.2f}s")

    if intent == "general":
        print(f"  [GENERAL RESPONSE]\n  {DASH}")
        print(f"  {understanding.get('general_response', '')}\n")
        grand_total = time.perf_counter() - run_start
        _print_latency_summary(
            latency_understanding, {}, {},
            grand_total=grand_total,
        )
        return {
            "response_type": "general",
            "layout": "PLAIN_TEXT",
            "format_reason": "General conversational intent",
            "formatted_answer": understanding.get("general_response", ""),
            "latency": _build_latency_dict(latency_understanding, {}, {}, grand_total),
        }

    if intent == "web_search":
        print(f"  [WEB SEARCH NEEDED]\n  {DASH}")
        print(f"  {understanding.get('web_search_summary', 'Search the web for this query.')}\n")
        grand_total = time.perf_counter() - run_start
        _print_latency_summary(
            latency_understanding, {}, {},
            grand_total=grand_total,
        )
        return {
            "response_type": "web_search",
            "layout": "PLAIN_TEXT",
            "format_reason": "Web search intent",
            "formatted_answer": understanding.get("web_search_summary", "Search the web for this query."),
            "latency": _build_latency_dict(latency_understanding, {}, {}, grand_total),
        }

    # ------------------------------------------------------------------
    # Step 2: Analysis Agent
    # ------------------------------------------------------------------
    print(f"  {DASH}")
    print(f"  [ Analysis Agent ]")
    print(f"  {DASH}\n")

    analysis = analyze_query(summary, understanding.get("modules", []))
    latency_analysis = analysis.get("latency", {})
    modules       = analysis.get("modules", [])
    filter_values = analysis.get("filter_values", {})
    filter_fields = analysis.get("filter_fields", {})

    print(f"  REASONING   : {analysis.get('reasoning', '')}\n")
    print(f"  MODULES     : {modules}\n")
    print(f"  [ANALYSIS]  LLM: {latency_analysis.get('llm_time', 0):.2f}s | Total: {latency_analysis.get('total_time', 0):.2f}s\n")

    print(f"  FILTER VALUES :")
    for mod, fv in filter_values.items():
        print(f"    [{mod}] {json.dumps(fv)}")

    print(f"\n  FILTER FIELDS :")
    for mod, ff in filter_fields.items():
        print(f"    [{mod}] {ff}")

    if not modules:
        print("\n  [No modules identified - cannot retrieve data.]\n")
        grand_total = time.perf_counter() - run_start
        _print_latency_summary(
            latency_understanding, latency_analysis, {},
            grand_total=grand_total,
        )
        return {
            "response_type": "no-modules",
            "layout": "PLAIN_TEXT",
            "format_reason": "No valid modules found for data retrieval",
            "formatted_answer": "Cannot retrieve data because no matching modules were found.",
            "latency": _build_latency_dict(latency_understanding, latency_analysis, {}, grand_total),
        }

    # ------------------------------------------------------------------
    # Step 3: Retrieval Layer
    # ------------------------------------------------------------------
    print(f"\n  {DASH}")
    print(f"  [ Retrieval Layer ]")
    print(f"  {DASH}\n")

    # filter_values from analysis agent is {module: {col: val}} but retrieval
    # expects a flat dict, so flatten it by merging all module filters together.
    flat_filter_values: dict = {}
    for fv in filter_values.values():
        flat_filter_values.update(fv)

    filtered_records = get_filtered_records(
        modules=modules,
        filter_fields=filter_fields,
        filter_values=flat_filter_values,
        module_filter_values=filter_values,
    )

    for module, records in filtered_records.items():
        label = module.upper()
        print(f"  [{label}] -> {len(records)} records retrieved after filtering")
        # sample rows commented out - uncomment to debug individual records
        # if records:
        #     sample = records[:sample_rows]
        #     print(f"  Sample ({min(sample_rows, len(records))} rows):")
        #     for row in sample:
        #         print(f"    {json.dumps(row, default=str)}")
        if not records:
            print(f"  (no records returned)")

    total_records = sum(len(r) for r in filtered_records.values())
    if total_records == 0:
        print(f"\n  [No records retrieved - skipping Execution Agent.]\n")
        print(f"{LINE}\n")
        grand_total = time.perf_counter() - run_start
        _print_latency_summary(
            latency_understanding, latency_analysis, {},
            grand_total=grand_total,
        )
        return {
            "response_type": "no-data",
            "layout": "PLAIN_TEXT",
            "format_reason": "No data retrieved",
            "formatted_answer": "No records retrieved for this query.",
            "latency": _build_latency_dict(latency_understanding, latency_analysis, {}, grand_total),
        }

    # ------------------------------------------------------------------
    # Step 4: Execution Agent (Queue-Driven)
    # ------------------------------------------------------------------
    print(f"\n  {DASH}")
    print(f"  [ Execution Agent — Queue-Driven ]")
    print(f"  {DASH}\n")

    print(f"  Schema being sent to planner:")
    print(_schema_summary(filter_fields))
    print(f"\n  (Actual data rows go to Execution Context only — LLM never sees them)\n")

    print(f"  [AGENT] Running ...\n")
    result = run_execution(
        question         = summary,
        filter_fields    = filter_fields,
        modules          = modules,
        filtered_records = filtered_records,
    )
    latency_execution = result.get("latency", {})

    print_result(result)

    grand_total = time.perf_counter() - run_start
    _print_latency_summary(
        latency_understanding, latency_analysis, latency_execution,
        grand_total=grand_total,
    )

    # Extract final answer from the last step's tool output
    step_results = result.get("step_results", {})
    queue        = result.get("queue", [])
    final_answer = ""
    if step_results and queue:
        last_key    = f"step_{len(queue) - 1}"
        last_output = step_results.get(last_key, {})
        final_value = last_output.get("final_value", last_output)
        final_answer = json.dumps(final_value, default=str)

    print(f"\n{LINE}\n")
    print(f"  Formatting Agent (Generating UI Layout from Trace)")
    print(f"{LINE}\n")

    # Only pass the execution trace (steps taken), NOT the raw data, to save tokens
    trace_lines = [f"Step {q.get('step', i)}: {q.get('tool', 'unknown')}" for i, q in enumerate(queue)]
    trace_summary = "\n".join(trace_lines)
    if not trace_summary:
        trace_summary = "No steps were taken."
        
    execution_trace_input = {
        "execution_trace": trace_summary,
        "step_results": step_results
    }

    try:
        formatted_result = format_pipeline_response(
            execution_trace_input,
            query=summary,
            analysis_context={
                "reasoning": analysis.get("reasoning", ""),
                "modules": modules,
                "filter_fields": filter_fields
            }
        )

        # Keep the formatted_answer as the raw data, allowing the Formatting Agent's explanation
        # to provide the rich context on the frontend instead of hardcoding it here.
        formatted_result["formatted_answer"] = final_answer
        formatted_result["step_results"]     = result.get("step_results", {})
        formatted_result["status"]           = result.get("status", "")
        formatted_result["latency"]          = _build_latency_dict(
            latency_understanding, latency_analysis, latency_execution, grand_total
        )
        return formatted_result
    except Exception as e:
        logger.error(f"Formatting Agent failed: {e}")
        return {
            "response_type":    "analytical-answer",
            "layout":           "MARKDOWN",
            "format_reason":    "Formatting failed, returning raw execution result",
            "formatted_answer": final_answer,
            "step_results":     result.get("step_results", {}),
            "status":           result.get("status", ""),
            "latency":          _build_latency_dict(
                latency_understanding, latency_analysis, latency_execution, grand_total
            ),
        }


# =============================================================================
# INTERACTIVE MAIN LOOP OR FASTAPI SERVER
# =============================================================================
if __name__ == "__main__":
    import sys
    from datetime import datetime
    logger.info("=" * 60)
    logger.info("NEW RUN  %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    if "--api" in sys.argv:
        print(f"\n{LINE}")
        print(f"  FM Full Pipeline - API Mode")
        print(f"  Starting FastAPI server on http://localhost:8000")
        print(f"{LINE}\n")
        
        import uvicorn
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from pydantic import BaseModel

        app = FastAPI()
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        class QueryRequest(BaseModel):
            query: str

        @app.post("/api/query")
        def api_query(request: QueryRequest):
            try:
                res = run_query(request.query)
                return res if res else {
                    "response_type": "error",
                    "layout": "PLAIN_TEXT",
                    "format_reason": "No response returned",
                    "formatted_answer": "Pipeline failed to produce an answer."
                }
            except Exception as exc:
                logger.error("Pipeline error: %s", exc, exc_info=True)
                return {
                    "response_type": "error",
                    "layout": "PLAIN_TEXT",
                    "format_reason": "Internal server error",
                    "formatted_answer": str(exc)
                }

        uvicorn.run(app, host="0.0.0.0", port=8000)

    else:
        print(f"\n{LINE}")
        print(f"  FM Full Pipeline - Interactive Mode")
        print(f"  Understanding -> Analysis -> Retrieval -> Execution")
        print(f"  Type your query and press Enter. Type 'exit' to quit.")
        print(f"  (Run with --api to start the REST server)")
        print(f"{LINE}\n")

        while True:
            try:
                query = input("  Query: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  Exiting.\n")
                break

            if query.lower() in ("exit", "quit", "q"):
                print("\n  Exiting.\n")
                break

            if not query:
                continue

            try:
                run_query(query)
            except Exception as exc:
                logger.error("Pipeline error: %s", exc, exc_info=True)
                print(f"\n  [ERROR] {exc}\n")
