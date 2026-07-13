import logging
from pathlib import Path
from app.api.advance.analysis.agent import analyze_query

# File log setup matching the execution pipeline
LOG_FILE = Path(__file__).parents[1] / "advance_agent.log"

logging.basicConfig(
    level=logging.WARNING,     # default: only warnings from libraries
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ]
)

# Set our own loggers to INFO level
logging.getLogger("advance").setLevel(logging.INFO)




def main():
    print("=== Analysis Agent — Interactive Mode ===")
    print("Type a query and press Enter to analyze it (map to question and extract filters).")
    print("Type 'exit' or press Ctrl+C to quit.\n")

    while True:
        try:
            query = input("Query > ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit"):
                print("Exiting.")
                break

            # analyze_query logs the structured output automatically
            analyze_query(query)
            print()
        except KeyboardInterrupt:
            print("\nExiting.")
            break


if __name__ == "__main__":
    main()
