"""
agent_logger.py — All logging logic for the execution agent.

Keeps agent.py clean by isolating every log line here.
The log file is: app/api/advance/advance_agent.log

Log format per question:
    QUESTION : <question text>
    -------------------------------------------------------
      WHY  : <why this tool is needed>
      CALL : <tool name> | module=<x> | <key args>
      GOT  : <one-line summary of tool result>

      ANSWER : <insight from final answer>
"""
import re
import logging

logger = logging.getLogger("advance.execution")


# =============================================================================
# Public functions — called from collect_result in agent.py
# =============================================================================

def log_question(question: str, pre_filters: dict = None):
    """Log the question being answered and any pre-filters."""
    logger.info("")
    logger.info("QUESTION : %s", question)
    if pre_filters:
        logger.info("PRE-FILTERS : %s", pre_filters)
    logger.info("-" * 55)


def log_why(reasoning: str):
    """
    Extract and log the formula the LLM decided to use.

    Priority order:
      1. Line that contains '=' and math operators → most likely the formula
      2. Line that starts with 'Formula:' or 'Approach:'
      3. First meaningful non-preamble line
    Skips: empty lines, lines starting with Step/Note/I will/I need
    """
    if not reasoning:
        return

    skip_prefixes = (
        "step ", "note", "i will", "i need", "i'll", "let me",
        "first", "next", "then", "finally", "to answer",
    )
    formula_keywords = ("=", "/", "×", "*", "%", "count", "group", "sum", "ratio", "divide")

    lines = [l.strip().lstrip("*#-•").strip() for l in reasoning.strip().split("\n")]
    lines = [re.sub(r"^\d+\.\s*", "", l) for l in lines]  # remove "1. " prefixes
    lines = [l for l in lines if l]  # remove empty

    best_formula = None
    best_approach = None
    first_meaningful = None

    for line in lines:
        lower = line.lower()

        # skip preamble lines
        if any(lower.startswith(p) for p in skip_prefixes):
            continue

        # priority 1: line looks like a formula
        if any(kw in lower for kw in formula_keywords) and best_formula is None:
            clean = re.sub(r"^formula:\s*", "", line, flags=re.IGNORECASE).strip()
            clean = re.sub(r"^approach:\s*", "", clean, flags=re.IGNORECASE).strip()
            best_formula = clean

        # priority 2: explicit formula/approach label
        if re.match(r"^(formula|approach)\s*:", lower) and best_approach is None:
            after = re.sub(r"^(formula|approach)\s*:\s*", "", line, flags=re.IGNORECASE).strip()
            if after:
                best_approach = after

        # priority 3: first meaningful line
        if first_meaningful is None and len(line) > 10:
            first_meaningful = line

    result = best_formula or best_approach or first_meaningful
    if result:
        logger.info("  THOUGHT : %s", result)


def log_tool_call(tool_name: str, args: dict):
    """
    Log what tool was called and its key arguments.
    Format: ACTION : <tool> | module=<x> | <key>=<val> | ...
    Excludes 'top_n' (not meaningful to the reader).
    """
    module = args.get("module", "")
    key_args = {k: v for k, v in args.items() if k not in ("module", "top_n")}
    line = f"{tool_name} | module={module}"
    if key_args:
        line += " | " + " | ".join(f"{k}={v}" for k, v in key_args.items())
    logger.info("  ACTION : %s", line)


def log_tool_result(output: dict, args: dict):
    """
    Log a one-line summary of what the tool returned.
    Shows: what tool returned + key numbers + top groups if any.

    count_records      → OBSERVATION : count = 10
    sum_values         → OBSERVATION : sum = 45.0  (6 records)
    get_average        → OBSERVATION : average = 11.16  (3 records)
    group_by_and_count → OBSERVATION : total = 10  |  top → Building A=3, Building B=2
    calculate_time_between → OBSERVATION : avg = 11.16 min  min = 8.27  max = 13.27  (3 records)
    do_math            → OBSERVATION : 9 DIV 10 = 0.9
    join_records       → OBSERVATION : matched = 5  unmatched_a = 2  unmatched_b = 1
    get_unique_values  → OBSERVATION : 4 unique values → [val1, val2, ...]
    """
    if "count" in output and "ranked" not in output and "stats" not in output:
        logger.info("  OBSERVATION : count = %s", output["count"])

    elif "total_sum" in output:
        logger.info("  OBSERVATION : sum = %s  (%s records)",
                    output["total_sum"], output.get("records_used"))

    elif "average" in output and "ranked" not in output:
        logger.info("  OBSERVATION : average = %s  (%s records)",
                    output["average"], output.get("records_used"))

    elif "ranked" in output:
        top   = output.get("ranked", [])[:5]
        total = output.get("total_records", "?")
        parts = []
        for r in top:
            # first non-count value is the group label
            label = next(
                (v for k, v in r.items() if k != "count"),
                "(unknown)"
            )
            if label is None or label == "":
                label = "(unassigned)"
            parts.append(f"{label} = {r.get('count')}")
        logger.info("  OBSERVATION : total = %s  |  top → %s", total, ",  ".join(parts))

    elif "stats" in output:
        s = output.get("stats", {})
        calc = output.get("calculated", "?")
        missing = output.get("missing_dates", 0)
        logger.info("  OBSERVATION : avg = %s min  |  min = %s min  |  max = %s min  "
                    "(%s records, %s missing dates)",
                    s.get("average"), s.get("minimum"), s.get("maximum"),
                    calc, missing)

    elif "result" in output:
        # do_math output
        logger.info("  OBSERVATION : %s %s %s = %s",
                    output.get("a"), output.get("operation"),
                    output.get("b"), output.get("result"))

    elif "matched_count" in output:
        logger.info("  OBSERVATION : matched = %s  |  unmatched_a = %s  |  unmatched_b = %s",
                    output.get("matched_count"),
                    output.get("unmatched_in_a"),
                    output.get("unmatched_in_b"))

    elif "unique_values" in output:
        vals = output.get("unique_values", [])[:6]
        logger.info("  OBSERVATION : %s unique values → %s",
                    output.get("count"), vals)

    else:
        logger.info("  OBSERVATION : %s", {k: v for k, v in output.items() if k != "module"})


def log_answer(final_text: str):
    """
    Log the final answer in 4 parts:
      APPROACH : how the LLM approached it
      FINAL_ANSWER_REASONING  : what formula/approach the LLM stated
      COMPUTED RESULT : the numeric result
      BUSINESS INSIGHT : the one-line conclusion
    """
    if not final_text:
        logger.info("  BUSINESS INSIGHT : (no answer text returned by LLM)")
        logger.info("")
        return

    approach_line  = None
    formula_line   = None
    computed_line  = None
    insight_line   = None

    skip_prefixes = ("step ", "i will", "i need", "let me", "to answer", "note")

    approach_triggers = ("approach", "method")
    formula_triggers  = ("formula",)
    computed_triggers = ("computed result", "result:", "calculated", "=", "%")
    insight_triggers  = ("insight", "conclusion", "therefore", "this means",
                         "the highest", "the most", "indicates", "suggests", "business insight")

    for line in final_text.strip().split("\n"):
        clean = line.strip().lstrip("*-•#").strip()
        if not clean:
            continue
        lower = clean.lower()

        if any(lower.startswith(p) for p in skip_prefixes):
            continue

        if approach_line is None and any(t in lower for t in approach_triggers):
            approach_line = re.sub(r"^(approach|method)\s*:\s*", "",
                                   clean, flags=re.IGNORECASE).strip()

        if formula_line is None and any(t in lower for t in formula_triggers):
            formula_line = re.sub(r"^(formula)\s*:\s*", "",
                                  clean, flags=re.IGNORECASE).strip()

        if computed_line is None and any(t in lower for t in computed_triggers):
            computed_line = re.sub(r"^(computed result|result|calculated)\s*:\s*", "",
                                   clean, flags=re.IGNORECASE).strip()

        if insight_line is None and any(t in lower for t in insight_triggers):
            insight_line = re.sub(r"^(business insight|insight|conclusion|therefore)\s*:\s*", "",
                                  clean, flags=re.IGNORECASE).strip()

    # fallback
    if not insight_line:
        for line in reversed(final_text.strip().split("\n")):
            clean = line.strip().lstrip("*-•#").strip()
            if clean and len(clean) > 15:
                insight_line = clean
                break

    if approach_line:
        logger.info("  APPROACH : %s", approach_line)
    if formula_line:
        logger.info("  FINAL_ANSWER_REASONING  : %s", formula_line)
    if computed_line:
        logger.info("  COMPUTED RESULT : %s", computed_line)
    logger.info("  BUSINESS INSIGHT : %s", insight_line or final_text.strip().split("\n")[0])
    logger.info("")