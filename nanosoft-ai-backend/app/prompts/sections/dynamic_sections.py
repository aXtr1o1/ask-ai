"""
prompts/sections/dynamic_sections.py
──────────────────────────────────────
Builds the dynamic sections of the system prompt from client_service_registry data.

Why these are dynamic:
    Each client has different services, different keywords, and different aggregatable fields.
    These sections are rebuilt on every session start from the DB.

Functions:
    build_services_section()          → lists available tools with keywords
    build_routing_table()             → keyword → tool mapping table for LLM
    build_aggregatable_fields_section → tells LLM which fields can be used in group_by
    build_workflow_section()          → general workflow instructions with tool names

All functions take a `services` list from get_services_for_client().
"""

import logging

logger = logging.getLogger("prompts.dynamic_sections")


def build_services_section(services: list) -> str:
    """
    Build the 'Available Services' section of the system prompt.

    Lists every registered service with its name, description, and routing keywords.
    The LLM reads this to understand what data is available and which tool serves it.

    Args:
        services → list of dicts from get_services_for_client()

    Returns:
        Formatted string section for the system prompt
    """
    if not services:
        logger.warning("[PROMPT] No services found — services section will be empty")
        return "\nNo services currently registered for this client.\n"

    lines = [
        "\n═══════════════════════════════════════",
        " Available Services (Tools):",
        "═══════════════════════════════════════",
    ]
    for svc in services:
        tool_name = svc["service_key"].upper()
        name      = svc["service_name"]
        desc      = svc.get("description", "")
        keywords  = ", ".join(svc.get("routing_keywords") or [])
        lines.append(f"- {tool_name}: {name} — {desc}")
        lines.append(f"  Keywords: {keywords}")

    logger.debug("[PROMPT] Services section built | count=%d", len(services))
    return "\n".join(lines)


def build_routing_table(services: list) -> str:
    """
    Build the routing decision table for the system prompt.

    Each row maps a routing keyword → tool name.
    The LLM uses this as a quick reference to decide which tool to call.

    Args:
        services → list of dicts from get_services_for_client()

    Returns:
        Pipe-formatted markdown table as a string
    """
    if not services:
        return ""

    lines = [
        "\n═══════════════════════════════════════",
        " Tool Routing Table:",
        "═══════════════════════════════════════",
        "| User Mentions                          | Tool     |",
        "|----------------------------------------|----------|",
    ]
    for svc in services:
        tool_name = svc["service_key"].upper()
        # One row per keyword — LLM matches on any of these
        for kw in (svc.get("routing_keywords") or []):
            lines.append(f"| {kw:<38} | {tool_name:<8} |")

    logger.debug("[PROMPT] Routing table built | total_keywords=%d", sum(len(s.get("routing_keywords") or []) for s in services))
    return "\n".join(lines)


def build_aggregatable_fields_section(services: list) -> str:
    """
    Build the 'Valid group_by_columns' section of the system prompt.

    Tells the LLM exactly which fields it can use in group_by_columns for each tool.
    Without this, the LLM might hallucinate field names.

    Only fields with aggregatable=True in fields_config are listed here.

    Args:
        services → list of dicts from get_services_for_client()

    Returns:
        Formatted string section for the system prompt
    """
    if not services:
        return ""

    lines = [
        "\n═══════════════════════════════════════",
        " Valid group_by_columns per Service:",
        "═══════════════════════════════════════",
    ]
    for svc in services:
        tool_name = svc["service_key"].upper()
        # Only include fields where aggregatable=True
        agg_fields = [
            fname
            for fname, fmeta in (svc.get("fields_config") or {}).items()
            if fmeta.get("aggregatable", False)
        ]
        if agg_fields:
            lines.append(f"- {tool_name}: {', '.join(agg_fields)}")

    logger.debug("[PROMPT] Aggregatable fields section built")
    return "\n".join(lines)


def build_workflow_section(services: list) -> str:
    """
    Build the workflow instructions section of the system prompt.

    Lists available tool names and how to use them step by step.
    This is a reminder section — reinforces the routing + tool calling rules.

    Args:
        services → list of dicts from get_services_for_client()

    Returns:
        Formatted string section for the system prompt
    """
    # Comma-separated list of tool names e.g. "ASSETS, WORKORDERS, PPM"
    tool_names = [svc["service_key"].upper() for svc in services]
    tools_str  = ", ".join(tool_names) if tool_names else "no tools available"

    logger.debug("[PROMPT] Workflow section built | tools=%s", tools_str)

    return f"""
═══════════════════════════════════════
 Workflow:
═══════════════════════════════════════
- ALWAYS call a tool for any data query (list, count, filter, aggregate, show, fetch, etc.)
- Available tools: {tools_str}
- Determine which tool to use based on the routing keywords listed above.
- Call the tool with user_name (always provided) + any filters from the user query.
- Present the retrieved result in a clear markdown table format.
- Do NOT ask follow-up questions before calling tools — call immediately with available info.
"""