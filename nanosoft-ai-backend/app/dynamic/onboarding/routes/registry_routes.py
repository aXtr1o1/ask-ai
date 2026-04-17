"""
dynamic/onboarding/routes/registry_routes.py
─────────────────────────────────────────────
Handles READ-ONLY registry endpoints:
    GET /api/client/verify/{client_name}/{user_id}/{service_key}
    GET /api/client/registry/{client_name}

Responsibility:
    - verify  → confirm data was inserted correctly after onboarding
    - registry → list all registered services for a client

These are diagnostic/inspection endpoints.
They do not modify any data.
"""

import logging
from fastapi import APIRouter

logger = logging.getLogger("dynamic.registry_routes")

router = APIRouter(prefix="/api/client", tags=["Dynamic Client - Registry"])


# ══════════════════════════════════════════════════════════════════════════════
# GET /verify/{client_name}/{user_id}/{service_key}
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/verify/{client_name}/{user_id}/{service_key}")
def verify_data(client_name: str, user_id: int, service_key: str, limit: int = 5):
    """
    Verify data was inserted correctly after onboarding.

    Returns:
        - total_records → total count of records for this client+user+service
        - sample        → last N records (default 5) ordered by id DESC

    Use this immediately after POST /onboard/service to confirm data arrived.

    Example:
        GET /api/client/verify/poc/1/assets?limit=5
    """
    logger.info(
        "[VERIFY] Incoming request | client_name=%s | user_id=%s | service_key=%s | limit=%d",
        client_name, user_id, service_key, limit,
    )

    from app.dynamic.service import get_conn
    conn   = get_conn()
    cursor = conn.cursor()

    # ── Fetch last N records for this client+user+service ────────────────────
    cursor.execute(
        """
        SELECT id, client_name, user_id, service_key, user_name, data, created_at
        FROM   public.client_service_data
        WHERE  client_name = %s
        AND    user_id     = %s
        AND    service_key = %s
        ORDER  BY id DESC
        LIMIT  %s
        """,
        (client_name, user_id, service_key, limit),
    )
    rows = cursor.fetchall()
    cursor.close()

    records = [
        {
            "id":          row[0],
            "client_name": row[1],
            "user_id":     row[2],
            "service_key": row[3],
            "user_name":   row[4],
            "data":        row[5],
            "created_at":  str(row[6]),
        }
        for row in rows
    ]

    # ── Get total count for this client+user+service ──────────────────────────
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM   public.client_service_data
        WHERE  client_name = %s
        AND    user_id     = %s
        AND    service_key = %s
        """,
        (client_name, user_id, service_key),
    )
    total = cursor.fetchone()[0]
    cursor.close()

    logger.info(
        "[VERIFY] ✅ Result | client_name=%s | service_key=%s | total=%d | sample=%d",
        client_name, service_key, total, len(records),
    )

    return {
        "client_name":   client_name,
        "user_id":       user_id,
        "service_key":   service_key,
        "total_records": total,
        "sample":        records,
    }


# ══════════════════════════════════════════════════════════════════════════════
# GET /registry/{client_name}
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/registry/{client_name}")
def get_client_registry(client_name: str):
    """
    List all services registered for a client.

    Returns all rows from client_service_registry for this client_name.
    Useful to confirm which services are available for the AI chatbot to use.

    Example:
        GET /api/client/registry/poc
    """
    logger.info("[REGISTRY] Incoming request | client_name=%s", client_name)

    from app.dynamic.service import get_conn
    conn   = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT service_key, service_name, endpoint, unique_field,
               routing_keywords, is_active, created_at
        FROM   client_service_registry
        WHERE  client_name = %s
        ORDER  BY created_at ASC
        """,
        (client_name,),
    )
    rows = cursor.fetchall()
    cursor.close()

    services = [
        {
            "service_key":      row[0],
            "service_name":     row[1],
            "endpoint":         row[2],
            "unique_field":     row[3],
            "routing_keywords": row[4],
            "is_active":        row[5],
            "created_at":       str(row[6]),
        }
        for row in rows
    ]

    logger.info(
        "[REGISTRY] ✅ Result | client_name=%s | services_found=%d",
        client_name, len(services),
    )

    return {
        "client_name": client_name,
        "services":    services,
        "count":       len(services),
    }