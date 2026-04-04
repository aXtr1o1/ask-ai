import psycopg2.extras
from .config import log


# ─────────────────────────────────────────────────────────────
# UPSERT — PPM
# Uses COUNT before/after to accurately split insert vs update
# ─────────────────────────────────────────────────────────────
def upsert_ppm(cursor, records: list, user_id: int, user_name: str):
    inserted = updated = errors = 0
    try:
        # ── Deduplicate by WorkOrder — keep last occurrence ───
        seen = {}
        for r in records:
            key = r.get("WorkOrder") or ""
            seen[key] = r
        records = list(seen.values())

        # ── COUNT before upsert ───────────────────────────────
        cursor.execute(
            'SELECT COUNT(*) FROM public.ppm WHERE user_name = %s',
            (user_name,)
        )
        before_count = cursor.fetchone()[0]
        log.info(f"    [PPM] Records in DB before upsert: {before_count}")

        rows = [
            (
                user_id, user_name,
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
            )
            for r in records
        ]

        psycopg2.extras.execute_values(cursor, """
            INSERT INTO public.ppm (
                user_id, user_name,
                "WorkOrder", "AssetTagNo", "EquipmentRefNo",
                "PPMStatus", "PPMStageName", "FrequencyName",
                "WoDateTime", "WoCompletedDate",
                "LocalityName", "LocalityCode", "BuildingName", "FloorName", "SpotName",
                "EquipmentName", "DivisionName", "DisciplineName", "ContractName",
                "PMTechName", "PMTechStartDateTime", "PMTechEndDateTime", "PMTechRemarks",
                "LastStandByRemarks", "PPMPendingPeriod", "SLADuration"
            ) VALUES %s
            ON CONFLICT ("WorkOrder") DO UPDATE SET
                user_id               = EXCLUDED.user_id,
                user_name             = EXCLUDED.user_name,
                "PPMStatus"           = EXCLUDED."PPMStatus",
                "PPMStageName"        = EXCLUDED."PPMStageName",
                "WoCompletedDate"     = EXCLUDED."WoCompletedDate",
                "PMTechName"          = EXCLUDED."PMTechName",
                "PMTechStartDateTime" = EXCLUDED."PMTechStartDateTime",
                "PMTechEndDateTime"   = EXCLUDED."PMTechEndDateTime",
                "PMTechRemarks"       = EXCLUDED."PMTechRemarks",
                "PPMPendingPeriod"    = EXCLUDED."PPMPendingPeriod",
                "LastStandByRemarks"  = EXCLUDED."LastStandByRemarks",
                updated_at            = NOW()
        """, rows, page_size=1000)

        # ── COUNT after upsert ────────────────────────────────
        cursor.execute(
            'SELECT COUNT(*) FROM public.ppm WHERE user_name = %s',
            (user_name,)
        )
        after_count = cursor.fetchone()[0]
        log.info(f"    [PPM] Records in DB after upsert: {after_count}")

        # ── Accurate split ────────────────────────────────────
        inserted = after_count - before_count
        updated  = len(records) - inserted

    except Exception as e:
        log.error(f"    ⚠️  PPM batch upsert failed: {e}")
        errors = len(records)

    log.info(
        f"    PPM → Sent={len(records)} | "
        f"Inserted={inserted} (new rows) | "
        f"Updated={updated} (existing rows) | "
        f"Errors={errors}"
    )
    return inserted, updated, errors