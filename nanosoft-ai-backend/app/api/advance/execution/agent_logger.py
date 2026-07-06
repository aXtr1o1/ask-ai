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

def log_question(question: str):
    """Log the question being answered."""
    logger.info("")
    logger.info("QUESTION : %s", question)
    logger.info("-" * 55)


def log_why(reasoning: str):
    """
    Extract the first meaningful line from the LLM's reasoning and log it.
    Strips 'Formula:' prefix and numbered list prefixes like '1. '.
    """
    if not reasoning:
        return
    for line in reasoning.strip().split("\n"):
        clean = line.strip().lstrip("*#").strip()
        clean = re.sub(r"^\d+\.\s*", "", clean)              # remove "1. "
        clean = re.sub(r"^formula:\s*", "", clean, flags=re.IGNORECASE)  # remove "Formula:"
        clean = clean.strip()
        if clean and clean.lower() not in ("computed result:", ""):
            logger.info("  WHY  : %s", clean)
            return


def log_tool_call(tool_name: str, args: dict):
    """
    Log what tool was called and its key arguments.
    Format: CALL : <tool> | module=<x> | <key>=<val> | ...
    Excludes 'top_n' (not meaningful to the reader).
    """
    module = args.get("module", "")
    key_args = {k: v for k, v in args.items() if k not in ("module", "top_n")}
    line = f"{tool_name} | module={module}"
    if key_args:
        line += " | " + " | ".join(f"{k}={v}" for k, v in key_args.items())
    logger.info("  CALL : %s", line)


def log_tool_result(output: dict, args: dict):
    """
    Log a one-line summary of what the tool returned.
    Format depends on output type:
      count_records    → GOT  : count = 10
      group_by_count   → GOT  : total = 10  |  top: Name=3, Name=2
      sum/average/stats → short summary
    """
    if "count" in output and "ranked" not in output:
        logger.info("  GOT  : count = %s", output["count"])

    elif "total_sum" in output:
        logger.info("  GOT  : sum = %s  (from %s records)",
                    output["total_sum"], output.get("records_used"))

    elif "average" in output:
        logger.info("  GOT  : average = %s  (from %s records)",
                    output["average"], output.get("records_used"))

    elif "ranked" in output:
        top   = output.get("ranked", [])[:3]
        total = output.get("total_records", "?")
        parts = []
        for r in top:
            val = list(r.values())[0]
            if val is None or val == "":
                val = "(unassigned)"
            parts.append(f"{val} = {r.get('count')}")
        logger.info("  GOT  : total = %s  |  top: %s", total, ",  ".join(parts))

    elif "stats" in output:
        s = output["stats"]
        logger.info("  GOT  : min=%s  max=%s  avg=%s",
                    s.get("min"), s.get("max"), s.get("mean"))

    elif "values" in output:
        logger.info("  GOT  : %s unique values", output.get("count"))

    else:
        logger.info("  GOT  : %s", {k: v for k, v in output.items() if k != "module"})


def log_answer(final_text: str):
    """
    Extract the insight/conclusion from the final answer and log it.

    Rules (searched from the bottom of the answer up):
      Rule 1 : Line starts with "Insight:" → use text after the prefix
      Rule 2 : Skip lines starting with "Formula:", "Computed Result:", "Result:"
      Rule 3 : Use the first line that passes Rules 1 & 2
    """
    skip_starts = ("formula", "computed result", "result:")
    insight = ""

    for line in reversed(final_text.strip().split("\n")):
        clean = line.strip().lstrip("*-•").strip()
        if not clean:
            continue
        clean_lower = clean.lower()

        # Rule 1: "Insight: ..." → extract and stop
        if clean_lower.startswith("insight:"):
            after = clean[len("insight:"):].strip()
            if after:
                insight = after
            break

        # Rule 2: skip formula/result lines
        if any(clean_lower.startswith(p) for p in skip_starts):
            continue

        # Rule 3: use this line
        insight = clean
        break

    logger.info("  ANSWER : %s", insight or final_text.strip().split("\n")[0])
    logger.info("")
