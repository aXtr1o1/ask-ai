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
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from langchain_core.messages import HumanMessage

from app.api.advance.Understanding_Agent.agent import classify_query
from app.api.advance.analysis.agent import analyze_query
from app.api.advance.retrieval.retrieval import get_filtered_records
from app.api.advance.execution.agent import run_execution


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

    # ------------------------------------------------------------------
    # Step 1: Understanding Agent
    # ------------------------------------------------------------------
    understanding = classify_query(query)
    intent = understanding.get("intent")
    summary = understanding.get("query_summary", query)

    print(f"  INTENT      : {intent}")
    print(f"  SUMMARY     : {summary}\n")

    if intent == "general":
        print(f"  [GENERAL RESPONSE]\n  {DASH}")
        print(f"  {understanding.get('general_response', '')}\n")
        return {
            "response_type": "general",
            "layout": "PLAIN_TEXT",
            "format_reason": "General conversational intent",
            "formatted_answer": understanding.get("general_response", "")
        }

    if intent == "web_search":
        print(f"  [WEB SEARCH NEEDED]\n  {DASH}")
        print(f"  {understanding.get('web_search_summary', 'Search the web for this query.')}\n")
        return {
            "response_type": "web_search",
            "layout": "PLAIN_TEXT",
            "format_reason": "Web search intent",
            "formatted_answer": understanding.get("web_search_summary", "Search the web for this query.")
        }

    # ------------------------------------------------------------------
    # Step 2: Analysis Agent
    # ------------------------------------------------------------------
    print(f"  {DASH}")
    print(f"  [ Analysis Agent ]")
    print(f"  {DASH}\n")

    analysis = analyze_query(summary, understanding.get("modules", []))
    modules = analysis.get("modules", [])
    filter_values = analysis.get("filter_values", {})
    filter_fields = analysis.get("filter_fields", {})

    print(f"  REASONING   : {analysis.get('reasoning', '')}\n")
    print(f"  MODULES     : {modules}\n")

    print(f"  FILTER VALUES :")
    for mod, fv in filter_values.items():
        print(f"    [{mod}] {json.dumps(fv)}")

    print(f"\n  FILTER FIELDS :")
    for mod, ff in filter_fields.items():
        print(f"    [{mod}] {ff}")

    if not modules:
        print("\n  [No modules identified - cannot retrieve data.]\n")
        return {
            "response_type": "no-modules",
            "layout": "PLAIN_TEXT",
            "format_reason": "No valid modules found for data retrieval",
            "formatted_answer": "Cannot retrieve data because no matching modules were found."
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
        return {
            "response_type": "no-data",
            "layout": "PLAIN_TEXT",
            "format_reason": "No data retrieved",
            "formatted_answer": "No records retrieved for this query."
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

    print_result(result)

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
    return {
        "response_type":    "analytical-answer",
        "layout":           "MARKDOWN",
        "format_reason":    "Queue-driven tool execution result",
        "formatted_answer": final_answer,
        "step_results":     result.get("step_results", {}),
        "status":           result.get("status", ""),
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
