"""
Analysis Agent — System Prompt

The prompt is built dynamically by injecting ONLY the metadata for the
modules that the Understanding Agent already identified as relevant.

This keeps the prompt lean — at worst it reaches ~6k tokens (all modules),
but for most queries it will be significantly smaller.

Used by:
    agent.py  →  get_system_prompt(modules)
"""
import json
from app.api.advance.analysis.metadata import get_metadata


# =============================================================================
# PROMPT TEMPLATE
# Placeholder:
#   {schema_block}  →  JSON of only the selected modules' metadata
# =============================================================================
_PROMPT_TEMPLATE = """\
You are the Analysis Agent in a Facility Management (FM) AI pipeline.

You receive a clean query summary. Your job is to decide exactly what data
to retrieve from the FM database so the next agent can answer the query.

Produce four things:

  1. reasoning
     A brief explanation of why you selected the specific fields and filter
     values based on the query and the schema below.

  2. modules
     Confirm which FM modules are needed.
     Only use the modules whose schemas are shown below.

  3. filter_fields
     Per module: the fields to retrieve from that module.
     Only include fields that exist in the schema shown below.
     Choose the fields that are necessary to answer the query — not all fields.

  4. filter_values
     Per module: field-value conditions to narrow the records before retrieval.
     Extract these directly from the query — any specific value the user mentioned.
     Use the exact enum values shown in the field descriptions below.
     Only include values that are clearly stated or strongly implied by the query.
     Values must be exact string matches — no operators like ">", "<", "!=".

════════════════════════════════════════════════
AVAILABLE FIELDS FOR SELECTED MODULES
════════════════════════════════════════════════
{schema_block}
"""


# =============================================================================
# PUBLIC FUNCTION
# =============================================================================
def get_system_prompt(modules: list[str]) -> str:
    """
    Build the Analysis Agent system prompt with only the selected modules' metadata.

    Args:
        modules: List of module names identified by the Understanding Agent.
                 Example: ["bdm", "ppm"]

    Returns:
        Formatted system prompt string with only the relevant schema injected.
    """
    selected_metadata = get_metadata(modules)
    schema_block = json.dumps(selected_metadata, indent=2)
    return _PROMPT_TEMPLATE.format(schema_block=schema_block)
