from datetime import datetime, timezone, timedelta

from app.api.database.postgres_client import get_pool
from app.config import settings

from .config import log, ENDPOINTS
from .db_helpers import get_clients, update_sync_timestamp
from .fetcher import fetch_single_page
from .upsert_assets import upsert_assets
from .upsert_ppm import upsert_ppm
from .upsert_bdm import upsert_bdm



# ─────────────────────────────────────────────────────────────
# CORE SYNC LOGIC
# page-by-page → batch upsert → free memory → next page
# never loads all records at once → no memory spike
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

    # user_name unpacked directly from DB row — zero hardcoding
    for (client_name, base_url, user_id, user_name, jwt_token, last_synced_at) in clients:
        log.info(f"\n{'─'*55}")
        log.info(f"👤 Client: {client_name} | user_id={user_id} | user_name={user_name} | {base_url}")

        if last_synced_at is None:
            log.info("   ℹ️  First-ever sync — fetching ALL records from API.")
        else:
            log.info(f"   🕒 Last synced at: {last_synced_at.strftime('%Y-%m-%d %H:%M:%S UTC')} — fetching changes since then.")

        client_summary = {
            "client":    client_name,
            "user_id":   user_id,
            "user_name": user_name,
            "status":    "ok",
            "endpoints": {},
            "synced_at": None,
        }
        synced_any = False

        for endpoint in ENDPOINTS:
            log.info(f"\n  🔄 Endpoint: {endpoint}")

            page_index    = 1
            total_fetched = 0
            total_ins     = 0
            total_upd     = 0
            total_err     = 0
            endpoint_ok   = True

            while True:
                # ── fetch ONE page only ──────────────────────────────
                try:
                    records = fetch_single_page(
                        base_url, jwt_token, user_id,
                        endpoint, last_synced_at, page_index
                    )
                except Exception as e:
                    log.error(f"  ❌ fetch page {page_index} crashed for {endpoint}: {e}")
                    endpoint_ok = False
                    break

                # ── no records → pagination done ─────────────────────
                if not records:
                    if page_index == 1:
                        log.info(f"  ℹ️  {endpoint} returned 0 records — nothing to upsert.")
                    else:
                        log.info(f"  [{endpoint}] Pagination complete at page {page_index}.")
                    break

                total_fetched += len(records)
                log.info(f"  [{endpoint}] Page {page_index} → {len(records)} records (total so far: {total_fetched})")

                # ── batch upsert this page immediately ───────────────
                try:
                    if endpoint == "/getAssets":
                        ins, upd, err = upsert_assets(cursor, records, user_id, user_name)
                    elif endpoint == "/getPPM":
                        ins, upd, err = upsert_ppm(cursor, records, user_id, user_name)
                    elif endpoint == "/getBDM":
                        ins, upd, err = upsert_bdm(cursor, records, user_id, user_name)
                    else:
                        log.warning(f"  Unknown endpoint {endpoint} — skipping.")
                        break

                    total_ins += ins
                    total_upd += upd
                    total_err += err
                    if err > 0:
                        conn.rollback()
                    synced_any = True

                except Exception as e:
                    log.error(f"  ❌ Upsert crashed for {endpoint} page {page_index}: {e}")
                    conn.rollback()
                    endpoint_ok = False
                    break

                # ── free page memory immediately ─────────────────────
                del records

                # ── next page ────────────────────────────────────────
                page_index += 1

            # ── endpoint summary ─────────────────────────────────────
            client_summary["endpoints"][endpoint] = {
                "records_fetched": total_fetched,
                "inserted":        total_ins,
                "updated":         total_upd,
                "errors":          total_err,
                "status":          "ok" if endpoint_ok else "error",
            }
            log.info(f"  [{endpoint}] ✅ Total: fetched={total_fetched} | inserted={total_ins} | updated={total_upd} | errors={total_err}")

        # ── commit all endpoints for this client ─────────────────────
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

