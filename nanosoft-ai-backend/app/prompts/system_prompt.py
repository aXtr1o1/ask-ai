"""
prompts/system_prompt.py
─────────────────────────
Assembles the full system prompt for the AI model at runtime.

Why it's dynamic:
    Each client has different services, keywords, and fields.
    The system prompt must reflect exactly what tools are available for THIS client.
    A static prompt would require code changes to add/remove services.

Assembly order:
    1. BASE_HEADER           → role definition + date rules (static)
    2. services_section      → lists available tools with descriptions (dynamic)
    3. routing_table         → keyword → tool mapping table (dynamic)
    4. aggregatable_fields   → valid group_by_columns per tool (dynamic)
    5. workflow_section      → how to use tools step by step (dynamic)
    6. STATIC_RULES          → tool calling rules + anti-hallucination (static)

Usage:
    from app.prompts.system_prompt import get_system_prompt
    prompt = get_system_prompt(client_name="poc", user_id=1)
    messages = [prompt] + lc_memory + [HumanMessage(content=query)]
"""

import logging
from langchain_core.messages import SystemMessage

from app.prompts.sections.base_header import BASE_HEADER, STATIC_RULES
from app.prompts.sections.dynamic_sections import (
    build_services_section,
    build_routing_table,
    build_aggregatable_fields_section,
    build_workflow_section,
)

logger = logging.getLogger("prompts.system_prompt")


def get_system_prompt(client_name: str, user_id: int) -> SystemMessage:
    """
    Build and return the complete system prompt for a client session.

    Steps:
        1. Load all active services for this client from DB
        2. Build each dynamic section using the services data
        3. Assemble all sections into one string
        4. Return as LangChain SystemMessage

    Falls back to a minimal prompt if services fail to load.

    Args:
        client_name: e.g. "poc"
        user_id:     e.g. 1

    Returns:
        SystemMessage to prepend to every model call
    """
    logger.info("[PROMPT] Building system prompt | client_name=%s | user_id=%s", client_name, user_id)

    # ── Load services from DB ─────────────────────────────────────────────────
    # Failure here means no dynamic sections — prompt still works with static rules
    try:
        from app.dynamic.service import get_conn, get_services_for_client
        conn     = get_conn()
        services = get_services_for_client(conn, client_name)
        logger.info("[PROMPT] Services loaded | client_name=%s | count=%d", client_name, len(services))
    except Exception as e:
        logger.error(
            "❌ [PROMPT] Failed to load services | client_name=%s | error=%s | using empty services",
            client_name, e,
        )
        services = []

    # ── Build each dynamic section ────────────────────────────────────────────
    services_section    = build_services_section(services)
    routing_table       = build_routing_table(services)
    aggregatable_fields = build_aggregatable_fields_section(services)
    workflow_section    = build_workflow_section(services)

    # ── Assemble full prompt ──────────────────────────────────────────────────
    # Order matters — LLM reads top to bottom
    content = (
        BASE_HEADER
        + services_section
        + routing_table
        + aggregatable_fields
        + workflow_section
        + STATIC_RULES
    )

    logger.info(
        "✅ [PROMPT] System prompt assembled | client_name=%s | services=%s | prompt_length=%d chars",
        client_name,
        [s["service_key"] for s in services],
        len(content),
    )

    return SystemMessage(content=content)