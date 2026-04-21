"""
dynamic/service.py
───────────────────
Core database operations for the dynamic client system.

This file is the single source of truth for all DB reads/writes
related to clients, services, and synced data.

Functions:
    get_conn()                  → get DB connection from pool
    save_client_to_registry()   → upsert client into client_registry
    save_service_to_registry()  → upsert service into client_service_registry
    ensure_unique_index()       → create unique index on client_service_data
    fetch_single_page()         → fetch one page of records from client API
    sync_service_data()         → paginate + bulk insert all records
    get_services_for_client()   → load all active services for a client (used by tool builder + system prompt)
    get_client_credentials()    → load token + base_url for a client (used by sync)

Tables touched:
    client_registry          → one row per client (name, token, base_url)
    client_service_registry  → one row per client+service (config, fields, keywords)
    client_service_data      → many rows per client+user+service (JSONB records)
"""

import json
import logging
import time
import psycopg2.extras
import requests
from datetime import timezone
from requests.exceptions import RequestException, Timeout
from fastapi import HTTPException

logger = logging.getLogger("dynamic.service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(ch)

# ── Constants ─────────────────────────────────────────────────────────────────
from app.services.sync.config import PAGE_SIZE, MAX_RETRIES, REQUEST_TIMEOUT

# ══════════════════════════════════════════════════════════════════════════════
# DB HELPER
# ══════════════════════════════════════════════════════════════════════════════

def get_conn():
    """
    Get the PostgreSQL connection from the app-level connection pool.
    Always use this — never create a new connection directly.
    """
    from app.api.database.postgres_client import get_pool
    return get_pool()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — SAVE CLIENT TO client_registry
# ══════════════════════════════════════════════════════════════════════════════

def save_client_to_registry(
    conn,
    client_name: str,
    token:       str,
    base_url:    str,
):
    """
    Upsert client credentials into client_registry.

    Safe to call multiple times — ON CONFLICT updates token + base_url.
    This means re-onboarding always refreshes credentials.

    Table: client_registry
    Unique key: client_name
    """
    logger.info("[SERVICE] Saving client | client_name=%s | base_url=%s", client_name, base_url)

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO client_registry
            (client_name, token, base_url, is_active)
        VALUES (%s, %s, %s, true)
        ON CONFLICT (client_name) DO UPDATE
            SET token     = EXCLUDED.token,
                base_url  = EXCLUDED.base_url,
                is_active = true
        """,
        (client_name, token, base_url),
    )
    conn.commit()
    cursor.close()
    logger.info("✅ [SERVICE] client_registry saved | client_name=%s", client_name)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — SAVE SERVICE CONFIG TO client_service_registry
# ══════════════════════════════════════════════════════════════════════════════

def save_service_to_registry(
    conn,
    client_name:      str,
    service_key:      str,
    service_name:     str,
    description:      str,
    routing_keywords: list,
    fields_config:    dict,
    endpoint:         str,
    unique_field:     str,
):
    """
    Upsert service configuration into client_service_registry.

    Safe to call multiple times — ON CONFLICT updates all config fields.
    This means re-onboarding always refreshes service config (fields, keywords, etc).

    Table: client_service_registry
    Unique key: (client_name, service_key)

    fields_config is stored as JSONB — it describes which fields are filterable,
    aggregatable, or date fields. The tool builder reads this at runtime.
    """
    logger.info(
        "[SERVICE] Saving service config | client_name=%s | service_key=%s | keywords=%s",
        client_name, service_key, routing_keywords,
    )

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO client_service_registry
            (client_name, service_key, service_name, description,
             routing_keywords, fields_config, endpoint, unique_field, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true)
        ON CONFLICT (client_name, service_key) DO UPDATE
            SET service_name     = EXCLUDED.service_name,
                description      = EXCLUDED.description,
                routing_keywords = EXCLUDED.routing_keywords,
                fields_config    = EXCLUDED.fields_config,
                endpoint         = EXCLUDED.endpoint,
                unique_field     = EXCLUDED.unique_field,
                is_active        = true
        """,
        (
            client_name,
            service_key,
            service_name,
            description,
            routing_keywords,
            json.dumps(fields_config),   # stored as JSONB
            endpoint,
            unique_field,
        ),
    )
    conn.commit()
    cursor.close()
    logger.info(
        "✅ [SERVICE] client_service_registry saved | client_name=%s | service_key=%s",
        client_name, service_key,
    )


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — ENSURE UNIQUE INDEX ON client_service_data
# ══════════════════════════════════════════════════════════════════════════════

def ensure_unique_index(
    conn,
    client_name:  str,
    user_id:      int,
    service_key:  str,
    unique_field: str,
):
    """
    Create a unique index on client_service_data for this client+user+service combination.

    Why we need this:
        client_service_data stores records as JSONB.
        We need to prevent duplicate records on re-sync.
        The unique constraint is on the unique_field value inside the JSONB data column.

    Index name: idx_{client_name}_{user_id}_{service_key}_unique
    Index on: (client_name, user_id, service_key, data->>'unique_field')

    IF NOT EXISTS makes this safe to call on every sync — no error if already exists.
    """
    # Sanitize client_name for use in index name (remove special chars)
    safe_name  = client_name.replace("-", "_").replace(".", "_")
    index_name = f"idx_{safe_name}_{user_id}_{service_key}_unique"

    logger.info(
        "[SERVICE] Ensuring unique index | index=%s | unique_field=%s",
        index_name, unique_field,
    )

    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE UNIQUE INDEX IF NOT EXISTS {index_name}
        ON public.client_service_data (
            client_name,
            user_id,
            service_key,
            (data->>'{unique_field}')
        )
        WHERE service_key = '{service_key}'
    """)
    conn.commit()
    cursor.close()
    logger.info("✅ [SERVICE] Unique index ensured | index=%s", index_name)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — FETCH ONE PAGE FROM CLIENT API
# ══════════════════════════════════════════════════════════════════════════════

def fetch_single_page(
    base_url:      str,
    jwt_token:     str,
    user_id:       int,
    endpoint:      str,
    last_synced_at,
    page_index:    int,
) -> list:
    """
    Fetch one page of records from the client's external API.

    Retries up to MAX_RETRIES times with 2s gap on failure.
    Returns list of records or [] if no more pages.

    Why POST instead of GET:
        Client APIs use POST with a payload containing PageIndex + PageSize.
        last_synced_at is passed to fetch only new/updated records (delta sync).

    Auth:
        x-auth header → Bearer JWT token
        userid header → user_id as string
    """
    url = f"{base_url}{endpoint}"

    # Format last_synced_at as ISO string for the API payload
    # Empty string means "fetch everything" (initial sync)
    if last_synced_at is not None:
        if hasattr(last_synced_at, "astimezone"):
            synced_ts = last_synced_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        else:
            synced_ts = str(last_synced_at)
    else:
        synced_ts = ""

    # Ensure Bearer prefix is not duplicated
    bearer  = f"Bearer {jwt_token}" if not jwt_token.startswith("Bearer ") else jwt_token
    headers = {
        "x-auth":       bearer,
        "userid":       str(user_id),
        "Content-Type": "application/json",
    }
    payload = {
        "data": {
            "PageIndex": page_index,
            "PageSize":  PAGE_SIZE,
            "UserID":    user_id,
            "DateTime":  synced_ts,
        }
    }

    logger.info("[SERVICE] Fetching page | endpoint=%s | page=%d | url=%s", endpoint, page_index, url)

    response = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            break  # success — exit retry loop
        except (Timeout, RequestException) as e:
            if attempt == MAX_RETRIES:
                logger.error(
                    "❌ [SERVICE] Page fetch failed after %d retries | endpoint=%s | page=%d | error=%s",
                    MAX_RETRIES, endpoint, page_index, e,
                )
                return []
            logger.warning(
                "⚠️ [SERVICE] Attempt %d/%d failed — retrying in 2s | endpoint=%s",
                attempt, MAX_RETRIES, endpoint,
            )
            time.sleep(2)

    if response is None:
        return []

    # Client API returns 400 with "No records found" when there are no more pages
    if response.status_code == 400 and "No records found" in response.text:
        logger.info("[SERVICE] No more records | endpoint=%s | page=%d", endpoint, page_index)
        return []

    if response.status_code != 200:
        logger.error(
            "❌ [SERVICE] Unexpected status %d | endpoint=%s | response=%s",
            response.status_code, endpoint, response.text[:300],
        )
        return []

    try:
        resp_json = response.json()
    except Exception as e:
        logger.error("❌ [SERVICE] Invalid JSON | endpoint=%s | page=%d | error=%s", endpoint, page_index, e)
        return []

    records = _extract_records(resp_json)
    logger.info("[SERVICE] Page %d → %d records extracted | endpoint=%s", page_index, len(records), endpoint)
    return records


def _extract_records(resp_json: dict) -> list:
    """
    Extract the records list from various API response shapes.

    Client APIs return records in different structures:
        { "Output": { "data": [...] } }
        { "data": [...] }
        { "data": { "records": [...] } }
    This function handles all known variants.
    """
    output = resp_json.get("Output") or resp_json.get("output")
    if isinstance(output, dict):
        records = output.get("data") or output.get("Data") or []
    else:
        raw = resp_json.get("data") or resp_json.get("Data")
        if isinstance(raw, list):
            records = raw
        elif isinstance(raw, dict):
            records = (
                raw.get("records") or raw.get("Records") or
                raw.get("data")    or raw.get("Data")    or
                raw.get("items")   or raw.get("Items")   or []
            )
        else:
            records = []

    if not isinstance(records, list):
        records = []
    return records


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — SYNC ALL PAGES INTO client_service_data
# ══════════════════════════════════════════════════════════════════════════════

def sync_service_data(
    conn,
    client_name:   str,
    user_id:       int,
    service_key:   str,
    base_url:      str,
    jwt_token:     str,
    endpoint:      str,
    unique_field:  str,
    last_synced_at=None,
) -> dict:
    """
    Fetch ALL pages from the client API and bulk upsert into client_service_data.

    Pagination logic:
        - Starts at page 1, increments until page returns < PAGE_SIZE records
        - If a page returns 0 records, stops immediately

    Upsert logic (ON CONFLICT):
        - Unique constraint on (client_name, user_id, service_key, data->>'unique_field')
        - On conflict → updates data + updated_at (no duplicate records)

    Returns:
        { "inserted": total_records_upserted, "pages_fetched": total_pages }
    """
    page_index     = 1
    total_inserted = 0
    pages_fetched  = 0

    # Ensure unique index exists before inserting (safe to call every time)
    ensure_unique_index(conn, client_name, user_id, service_key, unique_field)

    cursor = conn.cursor()

    logger.info(
        "[SERVICE] Starting sync | client_name=%s | service_key=%s | endpoint=%s",
        client_name, service_key, endpoint,
    )

    while True:
        # Fetch one page from client API
        records = fetch_single_page(
            base_url, jwt_token, user_id, endpoint, last_synced_at, page_index
        )

        # Empty page → no more data
        if not records:
            logger.info("[SERVICE] No records on page %d — stopping sync | endpoint=%s", page_index, endpoint)
            break

        # Prepare batch insert values: (client_name, user_id, service_key, json_record)
        insert_values = [
            (client_name, user_id, service_key, json.dumps(record))
            for record in records
        ]

        # ON CONFLICT: if record with same unique_field already exists → update data + timestamp
        psycopg2.extras.execute_values(
            cursor,
            f"""
            INSERT INTO public.client_service_data
                (client_name, user_id, service_key, data)
            VALUES %s
            ON CONFLICT (client_name, user_id, service_key, (data->>'{unique_field}'))
            WHERE service_key = '{service_key}'
            DO UPDATE SET
                data       = EXCLUDED.data,
                updated_at = now()
            """,
            insert_values,
            page_size=1000,
        )
        conn.commit()

        inserted        = len(records)
        total_inserted += inserted
        pages_fetched  += 1

        logger.info(
            "[SERVICE] Page %d synced | inserted=%d | total_so_far=%d | endpoint=%s",
            page_index, inserted, total_inserted, endpoint,
        )

        # If we got fewer records than PAGE_SIZE, this was the last page
        if inserted < PAGE_SIZE:
            logger.info(
                "[SERVICE] Last page reached | records=%d < page_size=%d | endpoint=%s",
                inserted, PAGE_SIZE, endpoint,
            )
            break

        time.sleep(0.5)  # prevent server overload (502 errors)
        page_index += 1

    cursor.close()
    logger.info(
        "✅ [SERVICE] Sync complete | service_key=%s | pages=%d | total_inserted=%d",
        service_key, pages_fetched, total_inserted,
    )
    return {"inserted": total_inserted, "pages_fetched": pages_fetched}


# ══════════════════════════════════════════════════════════════════════════════
# LOOKUP — GET ALL SERVICES FOR A CLIENT
# Used by: tool_builder.py + system_prompt.py
# ══════════════════════════════════════════════════════════════════════════════

def get_services_for_client(conn, client_name: str) -> list:
    """
    Load all active services for a client from client_service_registry.

    Called by:
        - tool_builder.py  → to build LangChain tools
        - system_prompt.py → to build dynamic routing table + services section
        - quota_service.py → to build quota exceeded menu

    Returns list of dicts:
    [
        {
            "service_key":      "assets",
            "service_name":     "Asset Management",
            "description":      "...",
            "routing_keywords": ["asset", "equipment"],
            "fields_config":    { "DivisionName": {...}, ... },
            "endpoint":         "/getAssets",
            "unique_field":     "AssetTagNo"
        },
        ...
    ]
    """
    logger.info("[SERVICE] Loading services | client_name=%s", client_name)

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT service_key, service_name, description,
               routing_keywords, fields_config, endpoint, unique_field
        FROM   client_service_registry
        WHERE  client_name = %s
        AND    is_active   = true
        ORDER  BY created_at ASC
        """,
        (client_name,),
    )
    rows = cursor.fetchall()
    cursor.close()

    services = []
    for row in rows:
        # fields_config may come back as string (if stored as text) or dict (if JSONB)
        fields_config = row[4]
        if isinstance(fields_config, str):
            fields_config = json.loads(fields_config)

        services.append({
            "service_key":      row[0],
            "service_name":     row[1],
            "description":      row[2],
            "routing_keywords": row[3] or [],
            "fields_config":    fields_config or {},
            "endpoint":         row[5],
            "unique_field":     row[6],
        })

    logger.info(
        "✅ [SERVICE] Services loaded | client_name=%s | count=%d | keys=%s",
        client_name, len(services), [s["service_key"] for s in services],
    )
    return services


# ══════════════════════════════════════════════════════════════════════════════
# LOOKUP — GET CLIENT CREDENTIALS
# Used by: sync endpoint to get token + base_url without re-sending them
# ══════════════════════════════════════════════════════════════════════════════

def get_client_credentials(conn, client_name: str) -> dict:
    """
    Load token + base_url for a client from client_registry.

    Used by the sync endpoint so the caller doesn't need to pass credentials again.
    Returns {} if client not found or is inactive.
    """
    logger.info("[SERVICE] Loading credentials | client_name=%s", client_name)

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT token, base_url
        FROM   client_registry
        WHERE  client_name = %s
        AND    is_active   = true
        """,
        (client_name,),
    )
    row = cursor.fetchone()
    cursor.close()

    if not row:
        logger.warning("[SERVICE] ⚠️ Client not found | client_name=%s", client_name)
        return {}

    logger.info("✅ [SERVICE] Credentials loaded | client_name=%s", client_name)
    return {"token": row[0], "base_url": row[1]}