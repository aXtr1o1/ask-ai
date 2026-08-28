"""
Field Lineage Validator — static, pre-execution check that a step only uses
field names that actually exist in whatever it is reading from.

Why this exists:
  A field that exists on the original module does not necessarily exist on a
  prior step's own output. Several tools return a NARROWED or TRANSFORMED
  list — e.g. calculate_mtbf's "mtbf_by_asset" contains only the asset field,
  failure_count, and mtbf_days, even though the module it read from (e.g. bdm)
  has dozens of other columns. A planned step that chains from that narrowed
  list (via a "data": "$step_N.key" argument) but asks for a field that was
  never in it — e.g. grouping by a field that only existed on the original
  module — fails at execution time with a real but avoidable error.

  This module computes, for every step in a queue, exactly which field names
  its own list-valued outputs will contain — using only that step's own
  literal args (never real data, never an LLM call) — and checks every later
  step's field-referencing args against the actual schema of whatever list it
  is chaining from, not the schema of the module that data may have
  originally come from.

Scope:
  Only checks what is STATICALLY knowable from the plan's own literal args.
  A tool/output combination whose exact field set can't be determined this
  way (e.g. get_record_fields with an empty "fields" — meaning "every column",
  which isn't enumerable without touching real data) resolves to "unknown"
  and is silently skipped — never flagged. A false rejection of a valid plan
  is a worse failure than missing a rare invalid one, so every kind of
  ambiguity here defers to "allow it" rather than "block it".

Public API:
  validate_field_lineage(queue) -> None    — raises ValueError on the first
                                              statically-provable violation.
"""
from __future__ import annotations

import logging

from app.api.advance.execution_agent.prompt.tool_meta import TOOL_LIST_OUTPUT_SCHEMA
from app.api.advance.Understanding_Agent.module_fields import MODULE_FIELDS

logger = logging.getLogger("advance.execution.lineage")


# =============================================================================
# TOOL FIELD CONSUMERS
# For every tool that can read a prior step's own output list (via a "data"-
# style argument) instead of a raw module, declares which of its OTHER args
# name a field that must therefore exist in that list. Nothing here is tied
# to any particular field name — only to argument names, which are fixed by
# each tool's own signature.
# =============================================================================
TOOL_FIELD_CONSUMERS: dict[str, dict] = {
    "group_by_and_aggregate": {
        "data_arg": "data", "field_args": ["group_fields", "agg_field"], "filters_arg": "filters",
    },
    "sort_and_limit": {
        "data_arg": "data", "field_args": ["sort_by"],
    },
    "flag_by_threshold": {
        "data_arg": "data", "field_args": ["field", "group_fields", "label_field"], "filters_arg": "filters",
    },
    "calculate_percentile": {
        "data_arg": "data", "field_args": ["field"], "filters_arg": "filters",
    },
    "forecast_linear": {
        "data_arg": "data", "field_args": ["value_key", "label_key"],
    },
}


# =============================================================================
# LITERAL VALUE HELPERS
# =============================================================================

def _is_ref(val) -> bool:
    return isinstance(val, str) and val.startswith("$step_")


def _ref_step_key(ref: str) -> "str | None":
    inner = ref[1:]
    parts = inner.split(".", 1)
    if not parts[0].startswith("step_"):
        return None
    return parts[0]


def _ref_root_key(ref: str) -> "str | None":
    inner = ref[1:]
    parts = inner.split(".", 1)
    if len(parts) < 2:
        return None
    return parts[1].split(".")[0].split("[")[0]


def _literal_str(v) -> "str | None":
    """Return v if it's a non-empty literal string (not a $step_N reference)."""
    if isinstance(v, str) and v.strip() and not _is_ref(v):
        return v
    return None


def _literal_str_list(v) -> "list[str] | None":
    """Return v if it's a non-empty list of plain literal strings."""
    if isinstance(v, list) and v and all(isinstance(x, str) and not _is_ref(x) for x in v):
        return v
    return None


# =============================================================================
# SCHEMA RESOLUTION
# =============================================================================

def resolve_ref_schema(ref, step_schemas: dict) -> "set[str] | None":
    """Resolve a '$step_N.key' reference to the field set of that step's output
    list, or None when the referenced step/key isn't tracked or isn't known.
    """
    if not _is_ref(ref):
        return None
    step_key = _ref_step_key(ref)
    root_key = _ref_root_key(ref)
    if step_key is None or root_key is None:
        return None
    return step_schemas.get(step_key, {}).get(root_key)


def _merge_and_score_schema(args: dict, step_schemas: dict) -> "set[str] | None":
    """merge_and_score's 'ranked' output: group_key field(s) + '<label>_score'
    per dataset + 'composite_score' — derived entirely from this step's own
    group_key and datasets[].label args, never from data.
    """
    datasets = args.get("datasets")
    group_key = args.get("group_key")
    if not isinstance(datasets, list) or not datasets:
        return None

    if isinstance(group_key, list):
        group_key_fields = [g for g in group_key if isinstance(g, str)]
    elif isinstance(group_key, str) and group_key:
        group_key_fields = [group_key]
    else:
        return None
    if not group_key_fields:
        return None

    fields = set(group_key_fields)
    for ds in datasets:
        if not isinstance(ds, dict):
            return None
        label = _literal_str(ds.get("label"))
        if not label:
            return None
        fields.add(f"{label}_score")
    fields.add("composite_score")
    return fields


def compute_step_output_schema(tool_name: str, args: dict, step_schemas: dict) -> dict:
    """Compute {output_key: field_set_or_None} for every list-valued output
    this step's tool produces, using only this step's own literal args.
    """
    specs = TOOL_LIST_OUTPUT_SCHEMA.get(tool_name, {})
    out: dict[str, "set[str] | None"] = {}

    for out_key, spec in specs.items():
        if "fixed" in spec:
            out[out_key] = set(spec["fixed"])

        elif "group_arg" in spec:
            fields = _literal_str_list(args.get(spec["group_arg"]))
            out[out_key] = (set(fields) | set(spec.get("extra", []))) if fields is not None else None

        elif "scalar_arg" in spec:
            val = _literal_str(args.get(spec["scalar_arg"])) or spec.get("default")
            out[out_key] = ({val} | set(spec.get("extra", []))) if val else None

        elif "list_arg" in spec:
            fields = _literal_str_list(args.get(spec["list_arg"]))
            out[out_key] = (set(fields) | set(spec.get("always", []))) if fields is not None else None

        elif "module_arg" in spec:
            mod = _literal_str(args.get(spec["module_arg"]))
            base = MODULE_FIELDS.get(mod) if mod else None
            out[out_key] = (set(base) | set(spec.get("extra", []))) if base is not None else None

        elif "label_and_scalar" in spec:
            label_arg, scalar_arg = spec["label_and_scalar"]
            label = _literal_str(args.get(label_arg))
            if label:
                fields = {label}
                scalar = _literal_str(args.get(scalar_arg))
                if scalar:
                    fields.add(scalar)
                out[out_key] = fields
            else:
                out[out_key] = None  # no label_field → full passthrough, not enumerable here

        elif "passthrough_arg" in spec:
            ref = args.get(spec["passthrough_arg"])
            out[out_key] = resolve_ref_schema(ref, step_schemas)

        elif spec.get("dynamic_merge_score"):
            out[out_key] = _merge_and_score_schema(args, step_schemas)

    return out


# =============================================================================
# VIOLATION FORMATTING
# =============================================================================

def _format_violation(field_names: list, ref: str, available: "set[str] | None") -> str:
    unique = list(dict.fromkeys(field_names))  # de-dupe, preserve order
    plural = len(unique) > 1
    quoted = ", ".join(repr(f) for f in unique)
    field_part = (
        f"Fields {quoted} are not available" if plural else f"Field {quoted} is not available"
    )
    avail_text = ", ".join(sorted(available)) if available else "(none)"
    return (
        "Invalid data dependency:\n"
        f"{field_part} in '{ref}'.\n\n"
        "Available fields:\n"
        f"{avail_text}\n\n"
        "The field may exist in the original module, but it was not preserved\n"
        "by the referenced upstream tool."
    )


# =============================================================================
# CONSUMPTION-SIDE CHECKS
# =============================================================================

def _names_from(val) -> list:
    if isinstance(val, list):
        return _literal_str_list(val) or []
    s = _literal_str(val)
    return [s] if s else []


def _check_consumer_fields(tool_name: str, args: dict, step_schemas: dict) -> list:
    """Return violation messages for this step's own field-referencing args
    when they consume a known, statically-resolved upstream list schema.
    """
    violations: list = []
    spec = TOOL_FIELD_CONSUMERS.get(tool_name)

    if spec:
        data_ref = args.get(spec["data_arg"])
        if _is_ref(data_ref):
            schema = resolve_ref_schema(data_ref, step_schemas)
            if schema is not None:
                schema_lower = {f.lower() for f in schema}
                missing: list = []

                for field_arg in spec.get("field_args", []):
                    for name in _names_from(args.get(field_arg)):
                        if name.lower() not in schema_lower:
                            missing.append(name)

                filters_arg = spec.get("filters_arg")
                if filters_arg:
                    for filt in (args.get(filters_arg) or []):
                        if isinstance(filt, dict):
                            f = _literal_str(filt.get("field"))
                            if f and f.lower() not in schema_lower:
                                missing.append(f)

                if missing:
                    violations.append(_format_violation(missing, data_ref, schema))

    if tool_name == "merge_and_score":
        violations.extend(_check_merge_and_score_consumers(args, step_schemas))

    return violations


def _check_merge_and_score_consumers(args: dict, step_schemas: dict) -> list:
    """merge_and_score aligns rows across datasets by group_key — a dataset
    whose referenced step output doesn't contain group_key silently drops
    every row from that dataset (no crash, just wrong/incomplete results),
    which is exactly the kind of silent failure worth catching before it runs.
    value_key is deliberately NOT checked here: the tool already falls back
    to a generic "count"/"value" metric name at runtime when value_key isn't
    found, so a mismatch there is tolerated by design, not a defect.
    """
    violations: list = []
    datasets = args.get("datasets")
    group_key = args.get("group_key")
    if not isinstance(datasets, list):
        return violations

    if isinstance(group_key, list):
        group_key_fields = [g for g in group_key if isinstance(g, str)]
    elif isinstance(group_key, str) and group_key:
        group_key_fields = [group_key]
    else:
        return violations

    for ds in datasets:
        if not isinstance(ds, dict):
            continue
        data_ref = ds.get("data")
        if not _is_ref(data_ref):
            continue
        schema = resolve_ref_schema(data_ref, step_schemas)
        if schema is None:
            continue
        schema_lower = {f.lower() for f in schema}
        missing = [f for f in group_key_fields if f.lower() not in schema_lower]
        if missing:
            violations.append(_format_violation(missing, data_ref, schema))

    return violations


# =============================================================================
# PUBLIC API
# =============================================================================

def validate_field_lineage(queue: list) -> None:
    """Walk the queue in plan order, tracking each step's own output-list
    schema, and reject the first step whose field-referencing args ask for a
    field that provably does not exist in whatever list it is chaining from.

    Only raises when a violation is statically provable from the plan's own
    literal args — every other case (module reads, unresolvable/ambiguous
    output shapes, non-list outputs) is left for the tool itself to validate
    at execution time, exactly as it already does.
    """
    step_schemas: dict[str, dict] = {}

    for step in queue:
        if not isinstance(step, dict):
            continue
        step_idx  = step.get("step")
        tool_name = step.get("tool")
        args      = step.get("args") or {}
        if step_idx is None or not isinstance(tool_name, str):
            continue
        step_key = f"step_{step_idx}"

        violations = _check_consumer_fields(tool_name, args, step_schemas)
        if violations:
            raise ValueError(violations[0])

        step_schemas[step_key] = compute_step_output_schema(tool_name, args, step_schemas)
