"""
Retrieval Pipeline Test Runner
================================
Tests the full pipeline:
  Understanding Agent → Analysis Agent → Retrieval Layer

Prints:
  - Intent + query summary (from Understanding Agent)
  - Modules, filter_fields, filter_values (from Analysis Agent)
  - Record counts and sample data per module (from Retrieval Layer)

Usage:
  cd D:\\nonosoft_client_demo\\ask-ai\\nanosoft-ai-backend
  python -m app.api.advance.retrieval.test_retrieval
"""
import json
import logging
import warnings
warnings.filterwarnings("ignore")

from app.api.advance.Understanding_Agent.agent import classify_query
from app.api.advance.analysis.agent import analyze_query
from app.api.advance.retrieval.retrieval import get_filtered_records


# =============================================================================
# LOGGING SETUP — only show our own logs, suppress library and route noise
# =============================================================================
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Enable our pipeline logs
logging.getLogger("advance").setLevel(logging.INFO)

# Suppress messy external/route logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("assets_route").setLevel(logging.WARNING)
logging.getLogger("postgres_client").setLevel(logging.WARNING)
logging.getLogger("ppm_route").setLevel(logging.WARNING)
logging.getLogger("bdm_route").setLevel(logging.WARNING)
logging.getLogger("fa_route").setLevel(logging.WARNING)
logging.getLogger("sb_route").setLevel(logging.WARNING)

LINE = "=" * 62
DASH = "-" * 50


def run_query(query: str, sample_rows: int = 3):
    """
    Run one query through Understanding → Analysis → Retrieval and print results.

    Args:
        query       : raw user question
        sample_rows : how many sample records to print per module (default 3)
    """
    print(f"\n{LINE}")
    print(f"  [RAW QUERY] : {query}")
    print(f"{LINE}\n")

    # ------------------------------------------------------------------
    # Step 1: Understanding Agent
    # ------------------------------------------------------------------
    understanding = classify_query(query)
    intent = understanding.get("intent")

    print(f"  INTENT      : {intent}")

    if intent == "general":
        print(f"  REPLY       : {understanding.get('general_response')}\n")
        return
    elif intent == "web_search":
        print(f"  SEARCH      : {understanding.get('web_search_summary', '')[:200]}...\n")
        return

    query_summary = understanding.get("query_summary")
    print(f"  SUMMARY     : {query_summary}\n")

    # ------------------------------------------------------------------
    # Step 2: Analysis Agent
    # ------------------------------------------------------------------
    print(f"  {DASH}")
    print(f"  [ Analysis Agent ]")
    print(f"  {DASH}\n")

    analysis = analyze_query(query_summary)

    print(f"  REASONING   : {analysis.get('reasoning')}\n")
    print(f"  MODULES     : {analysis.get('modules')}\n")

    filter_values = analysis.get("filter_values", {})   # { module: { col: val } }
    filter_fields = analysis.get("filter_fields", {})   # { module: { col: desc } }

    print("  FILTER VALUES :")
    has_values = any(v for v in filter_values.values())
    if has_values:
        for mod, vals in filter_values.items():
            if vals:
                print(f"    [{mod}] {json.dumps(vals)}")
    else:
        print("    (none)")

    print("\n  FILTER FIELDS :")
    for mod, fields in filter_fields.items():
        print(f"    [{mod}] {list(fields.keys())}")

    # ------------------------------------------------------------------
    # Step 3: Retrieval Layer
    # ------------------------------------------------------------------
    print(f"\n  {DASH}")
    print(f"  [ Retrieval Layer ]")
    print(f"  {DASH}\n")

    modules = analysis.get("modules", [])

    # filter_values from analysis agent is { module: { col: val } }
    # retrieval.get_filtered_records expects:
    #   filter_values      = flat dict applied across all modules  (HTTP-level)
    #   module_filter_values = per-module pre-filters from analysis { module: { col: val } }
    #
    # Since the analysis agent already separated them per-module, we pass
    # them as module_filter_values. The flat filter_values is empty (no HTTP
    # request context here — this is a direct pipeline test).
    filtered_records = get_filtered_records(
        modules=modules,
        filter_fields=filter_fields,
        filter_values={},               # no flat HTTP-level filters in test
        module_filter_values=filter_values,  # analysis agent's per-module filters
    )

    for module, records in filtered_records.items():
        print(f"  [{module.upper()}] → {len(records)} records retrieved after filtering")

        if records and sample_rows > 0:
            print(f"  Sample ({min(sample_rows, len(records))} rows):")
            for row in records[:sample_rows]:
                print(f"    {json.dumps(row, default=str)}")
        elif not records:
            print(f"  (no records returned)")
        print()

    print(f"{LINE}\n")


if __name__ == "__main__":
    print(f"\n{LINE}")
    print("  FM Retrieval Pipeline — Interactive Mode")
    print("  Type your query and press Enter. Type 'exit' to quit.")
    print(f"{LINE}\n")

    while True:
        try:
            query = input("  Query: ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit", "q"):
                print("\n  Goodbye.\n")
                break
            run_query(query)
        except KeyboardInterrupt:
            print("\n\n  Goodbye.\n")
            break
        except EOFError:
            print("\n\n  Goodbye.\n")
            break
