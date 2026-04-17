"""
dynamic/onboarding/routes/sync_routes.py
─────────────────────────────────────────
Handles POST /api/client/sync

Responsibility:
    Re-sync data for an already onboarded client + service.
    Reads credentials from client_registry — caller does NOT need to pass token/base_url again.

When to use:
    - Client's data has changed and needs to be refreshed in client_service_data
    - Scheduled background sync jobs call this endpoint
    - Manual re-sync triggered by admin

Difference from onboard:
    - Does NOT re-save client or service config
    - ONLY fetches fresh data and upserts into client_service_data
"""

import logging
from fastapi import APIRouter, HTTPException

from app.dynamic.onboarding.schemas import SyncRequest
from app.dynamic.service import (
    get_conn,
    sync_service_data,
)

logger = logging.getLogger("dynamic.sync_routes")

router = APIRouter(prefix="/api/client", tags=["Dynamic Client - Sync"])


# ══════════════════════════════════════════════════════════════════════════════
# POST /sync
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/sync")
def sync_client_service(req: SyncRequest):
    """
    Re-sync data for a specific client + service.

    What this endpoint does:
        1. Looks up base_url + token from client_registry using client_name
        2. Looks up endpoint + unique_field from client_service_registry
        3. Fetches fresh data from client API (paginated)
        4. Upserts all records into client_service_data

    Caller only needs to provide:
        - client_name  → identifies the client
        - user_id      → used as part of the composite key
        - service_key  → identifies which service to sync

    Request body:
    {
        "client_name": "poc",
        "user_id":     1,
        "service_key": "assets"
    }
    """
    logger.info(
        "🔄 [SYNC] Incoming request | client_name=%s | user_id=%s | service_key=%s",
        req.client_name, req.user_id, req.service_key,
    )

    conn   = get_conn()
    cursor = conn.cursor()

    # ── Lookup: get endpoint + base_url + token + unique_field from registry ─
    # JOIN client_service_registry + client_registry to get all needed config
    logger.info(
        "[SYNC] Looking up service config | client_name=%s | service_key=%s",
        req.client_name, req.service_key,
    )
    cursor.execute(
        """
        SELECT csr.endpoint, cr.base_url, cr.token, csr.unique_field
        FROM   client_service_registry csr
        JOIN   client_registry cr ON cr.client_name = csr.client_name
        WHERE  csr.client_name = %s
        AND    csr.service_key = %s
        """,
        (req.client_name, req.service_key),
    )
    row = cursor.fetchone()
    cursor.close()

    # ── Guard: service must exist before sync can run ─────────────────────────
    if not row:
        logger.warning(
            "[SYNC] ❌ Service not found | client_name=%s | service_key=%s",
            req.client_name, req.service_key,
        )
        raise HTTPException(
            status_code=404,
            detail=f"Service not found: client_name={req.client_name} service={req.service_key}",
        )

    endpoint, base_url, token, unique_field = row
    logger.info(
        "[SYNC] Config loaded | endpoint=%s | base_url=%s | unique_field=%s",
        endpoint, base_url, unique_field,
    )

    try:
        # ── Run sync: fetch all pages + upsert into client_service_data ───────
        logger.info("[SYNC] Starting data sync | client_name=%s | service_key=%s", req.client_name, req.service_key)
        summary = sync_service_data(
            conn         = conn,
            client_name  = req.client_name,
            user_id      = req.user_id,
            service_key  = req.service_key,
            base_url     = base_url,
            jwt_token    = token,
            endpoint     = endpoint,
            unique_field = unique_field,
        )
        logger.info(
            "✅ [SYNC] Complete | client_name=%s | service_key=%s | inserted=%d | pages=%d",
            req.client_name, req.service_key, summary["inserted"], summary["pages_fetched"],
        )
        return {"status": "success", "sync": summary}

    except Exception as e:
        logger.error(
            "❌ [SYNC] Failed | client_name=%s | service_key=%s | error=%s",
            req.client_name, req.service_key, e, exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))