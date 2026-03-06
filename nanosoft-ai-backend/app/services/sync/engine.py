from datetime import datetime, timezone, timedelta

from app.api.database.postgres_client import get_pool
from app.config import settings

from .config import log, ENDPOINTS
from .db_helpers import get_clients, update_sync_timestamp
from .fetcher import fetch_single_page, fetch_login
from .upsert_assets import upsert_assets
from .upsert_ppm import upsert_ppm
from .upsert_bdm import upsert_bdm


# ─────────────────────────────────────────────────────────────

# Deduplicates a list of records by a given key field

# ─────────────────────────────────────────────────────────────
def _dedup(records: list, key: str) -> list:
    seen = {}
    for r in records:
        seen[r.get(key) or ""] = r
    return list(seen.values())


# ─────────────────────────────────────────────────────────────
# CORE SYNC LOGIC
# 1. Login per client → get fresh jwt_token + api_user_id
# 2. Use api jwt + api_user_id for fetching data from API
# 3. Use db user_id + user_name for upserting into tables
# Collects ALL pages first → global dedup → single upsert
# fetched count = true unique records only (no duplicates)
# ─────────────────────────────────────────────────────────────
def run_sync() -> dict:
    sync_start = datetime.now(timezone.utc)
    log.info("=" * 60)
    log.info(f"🚀 SYNC STARTED at {sync_start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    log.info("=" * 60)

    summary = {"started_at": sync_start.isoformat(), "clients": []}

    try:
        conn   = get_pool()
        cursor = conn.cursor()
    except Exception as e:
        log.critical(f"❌ DB connection failed: {e}")
        return {"error": str(e)}

    clients = get_clients(cursor)
    log.info(f"📋 Found {len(clients)} client(s) in client_sync_config")

    for (client_name, base_url, user_id, user_name, last_synced_at) in clients:
        log.info(f"\n{'─'*55}")
        log.info(f"👤 Client: {client_name} | user_id={user_id} | user_name={user_name} | {base_url}")

        client_summary = {
            "client":    client_name,
            "user_id":   user_id,
            "user_name": user_name,
            "status":    "ok",
            "endpoints": {},
            "synced_at": None,
        }

        # ── STEP 1: Login to get fresh token + api_user_id ───────
        api_jwt, api_user_id = fetch_login(base_url)
        if not api_jwt or not api_user_id:
            log.error(f"  ❌ Login failed for [{client_name}] — skipping client.")
            client_summary["status"] = "login_failed"
            summary["clients"].append(client_summary)
            continue

        log.info(f"  🔑 Login OK — api_user_id={api_user_id} (db user_id={user_id} | db user_name={user_name})")

        if last_synced_at is None:
            log.info("   ℹ️  First-ever sync — fetching ALL records from API.")
        else:
            log.info(f"   🕒 Last synced at: {last_synced_at.strftime('%Y-%m-%d %H:%M:%S UTC')} — fetching changes since then.")

        synced_any = False

        for endpoint in ENDPOINTS:
            log.info(f"\n  🔄 Endpoint: {endpoint}")

            page_index  = 1
            all_records = []    # ← collect ALL pages here
            endpoint_ok = True

            # ── STEP 2: Collect ALL pages first ──────────────────
            while True:
                try:
                    records = fetch_single_page(
                        base_url, api_jwt, api_user_id,
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
                client_summary["endpoints"][endpoint] = {
                    "records_fetched": 0,
                    "inserted":        0,
                    "updated":         0,
                    "errors":          0,
                    "status":          "ok" if endpoint_ok else "error",
                }
                continue

            # ── STEP 3: Global dedup across ALL pages ─────────────
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
                log.info(f"  [{endpoint}] ⚠️  Removed {dupes_removed} duplicate(s) from API — {dedup_count} unique records remain.")

            # ── STEP 4: Single upsert with clean unique records ───
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
                synced_any = True

            except Exception as e:
                log.error(f"  ❌ Upsert crashed for {endpoint}: {e}")
                conn.rollback()
                endpoint_ok = False
                err = dedup_count

            # ── free memory ───────────────────────────────────────
            del all_records

            # ── endpoint summary ──────────────────────────────────
            client_summary["endpoints"][endpoint] = {
                "records_fetched": dedup_count,   # ← true unique count
                "inserted":        ins,
                "updated":         upd,
                "errors":          err,
                "status":          "ok" if endpoint_ok else "error",
            }
            log.info(f"  [{endpoint}] ✅ Total: fetched={dedup_count} | inserted={ins} | updated={upd} | errors={err}")

        # ── commit all endpoints for this client ──────────────────
        if synced_any:
            try:
                update_sync_timestamp(cursor, client_name)
                conn.commit()
                client_summary["synced_at"] = datetime.now(timezone.utc).isoformat()
                log.info(f"\n  ✅ Committed all data for [{client_name}] — last_synced_at updated.")
            except Exception as e:
                log.error(f"  ❌ Commit failed for [{client_name}]: {e}")
                conn.rollback()
                client_summary["status"] = "commit_failed"
        else:
            log.info(f"  ℹ️  No new data for [{client_name}] this cycle — last_synced_at unchanged.")
            client_summary["status"] = "no_new_data"

        summary["clients"].append(client_summary)

    cursor.close()
    conn.close()

    elapsed        = (datetime.now(timezone.utc) - sync_start).total_seconds()
    next_sync_time = (datetime.now(timezone.utc) + timedelta(minutes=settings.SYNC_INTERVAL_MINUTES)).strftime("%Y-%m-%d %H:%M:%S UTC")

    log.info(f"\n{'='*60}")
    log.info(f"✅ SYNC COMPLETED in {round(elapsed, 2)}s")
    log.info(f"😴 Sync engine SLEEPING — next sync in {settings.SYNC_INTERVAL_MINUTES} minute(s)")
    log.info(f"⏰ Next sync at: {next_sync_time}")
    log.info(f"{'='*60}\n")

    summary["elapsed_seconds"] = round(elapsed, 2)
    return summary
