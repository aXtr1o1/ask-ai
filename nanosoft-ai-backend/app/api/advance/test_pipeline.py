"""
Full Pipeline Test — Interactive Mode

Flow:
  User types a query
    → Understanding Agent  : intent + rich query_summary
    → Analysis Agent       : modules + filter_values + filter_fields
    → Retrieval Layer      : filtered DB records per module
    → Execution Agent      : tools run on records → final answer

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
from app.api.advance.execution.agent import get_agent


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

# Suppress noisy route / library loggers
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
# BUILD QUESTION MESSAGE FOR EXECUTION AGENT
# =============================================================================
def build_question_message(question: str, filter_fields: dict, filtered_records: dict) -> HumanMessage:
    """
    Build the message that the Execution Agent receives.
    Contains: the question, column definitions, and actual data records.
    """
    filter_context = (
        json.dumps(filter_fields, indent=2)
        if filter_fields
        else "No column definitions provided."
    )

    data_sections = []
    for module, records in filtered_records.items():
        data_sections.append(
            f"--- Module: {module} ({len(records)} records) ---\n"
            + json.dumps(records, indent=2, default=str)
        )
    data_context = "\n\n".join(data_sections) if data_sections else "No data loaded."

    return HumanMessage(content=(
        f"Question: {question}\n\n"
        f"Modules loaded: {list(filtered_records.keys())}\n"
        f"(Use only these module names when calling tools)\n\n"
        f"Column definitions per module:\n"
        f"{filter_context}\n\n"
        f"Actual data records:\n"
        f"{data_context}\n\n"
        f"Think through your approach, call the necessary tools, then deliver your final answer.\n"
        f"Your answer must include: Approach, Formula, Computed Result, and Business Insight.\n"
        f"The Computed Result must be a concrete value — a number, duration, or percentage."
    ))


# =============================================================================
# PRINT EXECUTION AGENT RESULT
# =============================================================================
def print_result(result: dict):
    trace = result.get("execution_trace", [])
    for entry in trace:
        if entry["type"] == "llm_decides_tool":
            print(f"\n  [STEP {entry['step']}] REASONING:")
            print(f"  {DASH}")
            reasoning_text = (entry.get("reasoning") or "").strip()
            if reasoning_text and reasoning_text != "[]":
                for line in reasoning_text.split("\n"):
                    print(f"    {line}")
            for i, t in enumerate(entry.get("tools", []), 1):
                print(f"\n  -> Tool {i}: {t['tool']}")
                print(f"     Args   : {t['args']}")
                print(f"     Output :")
                for line in json.dumps(t["output"], indent=6, default=str).split("\n"):
                    print(f"     {line}")
        elif entry["type"] == "final_answer":
            print(f"\n  [FINAL ANSWER]")
            print(f"  {DASH}")
            for line in (entry.get("answer") or "").strip().split("\n"):
                print(f"    {line}")


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
        print(f"  {understanding.get('response', '')}\n")
        return

    if intent == "web_search":
        print(f"  [WEB SEARCH NEEDED]\n  {DASH}")
        print(f"  {understanding.get('response', 'Search the web for this query.')}\n")
        return

    # ------------------------------------------------------------------
    # Step 2: Analysis Agent
    # ------------------------------------------------------------------
    print(f"  {DASH}")
    print(f"  [ Analysis Agent ]")
    print(f"  {DASH}\n")

    analysis = analyze_query(summary)
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
        print("\n  [No modules identified — cannot retrieve data.]\n")
        return

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
        print(f"  [{label}] → {len(records)} records retrieved after filtering")
        if records:
            sample = records[:sample_rows]
            print(f"  Sample ({min(sample_rows, len(records))} rows):")
            for row in sample:
                print(f"    {json.dumps(row, default=str)}")
        else:
            print(f"  (no records returned)")

    total_records = sum(len(r) for r in filtered_records.values())
    if total_records == 0:
        print(f"\n  [No records retrieved — skipping Execution Agent.]\n")
        print(f"{LINE}\n")
        return

    # ------------------------------------------------------------------
    # Step 4: Execution Agent
    # ------------------------------------------------------------------
    print(f"\n  {DASH}")
    print(f"  [ Execution Agent ]")
    print(f"  {DASH}\n")

    question_message = build_question_message(summary, filter_fields, filtered_records)

    initial_state = {
        "messages":             [question_message],
        "question":             summary,
        "modules":              modules,
        "filter_fields":        filter_fields,
        "module_filter_values": filter_values,
        "filtered_records":     filtered_records,
        "result":               {},
    }

    print(f"  [AGENT] Running ...\n")
    agent = get_agent()
    final_state = agent.invoke(initial_state, {"recursion_limit": 50})

    result = final_state.get("result", {})
    print_result(result)

    print(f"\n{LINE}\n")


# =============================================================================
# INTERACTIVE MAIN LOOP
# =============================================================================
if __name__ == "__main__":
    from datetime import datetime
    logger.info("=" * 60)
    logger.info("NEW RUN  %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    print(f"\n{LINE}")
    print(f"  FM Full Pipeline — Interactive Mode")
    print(f"  Understanding -> Analysis -> Retrieval -> Execution")
    print(f"  Type your query and press Enter. Type 'exit' to quit.")
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
