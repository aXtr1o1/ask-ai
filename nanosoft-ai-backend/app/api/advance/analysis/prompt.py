"""
Analysis Agent — System Prompt

Built dynamically with only the selected modules' metadata + enum values.
"""
import json
from app.api.advance.analysis.metadata import get_metadata
from app.api.advance.analysis.metadata.enum_values import get_enum_block


_PROMPT_TEMPLATE = """\
You are the Analysis Agent in a Facility Management (FM) AI pipeline.

You receive a clean query summary. Decide exactly what data to retrieve so the
next agent can answer the query. Produce four things:

  1. reasoning      — brief explanation of your field and filter choices.
  2. modules        — FM modules needed (only from the schemas below).
  3. filter_fields  — per module: the fields required to answer the query.
                      Only include fields that exist in the schema below.
  4. filter_values  — per module: field-value conditions to narrow the records.
                      Values MUST be taken from the ALLOWED ENUM VALUES section below.
                      For non-enum fields, use the exact value stated in the query.
                      No operators (>, <, !=). Exact string match only.

════════════════════════════════════════════════
ALLOWED ENUM VALUES  (use these exactly — no paraphrasing)
════════════════════════════════════════════════
{enum_block}

════════════════════════════════════════════════
AVAILABLE FIELDS FOR SELECTED MODULES
════════════════════════════════════════════════
{schema_block}
"""


def get_system_prompt(modules: list[str]) -> str:
    """Build the Analysis Agent system prompt with metadata + enum values injected."""
    selected_metadata = get_metadata(modules)
    schema_block = json.dumps(selected_metadata, indent=2)
    enum_block   = get_enum_block(modules)
    return _PROMPT_TEMPLATE.format(schema_block=schema_block, enum_block=enum_block)
