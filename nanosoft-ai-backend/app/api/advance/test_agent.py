"""
Direct agent runner — no server, no FastAPI.
Runs Q1 and Q2 directly in the terminal and prints clean formatted output.

Usage:
  cd D:\nonosoft_client_demo\ask-ai\nanosoft-ai-backend
  python -m app.api.advance.test_agent
"""
import json
import warnings
warnings.filterwarnings("ignore")   # suppress pandas FutureWarning in output

from app.api.advance.analysis.questions import QUESTIONS
from app.api.advance.retrieval.retrieval import get_filtered_records
from app.api.advance.execution.agent import get_agent


def _parse_interpretation(raw) -> str:
    """Extract clean text from agent interpretation (handles list with thinking extras)."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts = []
        for item in raw:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(p for p in parts if p)
    return str(raw)


def _print_tool_output(i: int, tool_out: dict):
    """Print a single tool output in readable format."""
    print(f"\n  -- Tool {i} " + "-"*36)

    # Show what operation was performed
    if "start_field" in tool_out:
        print(f"  Formula   : elapsed_minutes({tool_out['module']}, {tool_out['start_field']} -> {tool_out['end_field']})")
        print(f"  Records   : {tool_out['total_records']} total | {tool_out.get('computed_count', 0)} computed | {tool_out.get('null_count', 0)} null ({tool_out.get('null_rate_percent', 0)}%)")
        stats = tool_out.get("stats", {})
        if stats:
            print(f"  Average   : {stats.get('average')} min")
            print(f"  Min / Max : {stats.get('min')} / {stats.get('max')} min")
            print(f"  Std Dev   : {stats.get('stddev')} | Variance: {stats.get('variance')}")

    elif "group_field" in tool_out:
        print(f"  Formula   : group_and_count({tool_out['module']}, group_by={tool_out['group_field']})")
        print(f"  Records   : {tool_out['total_records']} total | {tool_out.get('unique_groups', 0)} groups")
        print(f"  Ranked    :")
        for rank in tool_out.get("ranked", [])[:5]:
            group_key = tool_out["group_field"]
            group_val = rank.get(group_key)
            group_val_str = str(group_val) if group_val is not None else "(no value)"
            print(f"              {group_val_str:40s} -> {rank.get('count')} records")

    elif "count" in tool_out and "condition" in tool_out:
        print(f"  Formula   : count_records({tool_out['module']}, condition={tool_out['condition']})")
        print(f"  Count     : {tool_out['count']}")

    elif "sum" in tool_out:
        print(f"  Formula   : sum_field({tool_out['module']}, field={tool_out.get('field')})")
        print(f"  Sum       : {tool_out['sum']}")

    elif "average" in tool_out:
        print(f"  Formula   : average_field({tool_out['module']}, field={tool_out.get('field')})")
        print(f"  Average   : {tool_out['average']}")

    elif "result" in tool_out and "operation" in tool_out:
        print(f"  Formula   : arithmetic({tool_out['operation']}, a={tool_out['a']}, b={tool_out.get('b', '')})")
        print(f"  Result    : {tool_out['result']}")

    else:
        print(f"  Output    : {json.dumps(tool_out, indent=14)}")


def run_question(question_id: str, filter_values: dict = {}):
    q_def = QUESTIONS[question_id]

    print(f"\n{'='*60}")
    print(f"  Q{question_id[-1]}  {q_def['question']}")
    print(f"  Modules : {q_def['modules']}")
    print(f"  Filters : {filter_values or 'none applied'}")
    print(f"{'='*60}")

    # Step 1: Retrieve
    filtered_records = get_filtered_records(
        modules=q_def["modules"],
        filter_fields=q_def["filter_fields"],
        filter_values=filter_values,
    )
    counts = {m: len(r) for m, r in filtered_records.items()}
    print(f"\n  [RETRIEVAL]")
    print(f"  Filter values : {filter_values if filter_values else 'none (no filters passed -> all records returned)'}")
    print(f"  Record counts : {counts}")

    # Show retrieved records per module
    for module, records in filtered_records.items():
        print(f"\n  -- {module.upper()} records ({len(records)}) --")
        for idx, rec in enumerate(records, 1):
            print(f"    [{idx}] {rec}")


    # Step 2: Run agent
    agent = get_agent()
    initial_state = {
        "messages":         [],
        "question":         q_def["question"],
        "modules":          q_def["modules"],
        "filter_fields":    q_def["filter_fields"],
        "filtered_records": filtered_records,
        "result":           {},
    }
    print("  [AGENT]    Thinking...\n")
    final_state = agent.invoke(initial_state)
    result = final_state.get("result", {})

    # Step 3: Print tool outputs
    tool_outputs = result.get("tool_outputs", [])
    print(f"  [TOOLS CALLED: {len(tool_outputs)}]")
    for i, tool_out in enumerate(tool_outputs, 1):
        _print_tool_output(i, tool_out)

    # Step 4: Print agent answer
    interpretation = _parse_interpretation(result.get("agent_interpretation", ""))
    print(f"\n  [AGENT ANSWER]")
    for line in interpretation.strip().split("\n"):
        print(f"  {line}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    # -- No filters (all records) --
    run_question("Q1", filter_values={})
    run_question("Q2", filter_values={})
    run_question("Q3", filter_values={})
    run_question("Q4", filter_values={})
    run_question("Q5", filter_values={})

    # -- With filters (real usage) --
    run_question("Q1", filter_values={"locality": "Doha"})
    run_question("Q2", filter_values={"building": "Building 1 - Residential High Rise"})
    run_question("Q3", filter_values={"locality": "Doha"})
    run_question("Q4", filter_values={"building": "Reef Mall"})
    run_question("Q5", filter_values={"locality": "Doha"})