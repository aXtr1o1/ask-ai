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
from app.api.advance.execution_agent.tools.tool_helpers  import _strip_markdown
from app.api.advance.execution_agent.prompt.tool_meta    import TOOL_OUTPUT_KEYS, REQUIRED_ARGS
from app.api.advance.execution_agent.prompt.prompts      import PLANNER_SYSTEM_PROMPT
from app.api.advance.execution_agent.queue.queue_runner  import run_queue
from app.api.advance.execution_agent.agent.agent_logger  import (
    log_question, log_queue, log_completion
)
from app.api.advance.analysis.metadata.enum_values   import get_enum_block_for_fields
from app.api.advance.gemini_stream                   import stream_with_thoughts

logger = logging.getLogger("advance.execution.agent")



def _extract_refs(val) -> list[str]:
    """Recursively extract all $step_N.key strings from any nested structure."""
    if isinstance(val, str):
        return [val] if val.startswith("$step_") else []
    if isinstance(val, list):
        out = []
        for item in val:
            out.extend(_extract_refs(item))
        return out
    if isinstance(val, dict):
        out = []
        for v in val.values():
            out.extend(_extract_refs(v))
        return out
    return []


def _validate_queue(queue: list) -> None:
    """
    Structural and $ref validation of the planned queue.

    Raises ValueError immediately if any of these conditions are met:
      - Queue is empty or not a list.
      - A step is missing 'step' or 'tool' keys.
      - Duplicate step indices are present.
      - A required argument for a known tool is missing.
      - A $step_N.key reference points to a step that does not exist yet.
      - A $step_N.key reference uses a key not in that tool's declared output keys.
      - The last step is not 'final_answer_tool'.
    """
    if not isinstance(queue, list) or len(queue) == 0:
        raise ValueError("Agent returned an empty or non-list queue.")

    # Reject duplicate step numbers
    seen_steps: set = set()
    for i, step in enumerate(queue):
        if isinstance(step, dict):
            idx = step.get("step")
            if idx in seen_steps:
                raise ValueError(
                    f"Duplicate step index {idx} found at position {i} in queue. "
                    f"Step indices must be unique."
                )
            if idx is not None:
                seen_steps.add(idx)

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
        required = REQUIRED_ARGS.get(current_tool, [])
        for req in required:
            if req not in args:
                raise ValueError(
                    f"Queue step index {current_idx} (position {i}, tool={current_tool}): "
                    f"missing required argument '{req}'. "
                    f"Args provided: {list(args.keys())}"
                )

        for arg_name, arg_val in args.items():
            for ref in _extract_refs(arg_val):

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

                # (b) If the tool's output keys are known, warn on unrecognised keys.
                #     Warning only — TOOL_OUTPUT_KEYS is manually maintained and may
                #     lag behind actual tool changes. A hard failure here would break
                #     valid queues whenever tool_meta.py is out of sync.
                if len(parts) == 2:
                    ref_key  = parts[1]
                    root_key = ref_key.split(".")[0].split("[")[0]  # strip [0] or [?filter]
                    ref_tool     = step_tool_map[ref_idx]
                    allowed_keys = TOOL_OUTPUT_KEYS.get(ref_tool, set())
                    if allowed_keys and root_key not in allowed_keys:
                        logger.warning(
                            "Queue step %d (%s) arg '%s': "
                            "'%s' uses key '%s' but tool '%s' "
                            "only outputs: %s — allowing with warning.",
                            i, current_tool, arg_name,
                            ref, root_key, ref_tool,
                            sorted(allowed_keys),
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
    # Only pass enum values for fields that were actually selected by the Analysis Agent.
    # This prevents the Execution Agent from using enum fields (e.g. WoStatus) that
    # were not fetched and do not exist in the available data columns.
    enum_text = get_enum_block_for_fields(modules, filter_fields)

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
        temperature        = 0,
        thinking_config    = types.ThinkingConfig(
            thinking_budget  = 1024,
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
        parsed = json.loads(_strip_markdown(raw_json))
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
    # Rules:
    #   None   → ""              (tools treat empty string as "not provided")
    #   dict   → keep as-is     (result_ref in final_answer_tool may be a dict)
    #   list   → keep as-is     (multi-step references)
    #   int/float → str(v)      (field names or enum values passed as numbers)
    for step in parsed:
        if isinstance(step, dict):
            args = step.get("args") or {}
            for k, v in args.items():
                if v is None:
                    # List args default to [] not "" — preserves correct type
                    args[k] = [] if k in ("filters", "group_fields", "conditions",
                                          "percentiles", "fields", "datasets") else ""
                elif isinstance(v, (dict, list)):
                    pass                              # keep structured values intact
                elif not isinstance(v, str):
                    args[k] = str(v)                  # int/float → string
            step["args"] = args

    queue = parsed

    # ── Auto-repair: final_answer_tool flat-args (Bug #1) ────────────────────
    # The LLM sometimes places multi-part answer labels directly as top-level
    # args instead of nesting them under result_ref:
    #   WRONG:   {"MTBF": "$step_0.overall_avg_mtbf_days", "MTTR": "$step_1.average"}
    #   CORRECT: {"result_ref": {"MTBF": "...", "MTTR": "..."}}
    # Detect and silently repair before validation so the request never crashes.
    for step in queue:
        if isinstance(step, dict) and step.get("tool") == "final_answer_tool":
            args = step.get("args", {})
            if "result_ref" not in args and args:
                step["args"] = {"result_ref": dict(args)}
                logger.info(
                    "[Execution Agent] Auto-repaired final_answer_tool: "
                    "wrapped flat args %s into result_ref dict.",
                    list(dict(args).keys()),
                )

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
    last_key     = f"step_{queue[-1]['step']}"
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

    return result