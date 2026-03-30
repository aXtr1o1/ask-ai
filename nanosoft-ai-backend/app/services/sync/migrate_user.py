"""
migrate_user.py — On-demand single user data migration
Called manually when a new user is added to the system.

Usage:
    from app.services.sync.migrate_user import migrate_user

    migrate_user(
        client_name = "ClientA",
        base_url    = "https://api.clienta.com",
        user_id     = 101,
        user_name   = "clienta_user",
        jwt_token   = "eyJhbGciOi..."
    )
"""

import logging
from datetime import datetime, timezone

from app.api.database.postgres_client import get_pool
from .config import ENDPOINTS
from .fetcher import fetch_single_page
from .upsert_assets import upsert_assets
from .upsert_ppm import upsert_ppm
from .upsert_bdm import upsert_bdm

log = logging.getLogger("migrate_user")
log.setLevel(logging.INFO)
_ch = logging.StreamHandler()
_ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
if not log.handlers:
    log.addHandler(_ch)


# ─────────────────────────────────────────────────────────────
# Deduplicates a list of records by a given key field
# ─────────────────────────────────────────────────────────────
def _dedup(records: list, key: str) -> list:
    seen = {}
    for r in records:
        seen[r.get(key) or ""] = r
    return list(seen.values())


# ─────────────────────────────────────────────────────────────
# MIGRATE USER
# 1. Insert new row into client_sync_config (last_synced_at = NULL)
#    → If client_name already exists → skip insert, log warning
# 2. Fetch ALL data from all 3 endpoints using provided jwt + user_id
# 3. Upsert records into Asset / ppm / bdm tables
# 4. Update last_synced_at = NOW() only after all migrations succeed
# ─────────────────────────────────────────────────────────────

def migrate_user(
    client_name: str,
    base_url:    str,
    user_id:     int,
    user_name:   str,
    jwt_token:   str,
) -> dict:

    migrate_start = datetime.now(timezone.utc)
    log.info("=" * 60)
    log.info(f"🚀 MIGRATE USER STARTED | client={client_name} | user_id={user_id} | user_name={user_name}")
    log.info("=" * 60)

    summary = {
        "client_name": client_name,
        "user_id":     user_id,
        "user_name":   user_name,
        "status":      "ok",
        "endpoints":   {},
        "synced_at":   None,
    }

    # ── Connect to DB ─────────────────────────────────────────
    try:
        conn   = get_pool()
        cursor = conn.cursor()
    except Exception as e:
        log.critical(f"❌ DB connection failed: {e}")
        return {"error": str(e)}

    # ── STEP 1: Insert new row if client_name does not exist ──
    try:
        cursor.execute("""
            SELECT id FROM client_sync_config WHERE client_name = %s
        """, (client_name,))
        existing = cursor.fetchone()

        if existing:
            log.warning(f"  ⚠️  [{client_name}] already exists in client_sync_config — skipping INSERT.")
        else:
            cursor.execute("""
                INSERT INTO client_sync_config
                    (client_name, base_url, user_id, user_name, jwt_token, last_synced_at)
                VALUES
                    (%s, %s, %s, %s, %s, NULL)
            """, (client_name, base_url, user_id, user_name, jwt_token))
            conn.commit()
            log.info(f"  ✅ New row inserted into client_sync_config for [{client_name}] — last_synced_at=NULL")

    except Exception as e:
        log.error(f"  ❌ Failed to insert/check client_sync_config for [{client_name}]: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        summary["status"] = "insert_failed"
        return summary

    # ── STEP 2 + 3: Fetch + Upsert for all 3 endpoints ───────
    # last_synced_at = None → fetches ALL records (full initial load)
    last_synced_at = None
    synced_any     = False

    for endpoint in ENDPOINTS:
        log.info(f"\n  🔄 Endpoint: {endpoint}")

        page_index  = 1
        all_records = []
        endpoint_ok = True

        # ── Collect ALL pages ─────────────────────────────────
        while True:
            try:
                records = fetch_single_page(
                    base_url, jwt_token, user_id,
                    endpoint, last_synced_at, page_index
                )
            except Exception as e:
                log.error(f"  ❌ fetch page {page_index} crashed for {endpoint}: {e}")
                endpoint_ok = False
                break

            if not records:
                if page_index == 1:
                    log.info(f"  ℹ️  {endpoint} returned 0 records — nothing to upsert.")
                else:
                    log.info(f"  [{endpoint}] Pagination complete at page {page_index}.")
                break

            log.info(f"  [{endpoint}] Page {page_index} → {len(records)} records (total so far: {len(all_records) + len(records)})")
            all_records.extend(records)
            page_index += 1

        # ── nothing fetched → skip upsert ─────────────────────
        if not all_records:
            summary["endpoints"][endpoint] = {
                "records_fetched": 0,
                "inserted":        0,
                "updated":         0,
                "errors":          0,
                "status":          "ok" if endpoint_ok else "error",
            }
            continue

        # ── Global dedup across ALL pages ──────────────────────
        raw_count = len(all_records)

        if endpoint == "/getAssets":
            all_records = _dedup(all_records, "AssetTagNo")
        elif endpoint == "/getPPM":
            all_records = _dedup(all_records, "WorkOrder")
        elif endpoint == "/getBDM":
            all_records = _dedup(all_records, "ComplaintNo")

        dedup_count   = len(all_records)
        dupes_removed = raw_count - dedup_count

        if dupes_removed > 0:
            log.info(f"  [{endpoint}] ⚠️  Removed {dupes_removed} duplicate(s) — {dedup_count} unique records remain.")

        # ── Single upsert with clean unique records ─────────────
        ins = upd = err = 0
        try:
            if endpoint == "/getAssets":
                ins, upd, err = upsert_assets(cursor, all_records, user_id, user_name)
            elif endpoint == "/getPPM":
                ins, upd, err = upsert_ppm(cursor, all_records, user_id, user_name)
            elif endpoint == "/getBDM":
                ins, upd, err = upsert_bdm(cursor, all_records, user_id, user_name)
            else:
                log.warning(f"  Unknown endpoint {endpoint} — skipping.")
                del all_records
                continue

            if err > 0:
                conn.rollback()
            else:
                synced_any = True

        except Exception as e:
            log.error(f"  ❌ Upsert crashed for {endpoint}: {e}")
            conn.rollback()
            endpoint_ok = False
            err = dedup_count

        # ── free memory ────────────────────────────────────────
        del all_records

        summary["endpoints"][endpoint] = {
            "records_fetched": dedup_count,
            "inserted":        ins,
            "updated":         upd,
            "errors":          err,
            "status":          "ok" if endpoint_ok else "error",
        }
        log.info(f"  [{endpoint}] ✅ fetched={dedup_count} | inserted={ins} | updated={upd} | errors={err}")

    # ── STEP 4: Update last_synced_at only if all succeeded ───
    if synced_any:
        try:
            cursor.execute("""
                UPDATE client_sync_config
                SET last_synced_at = now()
                WHERE client_name = %s
            """, (client_name,))
            conn.commit()
            summary["synced_at"] = datetime.now(timezone.utc).isoformat()
            log.info(f"\n  ✅ last_synced_at updated for [{client_name}] — migration complete.")
            summary["status"] = "ok"
        except Exception as e:
            log.error(f"  ❌ Failed to update last_synced_at for [{client_name}]: {e}")
            conn.rollback()
            summary["status"] = "timestamp_update_failed"
    else:
        log.info(f"  ℹ️  No data migrated for [{client_name}] — last_synced_at left as NULL for retry.")
        summary["status"] = "no_data_migrated"

    elapsed = (datetime.now(timezone.utc) - migrate_start).total_seconds()
    log.info(f"\n{'='*60}")
    log.info(f"✅ MIGRATE USER COMPLETED in {round(elapsed, 2)}s | client={client_name}")
    log.info(f"{'='*60}\n")

    summary["elapsed_seconds"] = round(elapsed, 2)
    
    cursor.close()
    conn.close()
    return summary
#you can use this function directly  for checking. direct file call .
# if __name__ == "__main__":
#     import sys
#     import logging

#     logging.basicConfig(
#         level=logging.INFO,
#         format="%(asctime)s | %(levelname)-8s | %(message)s",
#         datefmt="%Y-%m-%d %H:%M:%S",
#         handlers=[
#             logging.StreamHandler(),
#             logging.FileHandler("migrate_user.log", mode="a", encoding="utf-8"),
#         ],
#     )

#     result = migrate_user(
#         client_name = "v4demo",
#         base_url    = "https://v4demo.smartfm.cloud/askmeapi/",
#         user_id     = 101,
#         user_name   = "v4demo",
#         jwt_token   = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjEwMSwiaWF0IjoxNzc0MzQ5ODU2LCJleHAiOjE3NzQ0MzYyNTZ9.qMTAhrhbMqjuCUAMf9WtH1Fzi-QphZhBEz7yOdRF6GQ",
        
#     )

#     print("\n" + "=" * 60)
#     print("MIGRATION RESULT SUMMARY")
#     print("=" * 60)
#     print(f"Client     : {result.get('client_name')}")
#     print(f"Status     : {result.get('status')}")
#     print(f"Synced At  : {result.get('synced_at')}")
#     print(f"Elapsed    : {result.get('elapsed_seconds')}s")
#     print("\nEndpoint Breakdown:")
#     for endpoint, stats in result.get("endpoints", {}).items():
#         print(f"  {endpoint}")
#         print(f"    fetched  : {stats.get('records_fetched')}")
#         print(f"    inserted : {stats.get('inserted')}")
#         print(f"    updated  : {stats.get('updated')}")
#         print(f"    errors   : {stats.get('errors')}")
#         print(f"    status   : {stats.get('status')}")
#     print("=" * 60)