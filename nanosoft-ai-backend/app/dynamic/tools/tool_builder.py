"""
dynamic/tools/tool_builder.py
──────────────────────────────
Dynamically builds LangChain StructuredTools at runtime from client_service_registry.

How it works end-to-end:
    1. load_services()       → reads all active services for this client from DB
    2. build_input_schema()  → builds Pydantic model from fields_config (see tool_schemas.py)
    3. _make_tool_fn()       → creates a closure that calls sp_universal_query or sp_universal_aggregate
    4. _build_description()  → builds a description string with routing keywords
    5. StructuredTool()      → wraps everything into a LangChain tool

The tools are then passed to:
    model = base_llm.bind_tools(tools)

The LLM decides which tool to call based on the tool's name + description + routing keywords.

Usage in langchain_service.py:
    tools, tool_map = build_tools_for_client(client_name="poc", user_id=1)
    model = base_llm.bind_tools(tools)
"""

import json
import logging
from datetime import date, timedelta
from langchain_core.tools import StructuredTool

from app.dynamic.tools.tool_schemas import build_input_schema


def _resolve_date(date_value, fallback, is_end_date=False):
    if date_value is None:
        return None
    today = date.today()
    val = str(date_value).strip().lower()
    if val == "today":
        return today.isoformat()
    if val == "yesterday":
        return (today - timedelta(days=1)).isoformat()
    if val in ("this week", "thisweek"):
        return today.isoformat() if is_end_date else (today - timedelta(days=today.weekday())).isoformat()
    if val in ("last week", "lastweek"):
        last_monday = today - timedelta(days=today.weekday() + 7)
        return (last_monday + timedelta(days=6)).isoformat() if is_end_date else last_monday.isoformat()
    if val in ("this month", "thismonth"):
        return today.isoformat() if is_end_date else today.replace(day=1).isoformat()
    if val in ("last month", "lastmonth"):
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        return last_month_end.isoformat() if is_end_date else last_month_end.replace(day=1).isoformat()
    if val in ("this year", "thisyear"):
        return today.isoformat() if is_end_date else today.replace(month=1, day=1).isoformat()
    try:
        from datetime import datetime
        datetime.strptime(date_value, "%Y-%m-%d")
        return date_value
    except Exception:
        return fallback


def _get_time(date_from, date_to):
    today = date.today()
    today_str = today.isoformat()
    default_from = (today - timedelta(days=6)).isoformat()
    date_from = _resolve_date(date_from, fallback=default_from, is_end_date=False)
    date_to   = _resolve_date(date_to,   fallback=today_str,    is_end_date=True)
    if date_from is None and date_to is None:
        return default_from, today_str
    elif date_from is None:
        return default_from, date_to
    elif date_to is None:
        return date_from, today_str
    return date_from, date_to

logger = logging.getLogger("dynamic.tool_builder")
logger.setLevel(logging.INFO)


# ══════════════════════════════════════════════════════════════════════════════
# TOOL DESCRIPTION BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def _build_tool_description(service: dict) -> str:
    """
    Build the LangChain tool description string for one service.

    The description is critical — the LLM reads it to decide which tool to call.
    It must:
        - Clearly state what data this tool provides
        - List all routing keywords so the LLM knows when to trigger it
        - Be explicit that the tool MUST be called (not answered from memory)

    Args:
        service → dict from get_services_for_client()
    """
    keywords     = ", ".join(service.get("routing_keywords") or [])
    service_name = service["service_name"]

    return (
        f"ALWAYS call this tool for ANY query about {service_name} data. "
        f"This includes: listing records, counting records, filtering, searching, "
        f"grouping, or any aggregation related to {service_name}. "
        f"{service.get('description', '')} "
        f"MANDATORY trigger keywords — call this tool whenever user mentions: {keywords}. "
        f"Do NOT answer from memory — ALWAYS call this tool for data queries."
    )


# ══════════════════════════════════════════════════════════════════════════════
# TOOL FUNCTION FACTORY
# Creates a closure per service — each tool gets its own function
# ══════════════════════════════════════════════════════════════════════════════

def _make_tool_fn(
    service_key:   str,
    fields_config: dict,
    client_name:   str,
    user_id:       int,
):
    """
    Returns a callable tool function for one service.

    This is a closure — it captures client_name, user_id, service_key, fields_config
    so the returned function always queries the right client + service.

    The returned function:
        1. Separates user-facing filter args from system args (user_name, user_id, etc.)
        2. Builds p_filters dict  → non-date field filters
        3. Builds p_date_filters  → date range filters {field: {from: X, to: Y}}
        4. Calls sp_universal_query (list/count) OR sp_universal_aggregate (group by)
        5. Returns raw JSON string of the SP result

    Args:
        service_key:   e.g. "assets"
        fields_config: dict of field_name → {type, aggregatable, is_date}
        client_name:   e.g. "poc"
        user_id:       e.g. 1
    """

    # Pre-compute which fields are date fields — used when splitting kwargs
    date_fields = {
        fname for fname, fmeta in fields_config.items()
        if fmeta.get("is_date", False)
    }
    # Real columns (e.g. updated_at) are table columns, not inside JSONB data
    real_date_columns = {
        fname for fname, fmeta in fields_config.items()
        if fmeta.get("is_date", False) and fmeta.get("real_column", False)
    }
    # Use first real_date_column as the SP param (default: updated_at)
    real_date_column = next(iter(real_date_columns), "updated_at")
    def tool_fn(**kwargs) -> str:
        from app.api.database.postgres_client import get_pool
        conn   = get_pool()
        cursor = conn.cursor()

        # ── Extract system/control kwargs ─────────────────────────────────────
        # These are never passed as filters — they control how the SP is called
        is_aggregate     = kwargs.get("is_aggregate", False)
        group_by_columns = kwargs.get("group_by_columns") or []
        limit            = kwargs.get("limit")
        offset           = kwargs.get("offset") or 0

        # ── Fields to skip when building p_filters ────────────────────────────
        # These are system fields injected by the tool fn, not user filter values
        SKIP_FIELDS = {
            "user_name", "user_id", "is_aggregate",
            "group_by_columns", "aggregate_function",
            "limit", "offset", "keyword",
        }

        # Build set of date _from/_to field names to skip in normal filter loop
        # They are handled separately in the date filter loop below
        date_from_to_fields = set()
        for df in date_fields:
            date_from_to_fields.add(f"{df}_from")
            date_from_to_fields.add(f"{df}_to")

        # ── Build p_filters: non-date field filters ───────────────────────────
        # These become: WHERE data->>'FieldName' = 'value' in the SP
        p_filters: dict = {}
        for key, val in kwargs.items():
            if val is None:
                continue
            if key in SKIP_FIELDS:
                continue
            if key in date_from_to_fields:
                continue
            if key in date_fields:
                continue
            p_filters[key] = str(val)

        # ── Build p_date_filters: date range filters ──────────────────────────
        # Format: { "updated_at": { "from": "2024-01-01", "to": "2024-12-31" } }
        # If LLM passes no date at all → apply default last 7 days on real_date_column
        p_date_filters: dict = {}
        any_date_provided = any(
            kwargs.get(f"{df}_from") or kwargs.get(f"{df}_to")
            for df in date_fields
        )
        if not any_date_provided and real_date_column:
            # LLM sent no dates → default to last 7 days on the real date column
            default_from, default_to = _get_time(None, None)
            p_date_filters[real_date_column] = {
                "from": default_from,
                "to":   default_to,
            }
            logger.info("📅 [DATE DEFAULT] No dates from LLM → defaulting | %s: %s → %s",
                        real_date_column, default_from, default_to)
        else:
            for df in date_fields:
                from_val = kwargs.get(f"{df}_from")
                to_val   = kwargs.get(f"{df}_to")
                if from_val or to_val:
                    resolved_from, resolved_to = _get_time(from_val, to_val)
                    p_date_filters[df] = {}
                    if resolved_from:
                        p_date_filters[df]["from"] = resolved_from
                    if resolved_to:
                        p_date_filters[df]["to"]   = resolved_to

        # ── Keyword fallback: map to first string field ───────────────────────
        # If user says a specific technical term not matched by other fields,
        # it gets routed to the first string field as a loose filter
        keyword = kwargs.get("keyword")
        if keyword:
            string_fields = [
                fname for fname, fmeta in fields_config.items()
                if fmeta.get("type", "string") == "string" and not fmeta.get("is_date", False)
            ]
            if string_fields:
                p_filters[string_fields[0]] = keyword

        # ── Log all received args from LLM ────────────────────────────────────
        logger.info("=" * 60)
        logger.info("🤖 [TOOL] LLM args received | service=%s | client=%s", service_key, client_name)
        logger.info("   is_aggregate     = %s", is_aggregate)
        logger.info("   group_by_columns = %s", group_by_columns)
        logger.info("   limit            = %s", limit)
        logger.info("   offset           = %s", offset)
        logger.info("   keyword          = %s", kwargs.get("keyword"))
        logger.info("   p_filters        = %s", p_filters)
        logger.info("   p_date_filters   = %s", p_date_filters)
        logger.info("=" * 60)

        try:
            if is_aggregate and group_by_columns:
                # ── PATH A: GROUP BY aggregate ────────────────────────────────
                # Called when user asks "how many per X" or "breakdown by Y"
                # Uses sp_universal_aggregate which does COUNT(*) GROUP BY columns
                group_by_str = ",".join(group_by_columns)

                logger.info("🗄️  [TOOL] Calling sp_universal_aggregate | service=%s | group_by=%s", service_key, group_by_str)

                cursor.execute(
                    """SELECT public.sp_universal_aggregate(
                        %s::text,
                        %s::integer,
                        %s::text,
                        %s::text,
                        %s::jsonb,
                        %s::text
                    )""",
                    (
                        client_name,
                        user_id,
                        service_key,
                        group_by_str,
                        json.dumps(p_date_filters),
                        real_date_column,
                    )
                )

            elif is_aggregate and not group_by_columns:
                # ── PATH B: COUNT only (aggregate with no grouping) ───────────
                # Called when user asks "how many total" with no grouping
                # Uses sp_universal_query with limit=NULL to get total count
                logger.info("🗄️  [TOOL] Calling sp_universal_query [COUNT mode] | service=%s", service_key)

                cursor.execute(
                    """SELECT public.sp_universal_query(
                        %s::text,
                        %s::integer,
                        %s::text,
                        %s::jsonb,
                        %s::jsonb,
                        NULL::integer,
                        %s::integer,
                        %s::text
                    )""",
                    (
                        client_name,
                        user_id,
                        service_key,
                        json.dumps(p_filters),
                        json.dumps(p_date_filters),
                        0,
                        real_date_column,
                    )
                )

            else:
                # ── PATH C: Normal list / filter ──────────────────────────────
                # Called for "show me assets", "list complaints by division", etc.
                # Uses sp_universal_query with optional limit + offset
                logger.info(
                    "🗄️  [TOOL] Calling sp_universal_query [LIST mode] | service=%s | limit=%s | offset=%s",
                    service_key, limit, offset,
                )

                cursor.execute(
                    """SELECT public.sp_universal_query(
                        %s::text,
                        %s::integer,
                        %s::text,
                        %s::jsonb,
                        %s::jsonb,
                        %s::integer,
                        %s::integer,
                        %s::text
                    )""",
                    (
                        client_name,
                        user_id,
                        service_key,
                        json.dumps(p_filters),
                        json.dumps(p_date_filters),
                        limit,
                        offset,
                        real_date_column,
                    )
                )

            # ── Parse SP result ───────────────────────────────────────────────
            row = cursor.fetchone()
            cursor.close()

            raw = row[0] if row else {}
            if isinstance(raw, str):
                raw = json.loads(raw)

            p_count = raw.get("p_count", 0) if isinstance(raw, dict) else "?"
            p_list  = raw.get("p_list",  []) if isinstance(raw, dict) else []

            logger.info("=" * 60)
            logger.info("✅ [TOOL] SP result | service=%s | p_count=%s | records_returned=%s",
                        service_key, p_count, len(p_list) if isinstance(p_list, list) else "?")
            if isinstance(p_list, list) and len(p_list) > 0:
                logger.info("   first record sample = %s", json.dumps(p_list[0]))
            logger.info("=" * 60)

            return json.dumps(raw)

        except Exception as e:
            cursor.close()
            logger.error("=" * 60)
            logger.error("❌ [TOOL] SP call failed | service=%s | error=%s", service_key, str(e))
            logger.error("=" * 60)
            raise

    # Set the function name to service_key so LangChain tool name matches
    tool_fn.__name__ = service_key
    return tool_fn


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# Called from langchain_service.py on each new client session
# ══════════════════════════════════════════════════════════════════════════════

def build_tools_for_client(client_name: str, user_id: int):
    """
    Build LangChain StructuredTools for all active services of a client.

    This is called once per client session and the result is cached in
    LangChainService._client_tools to avoid rebuilding on every query.

    Steps:
        1. Load all active services from client_service_registry
        2. For each service:
            a. Build Pydantic input schema from fields_config
            b. Build tool function closure
            c. Build tool description with routing keywords
            d. Create StructuredTool

    Args:
        client_name: e.g. "poc"
        user_id:     e.g. 1

    Returns:
        tools    → list of StructuredTool  (passed to llm.bind_tools)
        tool_map → dict { "ASSETS": tool, "WORKORDERS": tool, ... }
                   (used for manual tool invocation in forced tool call path)
    """
    from app.dynamic.service import get_conn, get_services_for_client

    conn     = get_conn()
    services = get_services_for_client(conn, client_name)

    if not services:
        logger.warning(
            "⚠️ [TOOL BUILDER] No services found | client_name=%s | tool_map will be empty",
            client_name,
        )
        return [], {}

    tools    = []
    tool_map = {}

    for service in services:
        service_key   = service["service_key"]
        fields_config = service["fields_config"]

        logger.info("=" * 60)
        logger.info("🔧 [TOOL BUILDER] Building tool | name=%s | client=%s", service_key.upper(), client_name)
        logger.info("   fields       = %s", list(fields_config.keys()))
        logger.info("   keywords     = %s", service.get("routing_keywords"))
        logger.info("   date_fields  = %s", [f for f, m in fields_config.items() if m.get("is_date")])
        logger.info("   agg_fields   = %s", [f for f, m in fields_config.items() if m.get("aggregatable")])
        logger.info("=" * 60)

        # Build Pydantic input schema — LLM uses field descriptions to fill values
        input_schema = build_input_schema(service_key, fields_config)

        # Build tool function — closure that calls the right SP with right params
        fn = _make_tool_fn(
            service_key   = service_key,
            fields_config = fields_config,
            client_name   = client_name,
            user_id       = user_id,
        )

        # Build description — tells LLM when to call this tool
        description = _build_tool_description(service)

        # Register as LangChain StructuredTool
        # name is UPPERCASE service_key (e.g. "ASSETS") — must be consistent with tool_map keys
        tool = StructuredTool.from_function(
            func        = fn,
            name        = service_key.upper(),
            description = description,
            args_schema = input_schema,
        )

        tools.append(tool)
        tool_map[service_key.upper()] = tool

        logger.info("✅ [TOOL BUILDER] Tool registered | name=%s", service_key.upper())

    logger.info("=" * 60)
    logger.info("✅ [TOOL BUILDER] All tools built | client_name=%s | tools=%s", client_name, list(tool_map.keys()))
    logger.info("=" * 60)

    return tools, tool_map