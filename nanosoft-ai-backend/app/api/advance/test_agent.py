"""
Direct agent runner — no server, no FastAPI.
Runs Q1 and Q2 directly in the terminal and prints a clean execution trace.

Usage:
  cd D:\\nonosoft_client_demo\\ask-ai\\nanosoft-ai-backend
  python -m app.api.advance.test_agent
"""
import json
import warnings
warnings.filterwarnings("ignore")   # suppress pandas FutureWarning in output

from app.api.advance.analysis.questions import QUESTIONS
from app.api.advance.retrieval.retrieval import get_filtered_records
from app.api.advance.execution.agent import get_agent

SEP = "=" * 62
BAR = "─" * 50


# ── Format helpers ─────────────────────────────────────────────────────────

def _fmt_args(args: dict) -> str:
    """Format tool args as a clean single-line summary."""
    parts = [f"{k}={v!r}" for k, v in args.items() if v not in (None, "", 0)]
    return "  |  ".join(parts) if parts else "(none)"


def _fmt_output(tool_out: dict) -> list:
    """Format a tool output dict as a list of readable lines."""
    lines = []

    # elapsed_minutes
    if "start_field" in tool_out:
        lines.append(
            f"    elapsed_minutes({tool_out.get('module')}) : "
            f"{tool_out.get('start_field')} -> {tool_out.get('end_field')}"
        )
        lines.append(
            f"    records   : {tool_out.get('total_records')} total | "
            f"{tool_out.get('computed_count')} computed | "
            f"{tool_out.get('null_count')} null ({tool_out.get('null_rate_percent')}%)"
        )
        stats = tool_out.get("stats", {})
        if stats:
            lines.append(
                f"    avg / min / max : "
                f"{stats.get('average')} / {stats.get('min')} / {stats.get('max')} min"
            )
            lines.append(
                f"    stddev : {stats.get('stddev')}  |  variance : {stats.get('variance')}"
            )

    # group_and_count
    elif "group_field" in tool_out:
        lines.append(
            f"    group_and_count({tool_out.get('module')}) "
            f"group_by={tool_out.get('group_field')} | "
            f"total={tool_out.get('total_records')} records | "
            f"{tool_out.get('unique_groups')} groups"
        )
        for rank in tool_out.get("ranked", [])[:5]:
            gk = tool_out["group_field"]
            lines.append(f"      {str(rank.get(gk, '?')):<40s} -> {rank.get('count')} records")

    # count_records
    elif "count" in tool_out and "condition" in tool_out:
        lines.append(
            f"    count_records({tool_out.get('module')}) = {tool_out.get('count')} "
            f"| condition: {tool_out.get('condition')}"
        )

    # sum_field
    elif "sum" in tool_out:
        lines.append(
            f"    sum_field({tool_out.get('module')}, field={tool_out.get('field')}) = "
            f"{tool_out.get('sum')}  |  {tool_out.get('values_found')} values"
        )

    # average_field
    elif "average" in tool_out and "field" in tool_out:
        lines.append(
            f"    average_field({tool_out.get('module')}, field={tool_out.get('field')}) = "
            f"{tool_out.get('average')}  |  {tool_out.get('values_found')} values"
        )

    # arithmetic / logarithm
    elif "result" in tool_out and "operation" in tool_out:
        b = tool_out.get("b", "")
        b_str = f", {b}" if b not in ("", 0) else ""
        lines.append(
            f"    {tool_out.get('operation')}({tool_out.get('a')}{b_str}) = {tool_out.get('result')}"
        )

    # min_field / max_field / stddev / variance
    elif any(k in tool_out for k in ("min", "max", "stddev", "variance")):
        for k in ("min", "max", "stddev", "variance"):
            if k in tool_out:
                lines.append(
                    f"    {k}_field({tool_out.get('module')}, field={tool_out.get('field')}) = "
                    f"{tool_out.get(k)}"
                )

    else:
        lines.append(f"    {json.dumps(tool_out)}")

    return lines


# ── Trace printer ──────────────────────────────────────────────────────────

def _print_execution_trace(trace: list):
    """
    Print the full agent execution trace in structured format:

      STEP N — Agent Decides Formula
        WHY (LLM Reasoning):  <thinking text>
        Tool 1: <name>
          Args  : ...
          Output: ...

      FINAL ANSWER
        <thinking before final answer>
        <final text>
    """
    if not trace:
        print("  (no execution trace available)")
        return

    for entry in trace:
        etype = entry.get("type")

        # ── Agent decided to call tools ────────────────────────────────
        if etype == "agent_decides_tools":
            step     = entry["step"]
            thinking = (entry.get("thinking") or "").strip()
            tools    = entry.get("tools", [])

            print(f"\n  +-- STEP {step} - Agent Decides Formula " + "-" * 28)

            # LLM Reasoning / Thinking
            print(f"  |")
            if thinking:
                print(f"  |  WHY (LLM Reasoning):")
                for line in thinking.split("\n"):
                    print(f"  |    {line}")

            # Each tool called
            for i, tool_info in enumerate(tools, 1):
                tool_name = tool_info["tool"]
                args      = tool_info["args"]
                output    = tool_info.get("output", {})

                print(f"  |")
                print(f"  |  >> Tool {i}: {tool_name}")
                print(f"  |     Args   : {_fmt_args(args)}")
                print(f"  |     Output :")
                for line in _fmt_output(output):
                    print(f"  |  {line}")

        # ── Final answer ───────────────────────────────────────────────
        elif etype == "final_answer":
            thinking = (entry.get("thinking") or "").strip()
            text     = (entry.get("text") or "").strip()

            print(f"\n  +-- FINAL ANSWER " + "-" * 44)

            if thinking:
                print(f"\n  [LLM Reasoning before final answer]")
                for line in thinking.split("\n"):
                    print(f"    {line}")

            print()
            for line in text.split("\n"):
                print(f"  {line}")


# ── Main runner ────────────────────────────────────────────────────────────

def run_question(question_id: str, filter_values: dict = {}):
    q_def = QUESTIONS[question_id]

    print(f"\n{SEP}")
    print(f"  Q{question_id[-1]}  {q_def['question']}")
    print(f"  Modules : {q_def['modules']}")
    print(f"  Filters : {filter_values or 'none applied'}")
    print(f"{SEP}")

    # Step 1: Retrieve data silently — never shown, goes directly to tools
    filtered_records = get_filtered_records(
        modules=q_def["modules"],
        filter_fields=q_def["filter_fields"],
        filter_values=filter_values,
    )
    counts = {m: len(r) for m, r in filtered_records.items()}
    print(f"\n  [DATA]  {' | '.join(f'{m} -> {n} records loaded' for m, n in counts.items())}")

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
    print(f"  [AGENT] Running...\n")
    final_state = agent.invoke(initial_state)
    result = final_state.get("result", {})

    # Step 3: Print execution trace
    trace = result.get("execution_trace", [])
    _print_execution_trace(trace)

    print(f"\n{SEP}\n")


if __name__ == "__main__":
    run_question("Q1", filter_values={})
    run_question("Q2", filter_values={})
    run_question("Q3", filter_values={})
    run_question("Q4", filter_values={})
    run_question("Q5", filter_values={})

