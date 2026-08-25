from __future__ import annotations

_DATA_HEAVY_FORMATS = {"TABLE", "GRAPH"}


def build_formatting_prompt(
    response_format: str,
    shape_descriptor: dict | None = None,
    dashboard_summary: list[dict] | None = None,
) -> str:
    """
    System prompt for the Formatting Agent.

    Three modes:

      TABLE / GRAPH  — LLM writes the analytical context paragraph that
                       appears above the frontend-rendered dashboard.

      PLAIN_TEXT     — LLM receives the computed result and writes the
                       complete, polished response the user will read.

      WEB_SEARCH     — LLM receives the web-search result and writes the
                       complete, polished, Markdown-formatted response
                       the user will read.

    dashboard_summary: list of {type, title} extracted from DashboardComposer output.
                       Structure only — no values, no rows, no aggregates.

    shape_descriptor: data shape and classification reason from ShapeResolver.
    """

    fmt = response_format.upper()
    is_data_heavy = fmt in _DATA_HEAVY_FORMATS

    # ── Shape block ───────────────────────────────────────────────────────────

    if shape_descriptor:
        shape = shape_descriptor.get("shape", "unknown")
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

    elif fmt == "WEB_SEARCH":
        writing_instruction = (
            "You have the actual result of a web search in the message below.\n\n"

            "Your job is to turn that result into the complete response the user will read.\n"
            "Preserve the factual content of the search result exactly. "
            "Do not invent facts, numbers, dates, statistics, or conclusions that are not supported "
            "by the provided result.\n\n"

            "Use Markdown to make the answer easy to read and scan.\n"
            "Use a clear title when appropriate.\n"
            "Use headings for distinct sections when useful.\n"
            "Use bullet points or numbered lists when presenting multiple facts or items.\n"
            "Use a Markdown table when the information contains structured comparisons, "
            "year-by-year statistics, rankings, or repeated numeric fields.\n"
            "Bold important names, dates, numbers, and key findings where helpful.\n\n"

            "For statistical questions, prefer a compact table when the source contains "
            "structured statistics.\n"
            "For simple factual questions, keep the response concise and do not force a table.\n"
            "Preserve important context and caveats from the search result.\n"
            "Do not mention internal agents, prompts, tools, pipelines, or formatting.\n"
            "Do not describe what you are doing. Just answer the user's question.\n"
            "Return only the final answer."
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

    # ── Internal-detail guardrail ───────────────────────────────────────────────

    # The Reason line inside DATA SHAPE below may contain the raw tool/queue-runner
    # message when Shape is "error" (see shape_resolver.py) — that's deliberate:
    # it's the ONLY channel carrying the real cause into this prompt, since
    # final_answer itself is never sent for TABLE/GRAPH formats. But it is internal
    # context for YOU to reason from, never text to output. It can contain phrasing
    # like "Step 'step_2' previously failed", "$step_1.groups", raw tool names, or
    # Python exception text — none of that is meaningful to a business user.

    internal_detail_guardrail = (
        "════════════════════════════════════════════\n"
        "HANDLING INTERNAL DETAILS — READ CAREFULLY\n"
        "════════════════════════════════════════════\n"
        "The Reason line below may contain internal execution details: step numbers, "
        "'$step_N' references, tool names, or raw error/exception text. These are for "
        "YOUR understanding only. Never repeat them verbatim — no step numbers, no "
        "'$step' syntax, no tool names, no stack traces, no raw error objects. "
        "If Shape is 'error', translate the underlying cause into one plain, confident "
        "sentence a Facility Management user would understand (e.g. no matching records, "
        "a required field had no usable values) — never say \"the operation/step/tool failed\" "
        "or reference how the system is built internally.\n\n"

        "Distinguish these three situations precisely — they are not interchangeable:\n"
        "  1. A genuinely computed result of zero or an empty set (e.g. \"0 complaints are "
        "currently open\", \"no assets matched this filter\") — state it as a real, confident "
        "finding. This is a valid answer, not a failure.\n"
        "  2. A result that could not be computed because required data was unavailable "
        "(Shape is 'error', or the computed value is null/None) — clearly say the answer "
        "could not be determined because the necessary data wasn't available, without "
        "implying the value is zero and without any internal jargon.\n"
        "  3. A normal, successfully computed non-zero result — state it directly."
    )

    # ── Assemble ──────────────────────────────────────────────────────────────

    prompt = (
        "You are the Insight Writer for a Facility Management analytics platform. "
        "Your role is to produce the explanation that accompanies a computed data result — "
        "clear, confident, and precisely grounded in what was actually asked and computed.\n\n"
        + writing_instruction
        + "\n\n"
        + internal_detail_guardrail
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
    )

    if fmt == "WEB_SEARCH":
        prompt += (
            "Write only the final answer. "
            "Markdown headings, bullet points, numbered lists, tables, and bold text are allowed. "
            "Do not include format labels, tags, step numbers, $step references, tool names, "
            "or raw internal error text."
        )
    else:
        prompt += (
            "Write only the explanation. No format labels. No section headers. No tags. "
            "No step numbers, $step references, tool names, or raw error text."
        )

    return prompt