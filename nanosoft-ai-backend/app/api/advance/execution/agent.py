"""
FM Analytics Execution Agent — Queue-Driven, Tool-Only Architecture

Flow:
  Phase 1 — Planning (LLM called ONCE):
    question + schema  →  LLM  →  JSON queue of tool steps

  Phase 2 — Execution (no LLM, no loop):
    queue  →  run step by step  →  tools only  →  Execution Context
    filtered_records sit in Execution Context — tools read from there

  Final output:
    Raw tool results. LLM is never involved after Phase 1.
    Status: COMPLETE | PARTIAL | FAILED

Fix 3 — Pre-execution $ref key validation:
  _validate_queue() now checks every $step_N.key reference against the
  known OUTPUT KEYS of the referenced tool BEFORE the queue runs.
  This catches LLM hallucinations (wrong key names) at zero latency cost.

Public API:
  run_execution(question, filter_fields, modules, filtered_records) → ExecutionResult
"""
import json
import logging
import time

from google.genai import types

from app.config import settings
from app.api.advance.execution.prompts      import PLANNER_SYSTEM_PROMPT
from app.api.advance.execution.queue_runner import run_queue
from app.api.advance.execution.agent_logger import (
    log_question, log_queue, log_completion
)
from app.api.advance.execution.context_builder import build_formatting_context
from app.api.advance.analysis.metadata.enum_values import get_enum_block
from app.api.advance.gemini_stream import stream_with_thoughts

logger = logging.getLogger("advance.execution.agent")


# =============================================================================
# HELPERS — JSON extraction from LLM response
# =============================================================================

def _extract_text(response_content) -> str:
    """Pull plain text from a Gemini response (handles list-of-blocks format)."""
    if isinstance(response_content, str):
        return response_content
    if isinstance(response_content, list):
        for block in response_content:
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                return block["text"]
    return str(response_content)


def _strip_markdown(raw: str) -> str:
    """Remove markdown code fences if the model wrapped JSON in them."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.IGNORECASE)
        raw = raw.rstrip("`").strip()
    return raw


# =============================================================================
# TOOL OUTPUT KEYS — Fix 3: used to validate $ref keys before execution
# Each entry lists the keys that tool is guaranteed to return on success.
# Keep in sync with tools.py.
# =============================================================================
_TOOL_OUTPUT_KEYS: dict[str, set[str]] = {
    "count_records":          {"count", "module", "condition_field", "condition_value"},
    "sum_values":             {"total_sum", "records_used", "module", "field"},
    "get_average":            {"average", "records_used", "module", "field"},
    "get_minimum":            {"minimum", "records_used", "module", "field"},
    "get_maximum":            {"maximum", "records_used", "module", "field"},
    "calculate_time_between": {"stats", "calculated", "missing_dates", "total_records",
                               "module", "start_field", "end_field"},
    "group_by_and_count":     {"groups", "total_records", "unique_groups",
                               "module", "group_field", "filter_field", "filter_value"},
    "get_unique_values":      {"unique_values", "count", "module", "field",
                               "filter_field", "filter_value"},
    "join_records":           {"matched_count", "unmatched_in_a", "unmatched_in_b",
                               "records_in_a", "records_in_b",
                               "module_a", "module_b", "join_field"},
    "do_math":                {"result", "operation", "a", "b"},
    "sort_and_limit":         {"sorted_data", "total_in", "total_out",
                               "sort_by", "order", "limit"},
    "group_by_and_aggregate": {"groups", "total_records", "unique_groups",
                               "module", "group_field", "agg_field", "operation"},
    "count_records_multi":    {"count", "module",
                               "condition_field_1", "condition_value_1",
                               "condition_field_2", "condition_value_2",
                               "condition_field_3", "condition_value_3",
                               "condition_field_4", "condition_value_4"},
    "get_record_fields":      {"module", "total", "fields_returned", "records"},
    "final_answer_tool":      {"status", "final_value"},
}


def _validate_queue(queue: list) -> None:
    """
    Structural + $ref validation of the planned queue.

    Checks:
      1. Queue is a non-empty list of dicts with 'step' and 'tool' keys.
      2. The last step is always 'final_answer_tool'.
      3. Fix 3 — Every $step_N.key reference points to:
           a. A step index that exists and comes BEFORE the current step.
           b. A key that is in the known OUTPUT KEYS of that tool.
         This catches LLM hallucinations before the queue runner starts.
    """
    if not isinstance(queue, list) or len(queue) == 0:
        raise ValueError("Agent returned an empty or non-list queue.")

    # Build a map: step_index → tool_name for all steps seen so far
    step_tool_map: dict[int, str] = {}

    for i, step in enumerate(queue):
        if not isinstance(step, dict):
            raise ValueError(f"Queue step {i} is not a dict: {step}")
        if "step" not in step or "tool" not in step:
            raise ValueError(f"Queue step {i} missing 'step' or 'tool' key: {step}")

        current_idx  = step["step"]
        current_tool = step["tool"]
        args         = step.get("args", {})

        # Check required arguments are present for known tools
        _REQUIRED_ARGS: dict[str, list[str]] = {
            "get_unique_values":      ["module", "field"],
            "count_records":          ["module"],
            "count_records_multi":    ["module", "condition_field_1", "condition_value_1",
                                       "condition_field_2", "condition_value_2"],
            "sum_values":             ["module", "field"],
            "get_average":            ["module", "field"],
            "get_minimum":            ["module", "field"],
            "get_maximum":            ["module", "field"],
            "calculate_time_between": ["module", "start_field", "end_field"],
            "group_by_and_count":     ["module", "group_field"],
            "group_by_and_aggregate": ["module", "group_field", "agg_field", "operation"],
            "get_record_fields":      ["module"],
            "sort_and_limit":         ["data"],
            "join_records":           ["module_a", "module_b", "join_field"],
            "do_math":                ["operation", "a"],
        }
        required = _REQUIRED_ARGS.get(current_tool, [])
        for req in required:
            if req not in args:
                raise ValueError(
                    f"Queue step {i} ({current_tool}): missing required argument '{req}'. "
                    f"Args provided: {list(args.keys())}"
                )

        # Validate all arg values that are $step_N.key references
        for arg_name, arg_val in args.items():
            refs = arg_val if isinstance(arg_val, list) else [arg_val]
            for ref in refs:
                if not isinstance(ref, str) or not ref.startswith("$step_"):
                    continue  # plain value — skip

                inner = ref[1:]                    # "step_2.count"
                parts = inner.split(".", 1)
                ref_idx_str = parts[0][len("step_"):]  # "2"

                # (a) The referenced step must already exist before this one
                try:
                    ref_idx = int(ref_idx_str)
                except ValueError:
                    raise ValueError(
                        f"Queue step {i} ({current_tool}) arg '{arg_name}': "
                        f"invalid step reference '{ref}' — cannot parse step index."
                    )

                if ref_idx not in step_tool_map:
                    raise ValueError(
                        f"Queue step {i} ({current_tool}) arg '{arg_name}': "
                        f"'{ref}' references step {ref_idx} which does not exist "
                        f"before step {current_idx}. Steps defined so far: "
                        f"{sorted(step_tool_map.keys())}"
                    )

                # (b) The key must exist in the referenced tool's OUTPUT KEYS
                if len(parts) == 2:
                    ref_key      = parts[1]              # "stats.average" or "count"
                    root_key     = ref_key.split(".")[0]  # "stats" or "count"
                    ref_tool     = step_tool_map[ref_idx]
                    allowed_keys = _TOOL_OUTPUT_KEYS.get(ref_tool, set())
                    if allowed_keys and root_key not in allowed_keys:
                        raise ValueError(
                            f"Queue step {i} ({current_tool}) arg '{arg_name}': "
                            f"'{ref}' uses key '{root_key}' but tool '{ref_tool}' "
                            f"only outputs: {sorted(allowed_keys)}"
                        )

        step_tool_map[current_idx] = current_tool

    last_tool = queue[-1].get("tool")
    if last_tool != "final_answer_tool":
        raise ValueError(
            f"Last step must be 'final_answer_tool', got '{last_tool}'."
        )


# =============================================================================
# PUBLIC API
# =============================================================================

def run_execution(
    question:         str,
    filter_fields:    dict,
    modules:          list[str],
    filtered_records: dict,
    thought_callback: callable = None,
    progress_callback: callable = None,
    response_format:  str  = "PLAIN_TEXT",
    user_specified:   bool = False,
) -> dict:
    """
    Main entry point for the execution layer.

    Phase 1 — Planning (LLM called once):
      Receives: question + schema (field names only — NO actual data rows).
      Returns: a complete queue of tool steps as JSON.

    Phase 2 — Execution (no LLM):
      Executes each step using tools directly.
      Tools read filtered_records from the Execution Context.
      No data goes back to the LLM.

    Args:
        question:         FM analytics question text
        filter_fields:    Schema metadata { module: { field: description } }
        modules:          Module names e.g. ["ppm", "bdm"]
        filtered_records: Actual data rows per module (never sent to LLM)

    Returns:
        ExecutionResult:
        {
          "queue":        list of planned steps,
          "step_results": { "step_0": {tool output}, "step_1": {tool output}, ... },
          "queue_total":  int,
          "tools_called": int,
          "error_count":  int,
          "status":       "COMPLETE" | "PARTIAL" | "FAILED",
          "latency":      {"llm_time": float, "execution_time": float, "total_time": float}
        }

        COMPLETE — all steps ran with zero errors
        PARTIAL  — all steps ran but ≥1 intermediate step errored; answer may still be useful
        FAILED   — final_answer_tool itself errored; no usable answer
    """
    start_total = time.perf_counter()

    # ── Phase 1: Plan the queue (LLM called once, streaming) ──────────────────
    log_question(question, modules)

    schema_text = (
        json.dumps(filter_fields, indent=2)
        if filter_fields
        else "No column definitions provided."
    )
    enum_text = get_enum_block(modules)

    human_message = (
        f"Question: {question}\n\n"
        f"Available modules: {modules}\n\n"
        f"Column definitions per module:\n{schema_text}\n\n"
        f"Allowed enum values (use these EXACTLY as filter_value — no paraphrasing):\n{enum_text}\n\n"
        f"Intended presentation format: {response_format}\n\n"
        f"Produce the execution queue as a JSON array."
    )

    config = types.GenerateContentConfig(
        system_instruction = PLANNER_SYSTEM_PROMPT,
        response_mime_type = "application/json",
        temperature        = 1,
        thinking_config    = types.ThinkingConfig(
            thinking_budget  = 512,
            include_thoughts = True,
        ),
    )

    start_llm = time.perf_counter()
    thought, raw_json, usage = stream_with_thoughts(
        contents   = [{"role": "user", "parts": [{"text": human_message}]}],
        config     = config,
        thought_cb = thought_callback,
    )
    llm_time = time.perf_counter() - start_llm

    logger.info("[Execution Agent] tokens  : input=%d output=%d total=%d",
                usage.get("input_tokens", 0), usage.get("output_tokens", 0), usage.get("total_tokens", 0))
    logger.info("[Execution Agent] latency : llm=%.2fs", llm_time)

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        logger.error("[Execution Agent] JSON parse failed: %s\nRaw: %.300s", exc, raw_json)
        raise ValueError(f"Execution Agent returned invalid JSON. Error: {exc}") from exc

    # ── Coerce: model sometimes wraps the array in a dict ────────────────────
    # e.g. {"queue": [...]} or {"steps": [...]} instead of [...]
    if isinstance(parsed, dict):
        for wrap_key in ("queue", "steps", "plan", "execution_plan", "tool_calls", "tools"):
            if wrap_key in parsed and isinstance(parsed[wrap_key], list):
                logger.info("[Execution Agent] unwrapped queue from key '%s'", wrap_key)
                parsed = parsed[wrap_key]
                break
        else:
            # Last resort: take the first list value found
            for v in parsed.values():
                if isinstance(v, list):
                    parsed = v
                    break

    if not isinstance(parsed, list):
        raise ValueError(f"Execution Agent queue is not a list. Got: {type(parsed).__name__}")

    # ── Coerce step args: convert None / non-string scalars to strings ────────
    for step in parsed:
        if isinstance(step, dict):
            args = step.get("args") or {}
            for k, v in args.items():
                if v is None:
                    args[k] = ""                      # None → empty string
                elif not isinstance(v, (str, list)):
                    args[k] = str(v)                  # int/float → string
            step["args"] = args

    queue = parsed

    _validate_queue(queue)
    log_queue(queue)

    # ── Phase 2: Execute the queue (no LLM) ────────────────────────────────
    start_exec = time.perf_counter()
    result = run_queue(queue, filtered_records, progress_callback)
    execution_time = time.perf_counter() - start_exec
    
    total_time = time.perf_counter() - start_total
    
    result["latency"] = {
        "llm_time": round(llm_time, 2),
        "execution_time": round(execution_time, 2),
        "total_time": round(total_time, 2),
    }

    # ── Log completion ──────────────────────────────────────────────────────
    step_results = result.get("step_results", {})
    last_key     = f"step_{len(queue) - 1}"
    last_output  = step_results.get(last_key, {})
    final_value  = last_output.get("final_value", last_output)

    log_completion(
        status       = result["status"],
        tools_called = result["tools_called"],
        queue_total  = result["queue_total"],
        error_count  = result.get("error_count", 0),
        final_value  = final_value,
        latency      = result["latency"],
    )

    # Build context for the Formatting Agent and attach to result
    formatting_context = build_formatting_context(
        result,
        response_format  = response_format,
        suggested_format = response_format,
        user_specified   = user_specified,
    )
    result["formatting_context"] = formatting_context
    result["thought"] = thought

    return result
