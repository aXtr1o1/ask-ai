"""
Analysis Agent

Receives the Understanding Agent's query summary and the pre-identified
modules. Decides which fields to retrieve and which values to filter on
for each module.

Thought tokens are streamed in real-time via thought_callback.
"""
import logging
import time

from google.genai import types

from app.api.advance.analysis.schemas import AnalysisOutput
from app.api.advance.analysis.prompt import get_system_prompt
from app.api.advance.analysis.metadata import MODULE_SCHEMAS, get_metadata
from app.api.advance.gemini_stream import stream_with_thoughts

logger = logging.getLogger("advance.analysis")


# =============================================================================
# MAIN FUNCTION
# =============================================================================
def analyze_query(
    query_summary:   str,
    modules:         list[str],
    thought_callback = None,
) -> dict:
    """
    Run the Analysis Agent on a cleaned query summary.

    thought_callback(text_chunk: str): called with each thought token as it
    arrives from the API. Pass None for batch / test-pipeline mode.

    Returns:
        {
            "reasoning":     str,
            "modules":       [list of validated module names],
            "filter_fields": { module: { field: description } },
            "filter_values": { module: { field: value } },
            "thought":       str,
            "latency":       { llm_time, total_time },
        }
    """
    start_total = time.perf_counter()

    # ── Metadata summary log ──────────────────────────────────────────────────
    loaded_meta  = get_metadata(modules)
    meta_summary = ", ".join(
        f"{mod}({len(fields)} fields)" for mod, fields in loaded_meta.items()
    )
    logger.info("[Analysis Agent] metadata loaded — %s", meta_summary)

    system_prompt = get_system_prompt(modules)

    config = types.GenerateContentConfig(
        system_instruction = system_prompt,
        response_mime_type = "application/json",
        temperature        = 1,
        thinking_config    = types.ThinkingConfig(
            thinking_budget  = 512,
            include_thoughts = True,
        ),
    )

    contents = [{"role": "user", "parts": [{"text": query_summary}]}]

    # ── Stream ────────────────────────────────────────────────────────────────
    start_llm = time.perf_counter()
    thought, json_text, usage = stream_with_thoughts(
        contents   = contents,
        config     = config,
        thought_cb = thought_callback,
    )
    llm_time = time.perf_counter() - start_llm

    # ── Pre-coerce JSON before Pydantic validates ─────────────────────────────
    # The model sometimes returns filter_fields as a list ['F1','F2'] instead
    # of a dict {'F1': 'desc', 'F2': 'desc'}, and filter_values can have null values.
    # Fix both before handing to Pydantic so we never get a ValidationError here.
    import json as _json
    try:
        raw_dict = _json.loads(json_text)
    except _json.JSONDecodeError as exc:
        logger.error("[Analysis Agent] JSON decode failed: %s\nRaw: %.300s", exc, json_text)
        raise ValueError(f"Analysis Agent returned invalid JSON: {exc}") from exc

    # Coerce filter_fields: list → dict with empty description
    for mod, fields in (raw_dict.get("filter_fields") or {}).items():
        if isinstance(fields, list):
            raw_dict["filter_fields"][mod] = {f: "" for f in fields if isinstance(f, str)}

    # Coerce filter_values: drop null/non-string values
    for mod, vals in (raw_dict.get("filter_values") or {}).items():
        if isinstance(vals, dict):
            raw_dict["filter_values"][mod] = {
                k: str(v) for k, v in vals.items() if v is not None
            }

    try:
        response = AnalysisOutput.model_validate(raw_dict)
    except Exception as exc:
        logger.error("[Analysis Agent] schema validation failed: %s\nRaw: %.300s", exc, json_text)
        raise ValueError(f"Analysis Agent returned unparseable JSON: {exc}") from exc

    logger.info("[Analysis Agent] tokens  : input=%d output=%d total=%d",
                usage.get("input_tokens", 0), usage.get("output_tokens", 0), usage.get("total_tokens", 0))
    logger.info("[Analysis Agent] latency : llm=%.2fs", llm_time)

    # ── Validate — strip hallucinated modules / fields ────────────────────────
    valid_modules = [m for m in response.modules if m in MODULE_SCHEMAS]

    valid_filter_fields: dict[str, dict[str, str]] = {}
    for mod in valid_modules:
        valid_filter_fields[mod] = {
            field: desc
            for field, desc in response.filter_fields.get(mod, {}).items()
            if field in MODULE_SCHEMAS[mod]
        }

    valid_filter_values: dict[str, dict[str, str]] = {}
    for mod in valid_modules:
        valid_filter_values[mod] = {
            field: val
            for field, val in response.filter_values.get(mod, {}).items()
            if field in MODULE_SCHEMAS.get(mod, {})
        }

    total_time = time.perf_counter() - start_total
    logger.info("[Analysis Agent] latency : total=%.2fs", total_time)
    logger.info("[Analysis Agent] modules selected : %s", valid_modules)
    logger.info("[Analysis Agent] limit : %s", response.limit)
    for mod in valid_modules:
        ff = list(valid_filter_fields.get(mod, {}).keys())
        fv = valid_filter_values.get(mod, {})
        logger.info("[Analysis Agent] [%s] filter_fields : %s", mod, ff)
        logger.info("[Analysis Agent] [%s] filter_values : %s", mod, fv)

    return {
        "reasoning":     response.reasoning,
        "limit":         response.limit,
        "modules":       valid_modules,
        "filter_fields": valid_filter_fields,
        "filter_values": valid_filter_values,
        "thought":       thought,
        "latency": {
            "llm_time":   round(llm_time,   2),
            "total_time": round(total_time, 2),
        },
    }
