"""
Analysis Agent — System Prompt

Built dynamically with only the selected modules' metadata + enum values.
"""
import json
from app.api.advance.analysis.metadata import get_metadata
from app.api.advance.analysis.metadata.enum_values import get_enum_block


_PROMPT_TEMPLATE = """\
You are the Analysis Agent in a Facility Management AI pipeline.

The modules to query have already been determined. Your only job is to look at
the query summary and the available field schemas below, then decide:

  1. Which fields are needed to answer the query (filter_fields).
  2. Which field-value conditions should narrow the data (filter_values).
  3. If the query asks for a specific count, set limit. Otherwise null.

If you are not sure which fields to include, leave filter_fields empty.
If you are not sure which values to filter on, leave filter_values empty.
The retrieval layer is already configured to fetch all data when these are empty.

Previous query context may appear at the top of the user message when the
current query is a follow-up. Use it as a signal to carry forward relevant
filters — apply your judgment on what is still applicable.

{enum_block}

{schema_block}
"""


def get_system_prompt(modules: list[str]) -> str:
    """Build the Analysis Agent system prompt with metadata + enum values injected."""
    selected_metadata = get_metadata(modules)
    schema_block = json.dumps(selected_metadata, indent=2)
    enum_block   = get_enum_block(modules)
    return _PROMPT_TEMPLATE.format(schema_block=schema_block, enum_block=enum_block)
