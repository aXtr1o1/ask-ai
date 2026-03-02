import logging
import time
from datetime import datetime, timezone, timedelta

import psycopg2.extras
import requests
from requests.exceptions import RequestException, Timeout

from app.api.database.postgres_client import get_db_connection
from app.config import settings

# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────
log = logging.getLogger("sync_engine")

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
ENDPOINTS       = ["/getAssets", "/getPPM", "/getBDM"]
REQUEST_TIMEOUT = 120
MAX_RETRIES     = 3
PAGE_SIZE       = settings.SYNC_PAGE_SIZE


# ─────────────────────────────────────────────────────────────
# DB HELPERS
# ─────────────────────────────────────────────────────────────
def get_clients(cursor):
    cursor.execute("""
        SELECT client_name, base_url, user_id, jwt_token, last_synced_at
        FROM client_sync_config
        ORDER BY client_name
    """)
    return cursor.fetchall()


def update_sync_timestamp(cursor, client_name):
    cursor.execute("""
        UPDATE client_sync_config
        SET last_synced_at = now()
        WHERE client_name = %s
    """, (client_name,))
    log.info(f"[{client_name}] ✅ last_synced_at updated to NOW()")


# ─────────────────────────────────────────────────────────────
# FETCH — single page only (called per page to avoid memory spike)
# ─────────────────────────────────────────────────────────────
def fetch_single_page(base_url: str, jwt_token: str, user_id: int,
                      endpoint: str, last_synced_at, page_index: int) -> list:

    url = f"{base_url}/askmeapi{endpoint}"

    if last_synced_at is not None:
        if hasattr(last_synced_at, "astimezone"):
            synced_ts = last_synced_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            synced_ts = str(last_synced_at)
    else:
        synced_ts = None  # first-ever sync → API returns everything

    headers = {
        "x-auth":       f"Bearer {jwt_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "data": {
            "PageIndex":    page_index,
            "PageSize":     PAGE_SIZE,
            "UserId":       int(user_id),
            "JWT":          str(jwt_token),
            "LastSyncedAt": synced_ts,
        }
    }

    log.info(f"  [{endpoint}] Fetching page {page_index} (LastSyncedAt={synced_ts}) ...")

    response = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
            )
            break
        except (Timeout, RequestException) as e:
            if attempt == MAX_RETRIES:
                log.error(f"  [{endpoint}] Page {page_index} FAILED after {MAX_RETRIES} retries: {e}")
                return []
            log.warning(f"  [{endpoint}] Attempt {attempt}/{MAX_RETRIES} failed: {e} — retrying in 2s ...")
            time.sleep(2)

    if response is None:
        return []

    if response.status_code == 400 and "No records found" in response.text:
        log.info(f"  [{endpoint}] No more records at page {page_index}. Done.")
        return []

    if response.status_code != 200:
        log.error(f"  [{endpoint}] Unexpected status {response.status_code}: {response.text[:300]}")
        return []

    try:
        resp_json = response.json()
    except Exception as e:
        log.error(f"  [{endpoint}] Invalid JSON on page {page_index}: {e} | Body: {response.text[:300]}")
        return []

    return _extract_records(resp_json, endpoint, page_index)


def _extract_records(resp_json: dict, endpoint: str, page: int) -> list:
    output = resp_json.get("Output") or resp_json.get("output")
    if isinstance(output, dict):
        records = output.get("data") or output.get("Data") or []
    else:
        raw = resp_json.get("data") or resp_json.get("Data")
        if isinstance(raw, list):
            records = raw
        elif isinstance(raw, dict):
            records = (raw.get("records") or raw.get("Records") or
                       raw.get("data")    or raw.get("Data")    or
                       raw.get("items")   or raw.get("Items")   or [])
        else:
            records = []

    if not isinstance(records, list):
        records = []
    return records


# ─────────────────────────────────────────────────────────────
# UPSERT — assets
# ─────────────────────────────────────────────────────────────
def upsert_assets(cursor, records: list, user_id: int):
    inserted = updated = errors = 0
    for r in records:
        try:
            cursor.execute("""
                INSERT INTO asset (
                    user_id, "AssetTagNo", "AssetBarcode", "EquipmentName", "EquipmentRefNo",
                    "SerialNo", "StatusName", "ConditionName", "PriorityName",
                    "OnHold", "IsSnagged", "IsScraped",
                    "LocalityName", "BuildingName", "FloorName", "SpotName",
                    "Longitude", "Latitude", "AssetTypeName",
                    "DivisionName", "DisciplineName", "Owner",
                    "IsEnablePPM", "IsEnableBDM", "IsEnableBMS", "IsEnableDSM",
                    "MakeName", "ModelName", "YearOfManuf", "LifeInYear",
                    "PurDate", "PurValue", "InstalledDate", "ScrapDate", "ScrapValue",
                    "ServiceAreaName", "TradeGroupName", "DrawingNo", "Remarks"
                ) VALUES (
                    %s,%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,
                    %s,%s,%s,%s, %s,%s,%s, %s,%s,%s,
                    %s,%s,%s,%s, %s,%s,%s,%s,
                    %s,%s,%s,%s,%s, %s,%s,%s,%s
                )
                ON CONFLICT ("AssetTagNo") DO UPDATE SET
                    "StatusName"    = EXCLUDED."StatusName",
                    "ConditionName" = EXCLUDED."ConditionName",
                    "PriorityName"  = EXCLUDED."PriorityName",
                    "OnHold"        = EXCLUDED."OnHold",
                    "IsSnagged"     = EXCLUDED."IsSnagged",
                    "IsScraped"     = EXCLUDED."IsScraped",
                    "FloorName"     = EXCLUDED."FloorName",
                    "SpotName"      = EXCLUDED."SpotName",
                    "IsEnablePPM"   = EXCLUDED."IsEnablePPM",
                    "IsEnableBDM"   = EXCLUDED."IsEnableBDM",
                    "IsEnableBMS"   = EXCLUDED."IsEnableBMS",
                    "IsEnableDSM"   = EXCLUDED."IsEnableDSM",
                    "Remarks"       = EXCLUDED."Remarks"
            """, (
                user_id,
                r.get("AssetTagNo") or "",        r.get("AssetBarcode") or "",
                r.get("EquipmentName") or "",     r.get("EquipmentRefNo"),
                r.get("SerialNo"),                r.get("StatusName") or "",
                r.get("ConditionName") or "",     r.get("PriorityName") or "",
                r.get("OnHold") or False,         r.get("IsSnagged") or False,
                r.get("IsScraped") or False,      r.get("LocalityName") or "",
                r.get("BuildingName") or "",      r.get("FloorName") or "",
                r.get("SpotName") or "",          r.get("Longitude"),
                r.get("Latitude"),                r.get("AssetTypeName") or "",
                r.get("DivisionName") or "",      r.get("DisciplineName") or "",
                r.get("Owner") or "",             r.get("IsEnablePPM") or False,
                r.get("IsEnableBDM") or False,    r.get("IsEnableBMS") or False,
                r.get("IsEnableDSM") or False,    r.get("MakeName"),
                r.get("ModelName"),               r.get("YearOfManuf") or 0,
                r.get("LifeInYear"),              r.get("PurDate"),
                r.get("PurValue"),                r.get("InstalledDate"),
                r.get("ScrapDate"),               r.get("ScrapValue"),
                r.get("ServiceAreaName"),         r.get("TradeGroupName"),
                r.get("DrawingNo"),               r.get("Remarks"),
            ))
            if cursor.rowcount == 1:
                inserted += 1
            else:
                updated += 1
        except Exception as e:
            log.error(f"    ⚠️  Asset [{r.get('AssetTagNo')}]: {e}")
            errors += 1
    log.info(f"    Assets → Inserted: {inserted} | Updated: {updated} | Errors: {errors}")
    return inserted, updated, errors


# ─────────────────────────────────────────────────────────────
# UPSERT — ppm
# ─────────────────────────────────────────────────────────────
def upsert_ppm(cursor, records: list, user_id: int):
    inserted = updated = errors = 0
    for r in records:
        try:
            cursor.execute("""
                INSERT INTO ppm (
                    user_id, "WorkOrder", "AssetTagNo", "EquipmentRefNo",
                    "PPMStatus", "PPMStageName", "FrequencyName",
                    "WoDateTime", "WoCompletedDate",
                    "LocalityName", "LocalityCode", "BuildingName", "FloorName", "SpotName",
                    "EquipmentName", "DivisionName", "DisciplineName", "ContractName",
                    "PMTechName", "PMTechStartDateTime", "PMTechEndDateTime", "PMTechRemarks",
                    "LastStandByRemarks", "PPMPendingPeriod", "SLADuration"
                ) VALUES (
                    %s,%s,%s,%s, %s,%s,%s, %s,%s,
                    %s,%s,%s,%s,%s, %s,%s,%s,%s,
                    %s,%s,%s,%s, %s,%s,%s
                )
                ON CONFLICT ("WorkOrder") DO UPDATE SET
                    "PPMStatus"           = EXCLUDED."PPMStatus",
                    "PPMStageName"        = EXCLUDED."PPMStageName",
                    "WoCompletedDate"     = EXCLUDED."WoCompletedDate",
                    "PMTechName"          = EXCLUDED."PMTechName",
                    "PMTechStartDateTime" = EXCLUDED."PMTechStartDateTime",
                    "PMTechEndDateTime"   = EXCLUDED."PMTechEndDateTime",
                    "PMTechRemarks"       = EXCLUDED."PMTechRemarks",
                    "PPMPendingPeriod"    = EXCLUDED."PPMPendingPeriod",
                    "LastStandByRemarks"  = EXCLUDED."LastStandByRemarks"
            """, (
                user_id,
                r.get("WorkOrder") or "",         r.get("AssetTagNo") or "",
                r.get("EquipmentRefNo") or "",    r.get("PPMStatus") or "",
                r.get("PPMStageName") or "",      r.get("FrequencyName") or "",
                r.get("WoDateTime") or "",        r.get("WoCompletedDate"),
                r.get("LocalityName") or "",      r.get("LocalityCode") or "",
                r.get("BuildingName") or "",      r.get("FloorName"),
                r.get("SpotName"),                r.get("EquipmentName") or "",
                r.get("DivisionName") or "",      r.get("DisciplineName"),
                r.get("ContractName") or "",      r.get("PMTechName"),
                r.get("PMTechStartDateTime"),     r.get("PMTechEndDateTime"),
                r.get("PMTechRemarks"),           r.get("LastStandByRemarks"),
                r.get("PPMPendingPeriod"),        r.get("SLADuration") or 0,
            ))
            if cursor.rowcount == 1:
                inserted += 1
            else:
                updated += 1
        except Exception as e:
            log.error(f"    ⚠️  PPM [{r.get('WorkOrder')}]: {e}")
            errors += 1
    log.info(f"    PPM → Inserted: {inserted} | Updated: {updated} | Errors: {errors}")
    return inserted, updated, errors


# ─────────────────────────────────────────────────────────────
# UPSERT — bdm
# ─────────────────────────────────────────────────────────────
def upsert_bdm(cursor, records: list, user_id: int):
    inserted = updated = errors = 0
    for r in records:
        try:
            cursor.execute("""
                INSERT INTO bdm (
                    user_id, "ComplaintNo", "AssetTagNo", "AssetBarcode", "ClientWoNo",
                    "WoStatus", "PriorityName", "StageName",
                    "ComplainedDateTime", "BDMWOCompletedDate",
                    "LocalityName", "LocalityCode", "BuildingName", "FloorName", "SpotName",
                    "ComplaintTypeName", "ComplaintHeaderName",
                    "ComplaintModeName", "ComplaintNatureName",
                    "WoTypeName", "ServiceTypeName", "DivisionName", "DisciplineName", "ContractName",
                    "Description", "ComplainerName", "RegisterBy",
                    "AnalysisTechName", "ExecutionTechName",
                    "ResponseTAT", "ResolutionTAT",
                    "SLACCMStartDateTime", "SLACCMEndDateTime",
                    "SLABDMStartDateTime", "SLABDMEndDateTime",
                    "AnalysisStartTime", "AnalysisEndTime",
                    "ExecutionStartTime", "ExecutionEndTime",
                    "StandByRemarks"
                ) VALUES (
                    %s,%s,%s,%s,%s, %s,%s,%s, %s,%s,
                    %s,%s,%s,%s,%s, %s,%s, %s,%s,
                    %s,%s,%s,%s,%s, %s,%s,%s, %s,%s,
                    %s,%s, %s,%s, %s,%s, %s,%s, %s,%s, %s
                )
                ON CONFLICT ("ComplaintNo") DO UPDATE SET
                    "WoStatus"           = EXCLUDED."WoStatus",
                    "StageName"          = EXCLUDED."StageName",
                    "BDMWOCompletedDate" = EXCLUDED."BDMWOCompletedDate",
                    "AnalysisTechName"   = EXCLUDED."AnalysisTechName",
                    "ExecutionTechName"  = EXCLUDED."ExecutionTechName",
                    "ResponseTAT"        = EXCLUDED."ResponseTAT",
                    "ResolutionTAT"      = EXCLUDED."ResolutionTAT",
                    "StandByRemarks"     = EXCLUDED."StandByRemarks",
                    "AnalysisStartTime"  = EXCLUDED."AnalysisStartTime",
                    "AnalysisEndTime"    = EXCLUDED."AnalysisEndTime",
                    "ExecutionStartTime" = EXCLUDED."ExecutionStartTime",
                    "ExecutionEndTime"   = EXCLUDED."ExecutionEndTime"
            """, (
                user_id,
                r.get("ComplaintNo") or "",       r.get("AssetTagNo"),
                r.get("AssetBarcode"),            r.get("ClientWoNo"),
                r.get("WoStatus") or "",          r.get("PriorityName") or "",
                r.get("StageName"),               r.get("ComplainedDateTime") or "",
                r.get("BDMWOCompletedDate"),      r.get("LocalityName") or "",
                r.get("LocalityCode") or "",      r.get("BuildingName") or "",
                r.get("FloorName"),               r.get("SpotName"),
                r.get("ComplaintTypeName") or "", r.get("ComplaintHeaderName"),
                r.get("ComplaintModeName") or "", r.get("ComplaintNatureName"),
                r.get("WoTypeName") or "",        r.get("ServiceTypeName") or "",
                r.get("DivisionName"),            r.get("DisciplineName"),
                r.get("ContractName") or "",      r.get("Description"),
                r.get("ComplainerName"),          r.get("RegisterBy"),
                r.get("AnalysisTechName"),        r.get("ExecutionTechName"),
                r.get("ResponseTAT"),             r.get("ResolutionTAT"),
                r.get("SLACCMStartDateTime"),     r.get("SLACCMEndDateTime"),
                r.get("SLABDMStartDateTime"),     r.get("SLABDMEndDateTime"),
                r.get("AnalysisStartTime"),       r.get("AnalysisEndTime"),
                r.get("ExecutionStartTime"),      r.get("ExecutionEndTime"),
                r.get("StandByRemarks"),
            ))
            if cursor.rowcount == 1:
                inserted += 1
            else:
                updated += 1
        except Exception as e:
            log.error(f"    ⚠️  BDM [{r.get('ComplaintNo')}]: {e}")
            errors += 1
    log.info(f"    BDM → Inserted: {inserted} | Updated: {updated} | Errors: {errors}")
    return inserted, updated, errors


# ─────────────────────────────────────────────────────────────
# CORE SYNC LOGIC
# page-by-page → upsert → free memory → next page
# never loads all records at once → no memory spike
# ─────────────────────────────────────────────────────────────
def run_sync() -> dict:
    sync_start = datetime.now(timezone.utc)
    log.info("=" * 60)
    log.info(f"🚀 SYNC STARTED at {sync_start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    log.info("=" * 60)

    summary = {"started_at": sync_start.isoformat(), "clients": []}

    try:
        conn   = get_db_connection()
        cursor = conn.cursor()
    except Exception as e:
        log.critical(f"❌ DB connection failed: {e}")
        return {"error": str(e)}

    clients = get_clients(cursor)
    log.info(f"📋 Found {len(clients)} client(s) in client_sync_config")

    for (client_name, base_url, user_id, jwt_token, last_synced_at) in clients:
        log.info(f"\n{'─'*55}")
        log.info(f"👤 Client: {client_name} | user_id={user_id} | {base_url}")

        if last_synced_at is None:
            log.info("   ℹ️  First-ever sync — fetching ALL records from API.")
        else:
            log.info(f"   🕒 Last synced at: {last_synced_at.strftime('%Y-%m-%d %H:%M:%S UTC')} — fetching changes since then.")

        client_summary = {
            "client":    client_name,
            "user_id":   user_id,
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

                # ── upsert this page immediately ─────────────────────
                try:
                    if endpoint == "/getAssets":
                        ins, upd, err = upsert_assets(cursor, records, user_id)
                    elif endpoint == "/getPPM":
                        ins, upd, err = upsert_ppm(cursor, records, user_id)
                    elif endpoint == "/getBDM":
                        ins, upd, err = upsert_bdm(cursor, records, user_id)
                    else:
                        log.warning(f"  Unknown endpoint {endpoint} — skipping.")
                        break

                    total_ins += ins
                    total_upd += upd
                    total_err += err
                    synced_any = True

                except Exception as e:
                    log.error(f"  ❌ Upsert crashed for {endpoint} page {page_index}: {e}")
                    conn.rollback()
                    endpoint_ok = False
                    break

                # ── free page memory immediately ─────────────────────
                del records

                # ── if page was less than PAGE_SIZE → last page done ──
                # re-fetch to check is handled by next iteration returning []
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