from __future__ import annotations

_DATA_HEAVY_FORMATS = {"TABLE", "GRAPH"}


def build_formatting_prompt(
    response_format:   str,
    shape_descriptor:  dict | None       = None,
    dashboard_summary: list[dict] | None = None,
) -> str:
    """
    System prompt for the Formatting Agent.

    Two modes:
      TABLE / GRAPH  — LLM writes the analytical context paragraph that
                       appears above the frontend-rendered dashboard.
                       Dashboard component titles + types are provided so the
                       LLM can reference what the user is actually seeing.
                       No raw data values or row-level results are sent.

      PLAIN_TEXT     — LLM receives the computed result and writes the
                       complete, polished response the user will read.
                       Dashboard component context is still provided where available.

    dashboard_summary: list of {type, title} extracted from DashboardComposer output.
                       Structure only — no values, no rows, no aggregates.
    shape_descriptor:  data shape and classification reason from ShapeResolver.
    """
    fmt           = response_format.upper()
    is_data_heavy = fmt in _DATA_HEAVY_FORMATS

    # ── Shape block ───────────────────────────────────────────────────────────
    if shape_descriptor:
        shape  = shape_descriptor.get("shape",  "unknown")
        reason = shape_descriptor.get("reason", "")
        shape_block = f"  Shape : {shape}\n  Reason: {reason}"
    else:
        shape_block = "  (shape not available)"

    # ── Dashboard components block ─────────────────────────────────────────────
    if dashboard_summary:
        comp_lines = "\n".join(
            f"  • {c.get('type', 'component')} — {c.get('title', '(untitled)')}"
            for c in dashboard_summary
        )
        dashboard_block = (
            "════════════════════════════════════════════\n"
            "DASHBOARD COMPONENTS  (titles only — no values)\n"
            "════════════════════════════════════════════\n"
            + comp_lines
        )
    else:
        dashboard_block = ""

    # ── Mode-specific writing instruction ─────────────────────────────────────
    if is_data_heavy:
        writing_instruction = (
            "The result is rendered as an interactive dashboard in the user interface — "
            "the frontend displays all charts, KPI cards, and tables directly.\n"
            "You do not have access to any raw data values or row-level results, "
            "and you do not need them.\n\n"
            "You have three sources of context — use all three:\n"
            "  1. The user's question — tells you what they wanted to understand.\n"
            "  2. The computation steps — tell you exactly what was computed and how: "
            "which data module was queried, which fields were grouped or filtered, "
            "what metric was measured, and what scope was applied. "
            "Read the steps carefully — they are your primary source of analytical context.\n"
            "  3. The dashboard component titles — tell you what visuals the user is looking at "
            "right now (KPI cards, bar charts, time series, donuts, tables, etc.).\n\n"
            "Your job: write the analytical context paragraph that appears directly above the dashboard. "
            "Explain what was examined, how the answer was computed, and what the dashboard reveals. "
            "Reference the specific components by name so the user understands what they are seeing and why. "
            "Derive everything from the question, the steps, and the component titles — "
            "do not invent or estimate any numbers.\n\n"
            "Write in first person singular — speak directly as the AI assistant using 'I'. "
            "For example: 'I analysed...', 'I grouped...', 'I computed...'. "
            "Do not use 'We' or 'The system'. "
            "Write 3 to 5 sentences. Confident present tense. "
            "No markdown. No headers. No bullet points. Plain analytical prose only."
        )
    else:
        writing_instruction = (
            "You have the actual computed result in the message below.\n\n"
            "Your job is to write the complete, polished response the user will read. "
            "Open with the key finding and use the exact values from the result. "
            "If a single sentence of analytical context or implication genuinely adds value "
            "for a Facility Management professional, include it — otherwise keep the answer "
            "direct and concise.\n\n"
            "No markdown. No headers. No bullet points. Plain prose only."
        )

    # ── Assemble ──────────────────────────────────────────────────────────────
    prompt = (
        "You are the Insight Writer for a Facility Management analytics platform. "
        "Your role is to produce the explanation that accompanies a computed data result — "
        "clear, confident, and precisely grounded in what was actually asked and computed.\n\n"
        + writing_instruction
        + "\n\n════════════════════════════════════════════\n"
        "DATA SHAPE  (structure — no raw values)\n"
        "════════════════════════════════════════════\n"
        + shape_block
    )

    if dashboard_block:
        prompt += "\n\n" + dashboard_block

    prompt += (
        "\n\n════════════════════════════════════════════\n"
        f"Presentation format: {fmt}\n"
        "════════════════════════════════════════════\n"
        "Write only the explanation. No format labels. No section headers. No tags."
    )

    return prompt