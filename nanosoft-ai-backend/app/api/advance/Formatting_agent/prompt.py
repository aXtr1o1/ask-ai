from __future__ import annotations

# =============================================================================
# FORMAT LABELS
# =============================================================================
_FORMAT_LABEL = {
    "TABLE":          "Table",
    "GRAPH":          "Graph",
    "NUMBERED_LIST":  "Numbered List",
    "BULLET_LIST":    "Bullet List",
    "PLAIN_TEXT":     "Plain Text",
}

_DATA_HEAVY_FORMATS = {"TABLE", "GRAPH"}


def build_formatting_prompt(
    response_format: str,
    shape_descriptor: dict | None = None,
    alternatives: list[str] | None = None,
    format_overridden: bool = False,
) -> str:
    """
    Returns system_prompt for the Formatting Agent.

    The shape_descriptor (structure only — no actual values) is injected
    so the LLM can give a MEANINGFUL confidence score based on how well
    the format fits the data shape.

    Alternatives are computed by the shape_resolver (pure code) — the LLM
    only uses them if it decides to suggest one.
    """
    is_data_heavy   = response_format.upper() in _DATA_HEAVY_FORMATS
    current_label   = _FORMAT_LABEL.get(response_format.upper(), response_format)

    # Build alternatives string (code-computed, passed in)
    alt_labels = [_FORMAT_LABEL.get(a, a) for a in (alternatives or [])]
    others_str = ", ".join(alt_labels) if alt_labels else "none"

    # Shape context block (structure only — no values)
    if shape_descriptor:
        shape_type = shape_descriptor.get("type", "unknown")
        shape_lines = [f"  Data shape type : {shape_type}"]
        for k, v in shape_descriptor.items():
            if k != "type":
                shape_lines.append(f"  {k:20s}: {v}")
        shape_block = "\n".join(shape_lines)
    else:
        shape_block = "  (shape not available)"

    # Override notice
    override_note = (
        "\nNote: The display format was auto-corrected from the originally suggested format "
        "because the data shape did not match it. The format shown above is the resolved best fit.\n"
        if format_overridden else ""
    )

    # Writing guidance
    if is_data_heavy:
        writing_guidance = f"""\
The answer is displayed as a {current_label} — the frontend renders the data directly.
Your job: write the analytical context paragraph that appears above the {current_label}.
Describe what was examined, how it was computed, and what the data reveals.
Do not invent numbers — you have no rows. Reference the computation steps and shape info.
Write 3–5 sentences, confident present tense, no markdown, no headers."""
    else:
        writing_guidance = f"""\
The answer is presented as a {current_label}. You have the actual computed result.
Write the complete, polished response the user will read.
Lead with the finding. Use the actual values. Add a sentence of context.
Be specific. No markdown, no headers, no asterisks — plain text only."""

    system_prompt = f"""\
You are the Insight Writer in a Facility Management analytics platform.

{writing_guidance}
{override_note}
════════════════════════════════════════════
DATA SHAPE  (structure only — no raw values)
════════════════════════════════════════════
{shape_block}

════════════════════════════════════════════
FORMAT CONFIDENCE
════════════════════════════════════════════
Chosen format : {current_label}
Alternatives  : {others_str}

After writing the explanation, assess how well {current_label} fits
this data shape and query. Score 1–10 (10 = perfect fit, 1 = poor fit).

Base your score on:
- Does the data shape suit this format? (e.g. grouped_data suits TABLE/GRAPH)
- Are there few enough items for the format to be readable?
- Is an alternative from the list above clearly better?

Output in this exact structure:

[EXPLANATION]
<your explanation here>

[CONFIDENCE]
<integer 1-10>

If confidence < 8, add one final line inside [EXPLANATION]:
"This answer is displayed as {current_label}. You can also ask for: {others_str}."
If confidence >= 8, do not add any format suggestion.
"""
    return system_prompt


# =============================================================================
# CONVENIENCE CONSTANT (kept for legacy imports)
# =============================================================================
FORMATTING_SYSTEM_PROMPT = ""  # Not used directly — use build_formatting_prompt()