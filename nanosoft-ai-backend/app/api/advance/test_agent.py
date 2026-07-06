"""
Test Agent — Direct Pipeline Runner

Goal: Run the full pipeline end-to-end without starting the server.
      Print a clear step-by-step log of what the agent did.

Usage:
  cd D:\\nonosoft_client_demo\\ask-ai\\nanosoft-ai-backend
  python -m app.api.advance.test_agent
"""
import json
import logging
import warnings
from pathlib import Path
warnings.filterwarnings("ignore")

from langchain_core.messages import HumanMessage

from app.api.advance.analysis.questions import QUESTIONS
from app.api.advance.retrieval.retrieval import get_filtered_records
from app.api.advance.execution.agent import get_agent


# =============================================================================
# LOG FILE SETUP
# Writes a clean readable log to: app/api/advance/advance_agent.log
# Every run appends to the same file so you can see the full history.
# =============================================================================
LOG_FILE = Path(__file__).parent / "advance_agent.log"

# Only write our own advance.* logs to the file — suppress all library noise
logging.basicConfig(
    level=logging.WARNING,     # default: only warnings from libraries
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
# Our advance logger writes at INFO level
logging.getLogger("advance").setLevel(logging.INFO)
# Silence noisy library loggers
logging.getLogger("advance.retrieval").setLevel(logging.WARNING)  # remove [RETRIEVAL] lines
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("langgraph").setLevel(logging.WARNING)

logger = logging.getLogger("advance")


LINE = "=" * 62
DASH = "-" * 50


def build_question_message(question_definition: dict) -> HumanMessage:
    """
    Build the question message that will be sent to the LLM.
    Contains: question text + which modules are loaded + column names and descriptions.
    The actual data is NOT here — only metadata (column names + what they mean).
    """
    filter_context = (
        json.dumps(question_definition["filter_fields"], indent=2)
        if question_definition["filter_fields"]
        else "No filters applied."
    )
    return HumanMessage(content=(
        f"Question: {question_definition['question']}\n\n"
        f"Modules loaded: {question_definition['modules']}\n"
        f"(Use only these module names when calling tools)\n\n"
        f"Available columns per module (column name -> what it means):\n"
        f"{filter_context}\n\n"
        f"Write the formula first, then call the right tool(s)."
    ))


def print_result(result: dict):
    """
    Print the execution trace in a clear, readable format:
      - Formula the LLM decided
      - Each tool called, its arguments, and its output
      - The final answer
    """
    trace = result.get("execution_trace", [])

    for entry in trace:

        if entry["type"] == "llm_decides_tool":
            print(f"\n  [STEP {entry['step']}] LLM Formula / Reasoning:")
            print(f"  {DASH}")
            for line in (entry.get("reasoning") or "").strip().split("\n"):
                print(f"    {line}")

            for i, t in enumerate(entry.get("tools", []), 1):
                print(f"\n  -> Tool {i}: {t['tool']}")
                print(f"    Args   : {t['args']}")
                print(f"    Output :")
                for line in json.dumps(t["output"], indent=6, default=str).split("\n"):
                    print(f"    {line}")

        elif entry["type"] == "final_answer":
            print(f"\n  [FINAL ANSWER]")
            print(f"  {DASH}")
            for line in (entry.get("answer") or "").strip().split("\n"):
                print(f"    {line}")


def run_question(question_id: str, filter_values: dict = {}):
    """
    Run the full pipeline for one question and print the result step-by-step.

    Step 1: Load question definition
    Step 2: Load and filter records from JSON files
    Step 3: Build the question message (what LLM will receive)
    Step 4: Run the agent → LLM decides formula → tool runs → final answer
    Step 5: Print result step-by-step
    """
    # Step 1: Load question definition
    question_definition = QUESTIONS[question_id]

    print(f"\n{LINE}")
    print(f"  Question ID : {question_id}")
    print(f"  Question    : {question_definition['question']}")
    print(f"  Modules     : {question_definition['modules']}")
    print(f"  Filters     : {filter_values or 'none'}")
    print(f"{LINE}")

    # Step 2: Load and filter records
    filtered_records = get_filtered_records(
        modules=question_definition["modules"],
        filter_fields=question_definition["filter_fields"],
        filter_values=filter_values,
    )
    for module, records in filtered_records.items():
        print(f"  [DATA] {module} -> {len(records)} records loaded")

    # Step 3: Build the question message
    question_message = build_question_message(question_definition)

    # Step 4: Build initial state and run the agent
    initial_state = {
        "messages":         [question_message],
        "question":         question_definition["question"],
        "modules":          question_definition["modules"],
        "filter_fields":    question_definition["filter_fields"],
        "filtered_records": filtered_records,
        "result":           {},
    }

    print(f"\n  [AGENT] Running ...\n")
    agent       = get_agent()
    # recursion_limit: max graph steps (each ask_llm + run_tool = 2 steps)
    # Q1 has 4 modules → needs ~8-12 steps; set 25 to be safe while still capping loops
    final_state = agent.invoke(initial_state, {"recursion_limit": 25})

    # Step 5: Print clear step-by-step result
    result = final_state.get("result", {})
    print_result(result)

    print(f"\n{LINE}\n")


if __name__ == "__main__":
    from datetime import datetime
    logger.info("=" * 60)
    logger.info("NEW RUN  %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    run_question("Q1")
    run_question("Q2")
    run_question("Q3")
    run_question("Q4")
    run_question("Q5")
    run_question("Q6")
    run_question("Q7")
    run_question("Q8")
    run_question("Q9")
    run_question("Q10")
