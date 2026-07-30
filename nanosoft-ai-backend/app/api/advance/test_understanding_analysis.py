

import json
import logging

from app.api.advance.Understanding_Agent.agent import classify_query
from app.api.advance.analysis.agent import analyze_query


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def main():
    query = input("Enter Query: ").strip()
    session_id = "test-session"

    print("\n" + "=" * 70)
    print("UNDERSTANDING AGENT")
    print("=" * 70)

    understanding = classify_query(
        query=query,
        session_id=session_id,
    )

    print(json.dumps(understanding, indent=4))

    # Stop if the query doesn't require Analysis Agent
    if understanding["intent"] != "db_query":
        print("\nAnalysis Agent skipped (intent is not db_query).")
        return

    print("\n" + "=" * 70)
    print("ANALYSIS AGENT")
    print("=" * 70)

    analysis = analyze_query(
        query_summary=understanding["query_summary"],
        modules=understanding["modules"],
    )

    print(json.dumps(analysis, indent=4))


if __name__ == "__main__":
    main()