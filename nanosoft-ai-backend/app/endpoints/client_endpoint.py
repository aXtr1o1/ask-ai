"""
app/endpoints/client_endpoint.py
──────────────────────────────────
Client registry endpoint:
    POST /api/client_insertion

Flow:
    OLD client → just update JWT token in client_registry
    NEW client → full onboarding:
                 1. Insert into client_sync_config (last_synced_at = NULL)
                 2. Call onboard_service() → migrates all data
                 3. Update client_sync_config SET last_synced_at = NOW()
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from app.models.schemas import ClientInsertionRequest
from app.api.database.postgres_client import get_pool, release_conn
from app.dynamic.onboarding.schemas import OnboardServiceRequest
from app.dynamic.service import (
    get_conn,
    save_client_to_registry,
    save_service_to_registry,
    sync_service_data,
)

logger = logging.getLogger("endpoints.client")

router = APIRouter(tags=["client"])


@router.post("/client_insertion")
async def client_insertion(request: ClientInsertionRequest):

    user_id     = str(request.userId).strip()
    service     = request.service.strip()
    client_name = request.clientName.strip()
    token       = request.token.strip()

    if not user_id:
        raise HTTPException(status_code=400, detail="userId is required")
    conn = None
    try:
        conn = get_pool()
        cursor = conn.cursor()

        # ── Check if client already exists in client_registry ──
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
            logger.info(
                "✅ [CLIENT] Token updated | client=%s",
                client_name,
            )
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
    # CASE 2 — NEW CLIENT → full onboarding + migration
    # ══════════════════════════════════════════════════════════
    logger.info(
        "[CLIENT] New client | client=%s — starting full onboarding",
        client_name,
    )

    conn = None
    try:
        conn = get_pool()
        cursor = conn.cursor()

        # ── STEP 1: Insert into client_sync_config ─────────────
        # last_synced_at = NULL → cron will know this is a fresh client
        logger.info(
            "[CLIENT] Step 1 → Inserting into client_sync_config | client=%s",
            client_name,
        )
        cursor.execute(
            """
            INSERT INTO client_sync_config
                (client_name, user_id, service_key, last_synced_at, is_active)
            SELECT %s, %s, service_key, NULL, true
            FROM   client_service_registry
            WHERE  client_name = %s
            ON CONFLICT (client_name, user_id, service_key) DO NOTHING
            """,
            (client_name, int(user_id), client_name),
        )
        conn.commit()
        logger.info(
            "✅ [CLIENT] Step 1 complete — client_sync_config inserted | client=%s",
            client_name,
        )

        # ── STEP 2: Save client to client_registry ─────────────
        logger.info(
            "[CLIENT] Step 2 → Saving to client_registry | client=%s",
            client_name,
        )
        save_client_to_registry(conn, client_name, token, service)
        logger.info(
            "✅ [CLIENT] Step 2 complete — client_registry saved | client=%s",
            client_name,
        )

        # ── STEP 3: Sync all service data ──────────────────────
        # Load all service keys from client_service_registry and sync each
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT service_key, endpoint, unique_field
            FROM   client_service_registry
            WHERE  client_name = %s AND is_active = true
            """,
            (client_name,),
        )
        services = cursor.fetchall()
        cursor.close()

        logger.info(
            "[CLIENT] Step 3 → Syncing %d service(s) | client=%s | services=%s",
            len(services), client_name, [s[0] for s in services],
        )

        total_inserted = 0
        for service_key, endpoint, unique_field in services:
            logger.info(
                "[CLIENT] Syncing service | client=%s | service_key=%s",
                client_name, service_key,
            )
            summary = sync_service_data(
                conn          = conn,
                client_name   = client_name,
                user_id       = int(user_id),
                service_key   = service_key,
                base_url      = service,
                jwt_token     = token,
                endpoint      = endpoint,
                unique_field  = unique_field,
                last_synced_at= None,   # NULL → fetch ALL records
            )
            total_inserted += summary["inserted"]
            logger.info(
                "✅ [CLIENT] Service synced | service_key=%s | inserted=%d | pages=%d",
                service_key, summary["inserted"], summary["pages_fetched"],
            )

        # ── STEP 4: Update last_synced_at = NOW() ──────────────
        logger.info(
            "[CLIENT] Step 4 → Updating last_synced_at | client=%s",
            client_name,
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE client_sync_config
            SET    last_synced_at = %s
            WHERE  client_name = %s
            AND    user_id     = %s
            """,
            (datetime.now(timezone.utc), client_name, int(user_id)),
        )
        conn.commit()
        cursor.close()
        logger.info(
            "✅ [CLIENT] Step 4 complete — last_synced_at updated | client=%s",
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
        "client_type":     "new",
        "exists":          False,
        "message":         "Client onboarded and data migrated successfully",
        "client": {
        "client_name":      client_name,
        "base_url":         service,
        "user_id":          user_id,
        "token":            token,
        "records_inserted": total_inserted,
    },
    }