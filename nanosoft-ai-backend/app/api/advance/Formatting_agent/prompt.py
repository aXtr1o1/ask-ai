from __future__ import annotations

# =============================================================================
# SUPPORTED FORMATS
# =============================================================================
_FORMAT_LABEL = {
    "TABLE":      "Table",
    "GRAPH":      "Graph",
    "PLAIN_TEXT": "Plain Text",
}

_DATA_HEAVY_FORMATS = {"TABLE", "GRAPH"}


def build_formatting_prompt(
    response_format:  str,
    shape_descriptor: dict | None = None,
    format_overridden: bool = False,
) -> str:
    """
    Returns the system prompt for the Formatting Agent.

    Two modes:
      TABLE / GRAPH  — LLM writes the analytical context paragraph that
                       appears above the frontend-rendered data.
                       No actual row values are sent to the LLM.

      PLAIN_TEXT     — LLM receives the computed result and writes the
                       complete, polished response the user will read.

    shape_descriptor contains the data shape (e.g. "grouped_numeric_data")
    and the reason it was classified that way. Injected for context — no values.
    """
    fmt           = response_format.upper()
    is_data_heavy = fmt in _DATA_HEAVY_FORMATS
    label         = _FORMAT_LABEL.get(fmt, fmt)

    # Shape context block — structure only, no values
    if shape_descriptor:
        shape = shape_descriptor.get("shape", "unknown")
        reason = shape_descriptor.get("reason", "")
        shape_block = f"  Shape : {shape}\n  Reason: {reason}"
    else:
        shape_block = "  (shape not available)"

    # Override notice
    override_note = (
        "\nNote: The display format was auto-corrected because the data shape "
        "did not match the originally suggested format. "
        "The format shown above is the best fit for the result.\n"
        if format_overridden else ""
    )

    # Writing instruction — depends on data-heavy vs lightweight
    if is_data_heavy:
        writing_instruction = (
            f"The answer is displayed as a {label} — the frontend renders the data directly.\n"
            f"Your job: write the analytical context paragraph that appears above the {label}.\n"
            "Describe what was examined, how it was computed, and what the data reveals.\n"
            "Do NOT invent numbers — you have no row values. Reference the computation steps and shape.\n"
            "Write 3–5 sentences. Confident present tense. No markdown, no headers, no asterisks."
        )
    else:
        writing_instruction = (
            "You have the actual computed result.\n"
            "Write the complete, polished response the user will read.\n"
            "Lead with the key finding. Use the actual values from the result. "
            "Add one sentence of context if helpful.\n"
            "Be specific. No markdown, no headers, no asterisks — plain prose only."
        )

    return (
        "You are the Insight Writer in a Facility Management analytics platform.\n\n"
        + writing_instruction
        + f"\n{override_note}"
        + "\n════════════════════════════════════════════\n"
        + "DATA SHAPE  (structure — no raw values)\n"
        + "════════════════════════════════════════════\n"
        + shape_block
        + "\n════════════════════════════════════════════\n"
        + f"Chosen format: {label}\n"
        + "\nWrite only the explanation. No format label, no headers, no [EXPLANATION] tags."
    )