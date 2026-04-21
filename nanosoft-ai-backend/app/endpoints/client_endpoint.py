"""
app/endpoints/client_endpoint.py
──────────────────────────────────
Client registry endpoint:
    POST /api/client_insertion

Flow:
    OLD client → just update JWT token in client_registry

    NEW client → full onboarding:
                 1. Save client to client_registry (last_synced_at = NULL)
                 2. Loop through ALL services from service_catalog.py
                 3. Save each service config → client_service_registry
                 4. Sync all data for each service → client_service_data
                 5. Update last_synced_at = NOW() in client_registry ONCE after all done

NOTE:
    last_synced_at lives in client_registry — one timestamp per client.
    No changes to client_service_registry for tracking sync time.
    Everything is driven dynamically by service_catalog.get_all_services().
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from app.models.schemas import ClientInsertionRequest
from app.api.database.postgres_client import get_pool, release_conn
from app.dynamic.service import (
    save_client_to_registry,
    save_service_to_registry,
    sync_service_data,
)
from app.services.sync.service_catalog import get_all_services

logger = logging.getLogger("endpoints.client")

router = APIRouter(tags=["client"])


@router.post("/client_insertion")
async def client_insertion(request: ClientInsertionRequest):

    user_id     = str(request.userId).strip()
    service     = request.service.strip()        # base_url
    client_name = request.clientName.strip()
    token       = request.token.strip()

    if not user_id:
        raise HTTPException(status_code=400, detail="userId is required")

    # ══════════════════════════════════════════════════════════
    # CHECK — is this an OLD or NEW client?
    # ══════════════════════════════════════════════════════════
    conn = None
    try:
        conn = get_pool()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT client_name, base_url, token
            FROM   client_registry
            WHERE  client_name = %s AND is_active = true
            LIMIT  1
            """,
            (client_name,),
        )
        row = cursor.fetchone()
        cursor.close()

    except Exception as e:
        logger.error(
            "[CLIENT] DB error while checking client | client=%s | error=%s",
            client_name, e, exc_info=True,
        )
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="Database error while checking client")
    finally:
        if conn:
            release_conn(conn)

    # ══════════════════════════════════════════════════════════
    # CASE 1 — OLD CLIENT → just update token
    # ══════════════════════════════════════════════════════════
    if row:
        db_client_name, db_base_url, db_token = row

        logger.info(
            "[CLIENT] Old client found | client=%s — updating token only",
            client_name,
        )

        conn = None
        try:
            conn = get_pool()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE client_registry
                SET    token = %s
                WHERE  client_name = %s
                """,
                (token, client_name),
            )
            conn.commit()
            cursor.close()
            logger.info("✅ [CLIENT] Token updated | client=%s", client_name)

        except Exception as e:
            logger.error(
                "[CLIENT] Failed to update token | client=%s | error=%s",
                client_name, e, exc_info=True,
            )
            if conn:
                conn.rollback()
            raise HTTPException(status_code=500, detail="Failed to update token")
        finally:
            if conn:
                release_conn(conn)

        return {
            "client_type": "old",
            "exists":      True,
            "message":     "Token updated successfully",
            "client": {
                "client_name": db_client_name,
                "base_url":    db_base_url,
                "token":       token,
            },
        }

    # ══════════════════════════════════════════════════════════
    # CASE 2 — NEW CLIENT → full onboarding via service_catalog
    # ══════════════════════════════════════════════════════════
    logger.info(
        "[CLIENT] New client | client=%s — starting full onboarding",
        client_name,
    )

    # Load all services from catalog — no hardcoding
    all_services = get_all_services()
    logger.info(
        "[CLIENT] Loaded %d service(s) from catalog | services=%s",
        len(all_services), [s["service_key"] for s in all_services],
    )

    conn = None
    total_inserted = 0

    try:
        conn = get_pool()

        # ── STEP 1: Save client to client_registry ─────────────────────────
        # last_synced_at = NULL at this point (set to NOW after all services sync)
        logger.info("[CLIENT] Step 1 → Saving client to client_registry | client=%s", client_name)
        save_client_to_registry(conn, client_name, token, service)
        logger.info("✅ [CLIENT] Step 1 complete — client_registry saved | client=%s", client_name)

        # ── STEP 2: For each service → register config + sync data ─────────
        for idx, svc in enumerate(all_services, start=1):

            service_key  = svc["service_key"]
            endpoint     = svc["endpoint"]
            unique_field = svc["unique_field"]

            logger.info(
                "[CLIENT] Step 2.%d → Registering service | client=%s | service_key=%s | endpoint=%s",
                idx, client_name, service_key, endpoint,
            )

            # ── 2a: Save service config to client_service_registry ──────────
            save_service_to_registry(
                conn             = conn,
                client_name      = client_name,
                service_key      = service_key,
                service_name     = svc["service_name"],
                description      = svc["description"],
                routing_keywords = svc["routing_keywords"],
                fields_config    = svc["fields_config"],
                endpoint         = endpoint,
                unique_field     = unique_field,
            )
            logger.info(
                "✅ [CLIENT] Service registered | service_key=%s",
                service_key,
            )

            # ── 2b: Sync ALL data for this service ──────────────────────────
            # last_synced_at = None → full fetch (fresh onboard, get everything)
            logger.info(
                "[CLIENT] Syncing data | client=%s | service_key=%s | endpoint=%s",
                client_name, service_key, endpoint,
            )
            summary = sync_service_data(
                conn           = conn,
                client_name    = client_name,
                user_id        = int(user_id),
                service_key    = service_key,
                base_url       = service,
                jwt_token      = token,
                endpoint       = endpoint,
                unique_field   = unique_field,
                last_synced_at = None,   # NULL → fetch ALL records
            )
            total_inserted += summary["inserted"]
            logger.info(
                "✅ [CLIENT] Data synced | service_key=%s | inserted=%d | pages=%d",
                service_key, summary["inserted"], summary["pages_fetched"],
            )

        # ── STEP 3: Update last_synced_at = NOW() in client_registry ONCE ──
        # Only after ALL services have synced successfully
        logger.info(
            "[CLIENT] Step 3 → Updating last_synced_at in client_registry | client=%s",
            client_name,
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE client_registry
            SET    last_synced_at = %s
            WHERE  client_name   = %s
            """,
            (datetime.now(timezone.utc), client_name),
        )
        conn.commit()
        cursor.close()
        logger.info(
            "✅ [CLIENT] Step 3 complete — last_synced_at updated | client=%s",
            client_name,
        )

    except Exception as e:
        logger.error(
            "[CLIENT] ❌ Onboarding failed | client=%s | error=%s",
            client_name, e, exc_info=True,
        )
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            release_conn(conn)

    return {
        "client_type": "new",
        "exists":      False,
        "message":     "Client onboarded and all services synced successfully",
        "client": {
            "client_name":      client_name,
            "base_url":         service,
            "user_id":          user_id,
            "token":            token,
            "services_synced":  len(all_services),
            "records_inserted": total_inserted,
        },
    }