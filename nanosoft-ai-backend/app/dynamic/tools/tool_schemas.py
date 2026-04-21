"""
dynamic/tools/tool_schemas.py
──────────────────────────────
Builds Pydantic input schemas for LangChain tools dynamically at runtime.

Why this is its own file:
    tool_builder.py was getting large because schema building is complex.
    Extracting it here makes tool_builder.py focused only on tool registration.

What this file does:
    _pydantic_type()     → maps fields_config type string → Python type
    build_input_schema() → builds a full Pydantic model for one service's tool

How the schema is used:
    LangChain uses the Pydantic model as the tool's args_schema.
    The LLM sees the field names + descriptions and fills them based on user query.
    The tool function receives the filled values as **kwargs.
"""

import logging
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, create_model

logger = logging.getLogger("dynamic.tool_schemas")


# ── Type mapping ──────────────────────────────────────────────────────────────
# Maps fields_config "type" string → Python Optional type for Pydantic
# All fields are Optional because the LLM may not always fill every filter

def _pydantic_type(field_type: str):
    """
    Convert a fields_config type string to a Python Optional type.

    Supported types:
        string   → Optional[str]
        integer  → Optional[int]
        boolean  → Optional[bool]
        date     → Optional[str]  (dates are strings in ISO format)
        datetime → Optional[str]
        default  → Optional[str]  (fallback for unknown types)
    """
    mapping = {
        "string":   Optional[str],
        "integer":  Optional[int],
        "boolean":  Optional[bool],
        "date":     Optional[str],
        "datetime": Optional[str],
    }
    return mapping.get(field_type, Optional[str])


# ══════════════════════════════════════════════════════════════════════════════
# MAIN SCHEMA BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_input_schema(service_key: str, fields_config: dict) -> type:
    """
    Dynamically build a Pydantic BaseModel from a service's fields_config.

    The resulting model is used as the LangChain tool's args_schema.
    The LLM fills in the fields based on the user's natural language query.

    Schema always includes two groups of fields:

    GROUP 1 — System fields (always present, same for every service):
        user_name          → injected by the tool function, never asked from user
        user_id            → injected by the tool function, never asked from user
        is_aggregate       → True when user wants grouping/breakdown (e.g. "how many per division")
        group_by_columns   → list of columns to group by (only when is_aggregate=True)
        aggregate_function → COUNT / SUM / AVG (only when is_aggregate=True)
        limit              → max records to return (only set if user specifies a number)
        offset             → pagination offset (rarely used)
        keyword            → fallback for loose text search on string fields

    GROUP 2 — Dynamic fields (one per entry in fields_config):
        - Non-date fields → single Optional filter field
        - Date fields     → TWO fields: {field}_from and {field}_to (ISO date range)

    Args:
        service_key:   used to name the Pydantic model class (e.g. "AssetsInput")
        fields_config: dict from client_service_registry describing each field

    Returns:
        A dynamically created Pydantic BaseModel class
    """
    fields: Dict[str, Any] = {}

    # ── GROUP 1: System fields ────────────────────────────────────────────────

    # user_name and user_id are injected by the tool function before calling the SP
    # The LLM should NEVER ask the user for these — descriptions say so explicitly
    fields["user_name"] = (
        Optional[str],
        Field(None, description="Internal system-set user name. Never request from user.")
    )
    fields["user_id"] = (
        Optional[str],
        Field(None, description="Internal system-set user ID. Never request from user.")
    )

    # is_aggregate=True triggers the GROUP BY path in the tool function
    # The LLM sets this when user asks "how many per X" or "breakdown by Y"
    fields["is_aggregate"] = (
        Optional[bool],
        Field(False, description="Set True for grouping/breakdown queries like 'how many per X', 'breakdown by Y'.")
    )

    # group_by_columns is only filled when is_aggregate=True
    # Must contain column names from the aggregatable fields in fields_config
    fields["group_by_columns"] = (
        Optional[List[str]],
        Field(None, description="List of columns to group by. Only fill when is_aggregate=True.")
    )

    # aggregate_function: COUNT for counts, SUM for totals, AVG for averages
    fields["aggregate_function"] = (
        Optional[str],
        Field(None, description="COUNT for how many, SUM for total, AVG for average. Only when is_aggregate=True.")
    )

    # limit: only set when user explicitly asks for a specific number of records
    # For count queries, limit should be None
    fields["limit"] = (
        Optional[int],
        Field(None, description="Max records. Only set if user asks for a specific number. Omit for count queries.")
    )

    # offset: used for pagination — almost never set directly by LLM
    fields["offset"] = (
        Optional[int],
        Field(None, description="Pagination offset. Omit unless requested.")
    )

    # keyword: loose text search fallback when no specific field matches
    # Routes to the first string field in fields_config
    fields["keyword"] = (
        Optional[str],
        Field(None, description="Fallback for specific technical terms not covered by other fields.")
    )

    # DEFAULT date range fields — always present in every tool
    # All generic relative date queries route here unless user names a specific date field
    fields["updated_at_from"] = (
        Optional[str],
        Field(None, description=(
            "Use this for ALL generic relative date queries: 'today', 'yesterday', "
            "'this week', 'last week', 'this month', 'last month', 'this year'. "
            "Also use for action words like 'registered', 'created', 'added', 'updated' + any time period. "
            "This is the DEFAULT date field unless user explicitly names another date field."
        ))
    )
    fields["updated_at_to"] = (
        Optional[str],
        Field(None, description=(
            "End of date range for updated_at. Always pair with updated_at_from. "
            "Use for all generic relative date queries."
        ))
    )

    # ── GROUP 2: Dynamic fields from fields_config ────────────────────────────

    logger.debug("[SCHEMA] Building dynamic fields for service_key=%s", service_key)

    for field_name, field_meta in fields_config.items():
        ftype   = field_meta.get("type", "string")
        is_date = field_meta.get("is_date", False)
        py_type = _pydantic_type(ftype)

        if is_date:
            # Date fields get a FROM + TO pair for range filtering
            # e.g. PurDate → PurDate_from="2024-01-01", PurDate_to="2024-12-31"
            # ONLY filled when user explicitly mentions this field name or a direct synonym
            field_desc = field_meta.get("description") or field_name
            fields[f"{field_name}_from"] = (
                Optional[str],
                Field(None, description=(
                    f"Start range for {field_desc}. Use YYYY-MM-DD. "
                    f"ONLY fill if user explicitly mentions '{field_name}' or a direct synonym. "
                    f"Do NOT fill for generic words like 'today', 'yesterday', 'this week', "
                    f"'registered', 'created', 'added' — those go to updated_at_from."
                ))
            )
            fields[f"{field_name}_to"] = (
                Optional[str],
                Field(None, description=(
                    f"End range for {field_desc}. Use YYYY-MM-DD. "
                    f"ONLY fill if user explicitly mentions '{field_name}' or a direct synonym. "
                    f"Do NOT fill for generic words like 'today', 'yesterday', 'this week', "
                    f"'registered', 'created', 'added' — those go to updated_at_to."
                ))
            )
            logger.debug("[SCHEMA] Date field added: %s_from + %s_to", field_name, field_name)
        else:
            # Non-date fields get a single Optional filter
            fields[field_name] = (
                py_type,
                Field(None, description=field_meta.get("description") or f"Filter by {field_name}.")
            )
            logger.debug("[SCHEMA] Field added: %s (%s)", field_name, ftype)

    # Dynamically create and return the Pydantic model class
    # Name is e.g. "AssetsInput", "WorkordersInput"
    model_name = f"{service_key.capitalize()}Input"
    schema = create_model(model_name, **fields)

    logger.info(
        "[SCHEMA] ✅ Built input schema | service_key=%s | model=%s | total_fields=%d",
        service_key, model_name, len(fields),
    )
    return schema