"""
Analysis Pipeline Test Runner
==============================
Tests the Understanding Agent → Analysis Agent pipeline directly from terminal.

Usage:
  cd D:\\nonosoft_client_demo\\ask-ai\\nanosoft-ai-backend
  python -m app.api.advance.analysis.test_analysis
"""
import json
import logging
import warnings
warnings.filterwarnings("ignore")

from app.api.advance.Understanding_Agent.agent import classify_query
from app.api.advance.analysis.agent import analyze_query


# =============================================================================
# LOGGING SETUP — only show our own logs, suppress library noise
# =============================================================================
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("advance").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)

LINE = "=" * 62
DASH = "-" * 50


def run_query(query: str):
    """Run one query through Understanding → Analysis and print results."""
    print(f"\n{LINE}")
    print(f"  [RAW QUERY] : {query}")
    print(f"{LINE}\n")

    understanding = classify_query(query)
    intent = understanding.get("intent")
    
    print(f"  INTENT      : {intent}")
    
    if intent == "general":
        print(f"  REPLY       : {understanding.get('general_response')}\n")
        return
    elif intent == "web_search":
        print(f"  SEARCH      : {understanding.get('web_search_summary', '')[:200]}...\n")
        return

    query_summary = understanding.get('query_summary')
    print(f"  SUMMARY     : {query_summary}\n")

    print(f"  {'-' * 58}")
    print(f"  [ Analysis Agent ]")
    print(f"  {'-' * 58}\n")
    import sys; sys.stdout.flush()

    result = analyze_query(query_summary)

    print(f"  REASONING   : {result.get('reasoning')}\n")
    print(f"  MODULES     : {result.get('modules')}\n")

    print(f"  FILTER VALUES :")
    fv = result.get("filter_values", {})
    has_values = False
    if fv:
        for mod, values in fv.items():
            if values:
                print(f"    [{mod}] {json.dumps(values)}")
                has_values = True
    if not has_values:
        print("    (none)")
        
    print(f"\n  FILTER FIELDS :")
    ff = result.get("filter_fields", {})
    for mod, fields in ff.items():
        print(f"    [{mod}] {list(fields.keys())}")
        
    print(f"{LINE}\n")


if __name__ == "__main__":
    print(f"\n{LINE}")
    print("  FM Analysis Pipeline — Interactive Mode")
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
