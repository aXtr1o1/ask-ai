"""
Test Retrieval — Direct Retrieval Pipeline Runner

Goal: Run the retrieval pipeline end-to-end without starting the server
      and without the execution/agent layer.
      Print the filtered records loaded for each module.

Usage:
  cd nanosoft-ai-backend
  python -m app.api.advance.test_agent
"""
import json
import logging
import warnings
from pathlib import Path
warnings.filterwarnings("ignore")

# ── Force-import retrieval modules so route loggers are registered FIRST ─────
# retrieval.py lazy-imports these; doing it here means route loggers already
# exist before we apply any suppression below.
import app.api.advance.retrieval.assets   # noqa: F401
import app.api.advance.retrieval.bdm      # noqa: F401
import app.api.advance.retrieval.fa       # noqa: F401
import app.api.advance.retrieval.ppm      # noqa: F401
import app.api.advance.retrieval.sb       # noqa: F401

from app.api.advance.analysis.questions import QUESTIONS
from app.api.advance.retrieval.retrieval import get_filtered_records


# =============================================================================
# LOG FILE SETUP
# Writes a clean readable log to: app/api/advance/advance_agent.log
# Every run appends to the same file so you can see the full history.
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
logging.getLogger("advance.retrieval").setLevel(logging.INFO)

# ── Block route logger duplicates from propagating to root ────────────────────
_ROUTE_LOGGERS = frozenset(
    {"assets_route", "bdm_route", "fa_route", "ppm_route", "sb_route",
     "postgres_client"}
)

class _NoRouteDuplicates(logging.Filter):
    def filter(self, record):
        return record.name not in _ROUTE_LOGGERS

for _h in logging.root.handlers:
    _h.addFilter(_NoRouteDuplicates())

# ── Silence noisy library loggers ─────────────────────────────────────────────
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("langgraph").setLevel(logging.WARNING)

logger = logging.getLogger("advance")

LINE = "=" * 62
DASH = "-" * 50


def run_question(question_id: str):
    """
    Run the retrieval pipeline for one question and print the results.

    Step 1: Load question definition from questions.py
    Step 2: Load and filter records from DB using module_filter_values
    Step 3: Print filtered records per module
    """
    # Step 1: Load question definition
    question_definition = QUESTIONS[question_id]
    module_filter_values = question_definition.get("filter_values", {})

    config_log = (
        "======================================================================\n"
        "QUESTION CONFIGURATION\n"
        "======================================================================\n"
        f"Question ID : {question_id}\n"
        f"Question    : {question_definition['question']}\n"
        f"Modules     : {question_definition['modules']}\n\n"
        "Pre-Filter Values (from questions.py):\n"
        f"{json.dumps(module_filter_values, indent=4)}\n\n"
        "Filter Fields:\n"
        f"{json.dumps(question_definition.get('filter_fields', {}), indent=4)}"
    )
    logger.info(config_log)

    print(f"\n{LINE}")
    print(f"  Question [{question_id}]: {question_definition['question']}")
    print(LINE)

    # Step 2: Load and filter records from DB
    filtered_records = get_filtered_records(
        modules=question_definition["modules"],
        filter_fields=question_definition["filter_fields"],
        filter_values={},
        module_filter_values=module_filter_values,
    )

    # Step 3: Print filtered records per module
    for module, records in filtered_records.items():
        logger.info("  [DATA] %s -> %d records loaded", module, len(records))
        print(f"\n  Module: {module}  ({len(records)} records)")
        print(f"  {DASH}")
        if records:
            print(json.dumps(records[:5], indent=4, default=str))
            if len(records) > 5:
                print(f"  ... and {len(records) - 5} more records.")
        else:
            print("  (no records)")

    print(f"\n{LINE}\n")


if __name__ == "__main__":
    from datetime import datetime
    logger.info("=" * 60)
    logger.info("NEW RUN  %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    #run_question("Q1")
    #run_question("Q2")
    #run_question("Q3")
    #run_question("Q4")
    #run_question("Q5")
    #run_question("Q6")
    #run_question("Q7")
    #run_question("Q8")
    #run_question("Q9")
    #run_question("Q10")
    #run_question("Q11")
    #run_question("Q12")
    #run_question("Q13")
    #run_question("Q14")
    #run_question("Q15")
    run_question("Q16")
    #run_question("Q17")
    #run_question("Q18")
    #run_question("Q19")
    #run_question("Q20")
