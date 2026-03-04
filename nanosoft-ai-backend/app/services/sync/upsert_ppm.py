import psycopg2.extras
from .config import log

# UPSERT — ppm
# BATCH insert using execute_values → fast + no memory spike

def upsert_ppm(cursor, records: list, user_id: int, user_name: str):
    inserted = updated = errors = 0
    try:
        seen = {}
        for r in records:
            key = r.get("WorkOrder") or ""
            seen[key] = r
        records = list(seen.values())

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
            INSERT INTO ppm (
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

        inserted = len(records)

    except Exception as e:
        log.error(f"    ⚠️  PPM batch upsert failed: {e}")
        errors = len(records)

    log.info(f"    PPM → Upserted: {inserted} | Errors: {errors}")
    return inserted, updated, errors

