"""
Test Agent — Direct Pipeline Runner (Queue-Driven Architecture)

Flow:
  Load question definition
    → Retrieve filtered records
    → run_execution() : plan queue (LLM once) + execute queue (tools only)
    → Print step-by-step results from tools (no LLM answer text)

Usage:
  cd D:\\nonosoft_client_demo\\ask-ai\\nanosoft-ai-backend
  python -m app.api.advance.test_agent
"""
import json
import logging
import warnings
from pathlib import Path
warnings.filterwarnings("ignore")

from app.api.advance.analysis.questions import QUESTIONS
from app.api.advance.retrieval.retrieval import get_filtered_records
from app.api.advance.execution.agent import run_execution


# =============================================================================
# LOG FILE SETUP
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
logging.getLogger("advance.retrieval").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("langgraph").setLevel(logging.WARNING)

logger = logging.getLogger("advance")

LINE = "=" * 62
DASH = "-" * 50


# =============================================================================
# PRINT RESULT — display planned queue + step-by-step tool outputs
# =============================================================================
def print_result(result: dict):
    """
    Print the execution result in a clear, readable format.

    Shows:
      - The planned queue (what the LLM decided to do)
      - Each step's tool output (what actually ran)
      - Final answer from the last tool result
    """
    queue        = result.get("queue", [])
    step_results = result.get("step_results", {})
    status       = result.get("status", "?")
    queue_total  = result.get("queue_total", 0)
    tools_called = result.get("tools_called", 0)

    # ── Planned Queue ────────────────────────────────────────────────────────
    print(f"\n  [PLANNED QUEUE]  ({len(queue)} steps)")
    print(f"  {DASH}")
    for step in queue:
        print(f"    Step {step['step']}: {step['tool']}  args={step.get('args', {})}")

    # ── Step Results ─────────────────────────────────────────────────────────
    print(f"\n  [EXECUTION TRACE]")
    print(f"  {DASH}")
    for step in queue:
        step_key  = f"step_{step['step']}"
        tool_name = step["tool"]
        output    = step_results.get(step_key, {})

        print(f"\n  Step {step['step']}: {tool_name}")
        print(f"    Args   : {step.get('args', {})}")
        print(f"    Output :")
        for line in json.dumps(output, indent=6, default=str).split("\n"):
            print(f"    {line}")

    # ── Completion Status ────────────────────────────────────────────────────
    print(f"\n  [STATUS] {status}  |  {tools_called}/{queue_total} steps executed")

    # ── Final Answer (from last step's tool output) ──────────────────────────
    if step_results:
        last_key    = f"step_{len(queue) - 1}"
        last_output = step_results.get(last_key, {})
        final_value = last_output.get("final_value", last_output)

        print(f"\n  [FINAL ANSWER]")
        print(f"  {DASH}")
        print(f"    {json.dumps(final_value, indent=4, default=str)}")


# =============================================================================
# RUN ONE QUESTION
# =============================================================================
def run_question(question_id: str, filter_values: dict = {}):
    """
    Run the full pipeline for one question and print the result.

    Step 1: Load question definition
    Step 2: Retrieve and filter records from the database
    Step 3: Plan queue (LLM called once — sees schema, NOT data rows)
    Step 4: Execute queue (tools only — reads data from Execution Context)
    Step 5: Print step-by-step tool results
    """
    question_definition = QUESTIONS[question_id]

    print(f"\n{LINE}")
    print(f"  Question ID : {question_id}")
    print(f"  Question    : {question_definition['question']}")
    print(f"  Modules     : {question_definition['modules']}")
    print(f"  Filters     : {filter_values or 'none'}")
    print(f"{LINE}")

    # Step 1: Load and filter records
    module_filter_values = question_definition.get("filter_values", {})
    filtered_records = get_filtered_records(
        modules=question_definition["modules"],
        filter_fields=question_definition["filter_fields"],
        filter_values=filter_values,
        module_filter_values=module_filter_values,
    )
    for module, records in filtered_records.items():
        print(f"  [DATA] {module} → {len(records)} records loaded")

    # Step 2: Run execution agent
    #   - LLM sees: question + schema (filter_fields) — NOT actual records
    #   - Tools see: filtered_records via Execution Context
    print(f"\n  [AGENT] Running ...\n")
    result = run_execution(
        question         = question_definition["question"],
        filter_fields    = question_definition["filter_fields"],
        modules          = question_definition["modules"],
        filtered_records = filtered_records,
    )

    # Step 3: Print results
    print_result(result)
    print(f"\n{LINE}\n")


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    from datetime import datetime
    logger.info("=" * 60)
    logger.info("NEW RUN  %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    # run_question("Q1")
    run_question("Q2")
    # run_question("Q3")
    # run_question("Q4")
    # run_question("Q5")
    # run_question("Q6")
    # run_question("Q7")
    # run_question("Q8")
    # run_question("Q9")
    # run_question("Q10")
