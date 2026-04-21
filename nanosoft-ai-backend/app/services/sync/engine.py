"""
app/services/sync/engine.py
────────────────────────────
Cron sync engine — called by sync_runner.py every N minutes.

Flow:
    1. Load all active clients from client_registry
       (includes token, base_url, user_id, last_synced_at)
    2. For each client → load all active services from client_service_registry
    3. Sync each service using the SAME last_synced_at from client_registry
       (delta sync — only fetch records newer than last sync)
    4. After ALL services synced → update last_synced_at = NOW() in client_registry ONCE

NOTE:
    last_synced_at is stored in client_registry — one timestamp per client.
    All services of a client share the same last_synced_at.
    client_sync_config table is no longer used.
    client_service_registry does NOT need a last_synced_at column.
"""

import logging
from datetime import timezone, datetime
from app.api.database.postgres_client import get_pool
from app.dynamic.service import sync_service_data

log = logging.getLogger("sync.engine")


def run_sync():
    log.info("═" * 60)
    log.info("🔄 [ENGINE] Starting full sync run")
    log.info("═" * 60)

    conn = get_pool()

    # ── STEP 1: Load all active clients from client_registry ─────────────────
    # last_synced_at is read here — one value per client, shared across all services
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT client_name, token, base_url, user_id, last_synced_at
        FROM   client_registry
        WHERE  is_active = true
        """
    )
    clients = cursor.fetchall()
    cursor.close()

    log.info("[ENGINE] Found %d active client(s)", len(clients))

    total_synced = 0
    total_failed = 0

    for client_name, token, base_url, user_id, last_synced_at in clients:

        log.info(
            "[ENGINE] ── Processing client=%s | user_id=%s | last_synced_at=%s",
            client_name, user_id, last_synced_at,
        )

        # ── STEP 2: Load all active services for this client ─────────────────
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT service_key, endpoint, unique_field
            FROM   client_service_registry
            WHERE  client_name = %s
            AND    is_active   = true
            """,
            (client_name,),
        )
        services = cursor.fetchall()
        cursor.close()

        log.info(
            "[ENGINE] client=%s | Found %d service(s): %s",
            client_name, len(services), [s[0] for s in services],
        )

        if not services:
            log.warning(
                "[ENGINE] ⚠️ No active services found | client=%s — skipping",
                client_name,
            )
            continue

        client_failed = False

        for service_key, endpoint, unique_field in services:

            log.info(
                "[ENGINE] Syncing | client=%s | service=%s | last_synced_at=%s",
                client_name, service_key, last_synced_at,
            )

            try:
                # ── STEP 3: Delta sync using shared last_synced_at ────────────
                # last_synced_at = NULL     → full fetch (fresh client, first ever sync)
                # last_synced_at = datetime → delta fetch (only new/updated records)
                summary = sync_service_data(
                    conn           = conn,
                    client_name    = client_name,
                    user_id        = user_id,
                    service_key    = service_key,
                    base_url       = base_url,
                    jwt_token      = token,
                    endpoint       = endpoint,
                    unique_field   = unique_field,
                    last_synced_at = last_synced_at,
                )

                log.info(
                    "✅ [ENGINE] Service done | client=%s | service=%s | inserted=%d | pages=%d",
                    client_name, service_key,
                    summary["inserted"], summary["pages_fetched"],
                )
                total_synced += 1

            except Exception as e:
                log.error(
                    "❌ [ENGINE] Failed | client=%s | service=%s | error=%s",
                    client_name, service_key, e, exc_info=True,
                )
                # ── Rollback broken transaction so next service runs cleanly ──
                try:
                    conn.rollback()
                    log.info(
                        "[ENGINE] Transaction rolled back | client=%s | service=%s",
                        client_name, service_key,
                    )
                except Exception as rb_err:
                    log.error("[ENGINE] Rollback failed | error=%s", rb_err)
                total_failed  += 1
                client_failed  = True  # mark client as failed — do NOT update last_synced_at

        # ── STEP 4: Update last_synced_at in client_registry ONCE per client ─
        # Only update if ALL services synced successfully
        # If any service failed → keep old last_synced_at so next run retries from same point
        if not client_failed:
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
            log.info(
                "✅ [ENGINE] last_synced_at updated | client=%s",
                client_name,
            )
        else:
            log.warning(
                "⚠️ [ENGINE] Skipping last_synced_at update due to failures | client=%s",
                client_name,
            )

    log.info("═" * 60)
    log.info(
        "✅ [ENGINE] Sync run complete | synced=%d | failed=%d",
        total_synced, total_failed,
    )
    log.info("═" * 60)