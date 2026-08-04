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
from app.api.advance.analysis.mandatory_fields import build_query_field_context

logger = logging.getLogger("advance.analysis")


# =============================================================================
# MAIN FUNCTION
# =============================================================================
def analyze_query(
    query_summary:   str,
    modules:         list[str],
    thought_callback = None,
    last_db_turn:    dict | None = None,
) -> dict:
    """
    Run the Analysis Agent on a cleaned query summary.

    thought_callback(text_chunk: str): called with each thought token as it
    arrives from the API. Pass None for batch / test-pipeline mode.

    last_db_turn: the most recent db_query turn from ConversationMemory.
    When provided, a compact [PREVIOUS QUERY CONTEXT] block is prepended to
    the user message so the Analysis Agent can inherit filters for follow-ups.

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

    # ── Build user message — inject previous context block if available ────────
    user_message = query_summary

    if last_db_turn and last_db_turn.get("modules"):
        prev_summary      = last_db_turn.get("query_summary", "")
        prev_modules      = ", ".join(last_db_turn.get("modules", []))
        prev_filter_fields = last_db_turn.get("filter_fields", {})
        prev_filter_values = last_db_turn.get("filter_values", {})

        # Compact single-line representation of fields and values
        fields_parts = []
        for mod, fields in prev_filter_fields.items():
            if isinstance(fields, dict) and fields:
                fields_parts.append(f"{mod}: [{', '.join(fields.keys())}]")
        fields_str = " | ".join(fields_parts) or "none"

        values_parts = []
        for mod, vals in prev_filter_values.items():
            if isinstance(vals, dict) and vals:
                pairs = ", ".join(f"{k}={v}" for k, v in vals.items())
                values_parts.append(f"{mod}: {{{pairs}}}")
        values_str = " | ".join(values_parts) or "none"

        context_block = (
            f"[PREVIOUS QUERY CONTEXT — use only if current query is a follow-up or refinement]\n"
            f"Query was about : {prev_summary}\n"
            f"Modules used    : {prev_modules}\n"
            f"Fields retrieved: {fields_str}\n"
            f"Filters applied : {values_str}\n"
            f"{'─' * 60}\n\n"
            f"Current query:\n{query_summary}"
        )
        user_message = context_block
        logger.info("[Analysis Agent] previous db_query context injected — modules=%s", prev_modules)
    else:
        logger.info("[Analysis Agent] no previous db_query context — fresh query")

    contents = [{"role": "user", "parts": [{"text": user_message}]}]


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

    # ── Coerce parallel arrays ────────────────────────────────────────────────
    # Sometimes the LLM returns filter_fields: ["StatusName"] and filter_values: ["Offline"]
    # Detect parallel lists of strings and zip them into dicts before normal coercion.
    raw_ff = raw_dict.get("filter_fields")
    raw_fv = raw_dict.get("filter_values")
    
    if isinstance(raw_ff, list) and isinstance(raw_fv, list) and len(raw_ff) == len(raw_fv):
        all_ff_str = all(isinstance(x, str) for x in raw_ff)
        all_fv_str = all(isinstance(x, str) for x in raw_fv)
        if all_ff_str and all_fv_str and len(raw_ff) > 0:
            mod_key = modules[0] if modules else "unknown"

            raw_dict["filter_fields"] = {mod_key: {f: "" for f in raw_ff}}
            raw_dict["filter_values"] = {mod_key: {k: v for k, v in zip(raw_ff, raw_fv)}}
            logger.warning("[Analysis Agent] filter_fields and filter_values were parallel arrays — zipped into dicts")

            # Re-fetch for the rest of the coercion logic
            raw_ff = raw_dict.get("filter_fields")
            raw_fv = raw_dict.get("filter_values")

    # ── Coerce filter_fields ───────────────────────────────────────────────────
    # The LLM can return filter_fields in three shapes:

    if isinstance(raw_ff, list):
        # Shape C: flat list — wrap under the first module from Understanding Agent
        mod_key = modules[0] if modules else "unknown"
        raw_dict["filter_fields"] = {
            mod_key: {f: "" for f in raw_ff if isinstance(f, str)}
        }
        logger.warning(
            "[Analysis Agent] filter_fields was a flat list — wrapped under module '%s'", mod_key
        )
    elif isinstance(raw_ff, dict):
        # Shape B: per-module list → convert to dict
        for mod, fields in raw_ff.items():
            if isinstance(fields, list):
                raw_dict["filter_fields"][mod] = {f: "" for f in fields if isinstance(f, str)}
    else:
        # None or unexpected type — reset to empty
        raw_dict["filter_fields"] = {}

    # ── Coerce filter_values ───────────────────────────────────────────────────
    # The LLM can return filter_values as a flat dict {"WoStatus": "Open"} instead
    # of nested {"bdm": {"WoStatus": "Open"}}. Detect and wrap it.
    raw_fv = raw_dict.get("filter_values")

    if isinstance(raw_fv, dict):
        # Check each module's value — it can be:
        #   Shape A (correct):    {"bdm": {"WoStatus": "Open"}}
        #   Shape B (flat dict):  {"WoStatus": "Open"}          ← wrap under module
        #   Shape C (list-dicts): {"bdm": [{"ResponseTAT": "NROT"}, {"ResolutionTAT": "SNA"}]}

        # Detect Shape B: all values are strings/None (flat, not nested)
        all_flat = all(not isinstance(v, dict) and not isinstance(v, list) for v in raw_fv.values())
        if all_flat and raw_fv:
            mod_key = modules[0] if modules else "unknown"
            raw_dict["filter_values"] = {mod_key: raw_fv}
            logger.warning(
                "[Analysis Agent] filter_values was flat dict — wrapped under module '%s'", mod_key
            )
        else:
            # Shape A or Shape C — normalise per module
            for mod, vals in list(raw_fv.items()):
                if isinstance(vals, list):
                    # Shape C: list of dicts → merge into one dict
                    merged: dict = {}
                    for item in vals:
                        if isinstance(item, dict):
                            merged.update(item)
                    raw_dict["filter_values"][mod] = {
                        k: v if isinstance(v, list) else str(v) for k, v in merged.items() if v is not None
                    }
                    logger.warning(
                        "[Analysis Agent] filter_values[%s] was list-of-dicts — merged into dict", mod
                    )
                elif isinstance(vals, dict):
                    # Shape A (correct): drop null values
                    raw_dict["filter_values"][mod] = {
                        k: v if isinstance(v, list) else str(v) for k, v in vals.items() if v is not None
                    }
    elif isinstance(raw_fv, list):
        # Shape D: flat list of dicts (missing module wrapper) -> [{"StatusName": "Offline"}]
        merged: dict = {}
        for item in raw_fv:
            if isinstance(item, dict):
                merged.update(item)
        if merged:
            mod_key = modules[0] if modules else "unknown"
            raw_dict["filter_values"] = {
                mod_key: {k: v if isinstance(v, list) else str(v) for k, v in merged.items() if v is not None}
            }
            logger.warning(
                "[Analysis Agent] filter_values was flat list of dicts — wrapped under module '%s'", mod_key
            )
        else:
            raw_dict["filter_values"] = {}
    else:
        raw_dict["filter_values"] = {}




    try:
        response = AnalysisOutput.model_validate(raw_dict)
    except Exception as exc:
        logger.error("[Analysis Agent] schema validation failed: %s\nRaw: %.300s", exc, json_text)
        raise ValueError(f"Analysis Agent returned unparseable JSON: {exc}") from exc

    logger.info("[Analysis Agent] tokens  : input=%d output=%d total=%d",
                usage.get("input_tokens", 0), usage.get("output_tokens", 0), usage.get("total_tokens", 0))
    logger.info("[Analysis Agent] latency : llm=%.2fs", llm_time)

    # ── Use modules from Understanding Agent — Analysis Agent does not predict modules ──
    valid_modules = [m for m in modules if m in MODULE_SCHEMAS]

    # Map lowercase field names to actual schema field names
    schema_fields_lower = {
        mod: {k.lower(): k for k in MODULE_SCHEMAS.get(mod, {})}
        for mod in valid_modules
    }

    valid_filter_fields: dict[str, dict[str, str]] = {}
    for mod in valid_modules:
        valid_filter_fields[mod] = {}
        extracted_fields = []
        for field, desc in response.filter_fields.get(mod, {}).items():
            actual_field = schema_fields_lower[mod].get(field.lower())
            if actual_field:
                valid_filter_fields[mod][actual_field] = desc
                extracted_fields.append(actual_field)
                
        try:
            context = build_query_field_context(mod, extracted_fields)
            for m_field in context["mandatory_fields"]:
                if m_field not in valid_filter_fields[mod]:
                    valid_filter_fields[mod][m_field] = "Mandatory field"
        except KeyError:
            pass

    valid_filter_values: dict[str, dict[str, str | list[str]]] = {}
    for mod in valid_modules:
        valid_filter_values[mod] = {}
        for field, val in response.filter_values.get(mod, {}).items():
            actual_field = schema_fields_lower[mod].get(field.lower())
            if actual_field:
                valid_filter_values[mod][actual_field] = val

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
