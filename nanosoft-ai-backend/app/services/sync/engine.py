"""
app/services/sync/engine.py
────────────────────────────
Cron sync engine — called by sync_runner.py every N minutes.

Flow:
    1. Load all active clients from client_registry
    2. For each client → load all active service_keys from client_service_registry
    3. For each service_key → get last_synced_at from client_sync_config
    4. Call sync_service_data() with last_synced_at (delta sync)
    5. Update last_synced_at in client_sync_config after success
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

    # ── STEP 1: Load all active clients ──────────────────────────
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT client_name, token, base_url
        FROM   client_registry
        WHERE  is_active = true
        """
    )
    clients = cursor.fetchall()
    cursor.close()

    log.info("[ENGINE] Found %d active client(s)", len(clients))

    total_synced  = 0
    total_failed  = 0

    for client_name, token, base_url in clients:

        log.info("[ENGINE] ── Processing client: %s", client_name)

        # ── STEP 2: Load all active service_keys for this client ─
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
            "[ENGINE] Client=%s | Found %d service(s): %s",
            client_name, len(services), [s[0] for s in services]
        )

        for service_key, endpoint, unique_field in services:

            # ── STEP 3: Get last_synced_at from client_sync_config
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, last_synced_at, user_id
                FROM   client_sync_config
                WHERE  client_name  = %s
                AND    service_key  = %s
                AND    is_active    = true
                """,
                (client_name, service_key),
            )
            rows = cursor.fetchall()
            cursor.close()

            if not rows:
                log.warning(
                    "[ENGINE] ⚠️ No sync config found | client=%s | service=%s — skipping",
                    client_name, service_key,
                )
                continue

            for config_id, last_synced_at, user_id in rows:

                log.info(
                    "[ENGINE] Syncing | client=%s | user_id=%s | service=%s | last_synced_at=%s",
                    client_name, user_id, service_key, last_synced_at,
                )

                try:
                    # ── STEP 4: Call sync_service_data() ─────────
                    summary = sync_service_data(
                        conn          = conn,
                        client_name   = client_name,
                        user_id       = user_id,
                        service_key   = service_key,
                        base_url      = base_url,
                        jwt_token     = token,
                        endpoint      = endpoint,
                        unique_field  = unique_field,
                        last_synced_at= last_synced_at,
                    )

                    # ── STEP 5: Update last_synced_at ─────────────
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE client_sync_config
                        SET    last_synced_at = %s
                        WHERE  id = %s
                        """,
                        (datetime.now(timezone.utc), config_id),
                    )
                    conn.commit()
                    cursor.close()

                    log.info(
                        "✅ [ENGINE] Done | client=%s | service=%s | inserted=%d | pages=%d",
                        client_name, service_key,
                        summary["inserted"], summary["pages_fetched"],
                    )
                    total_synced += 1

                except Exception as e:
                    log.error(
                        "❌ [ENGINE] Failed | client=%s | service=%s | error=%s",
                        client_name, service_key, e, exc_info=True,
                    )
                    total_failed += 1

    log.info("═" * 60)
    log.info(
        "✅ [ENGINE] Sync run complete | synced=%d | failed=%d",
        total_synced, total_failed,
    )
    log.info("═" * 60)