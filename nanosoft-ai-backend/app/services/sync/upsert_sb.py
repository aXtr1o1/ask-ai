import psycopg2.extras
from .config import log


# ─────────────────────────────────────────────────────────────
# UPSERT — ScheduleBased (SB)
# Uses COUNT before/after to accurately split insert vs update
# Unique key: (user_name, SBCreWorkOrder)
# ─────────────────────────────────────────────────────────────
def upsert_sb(cursor, records: list, user_id: int, user_name: str):
    inserted = updated = errors = 0
    try:
        # ── Deduplicate by SBCreWorkOrder — keep last occurrence
        seen = {}
        for r in records:
            key = r.get("SBCreWorkOrder") or ""
            seen[key] = r
        records = list(seen.values())

        # ── COUNT before upsert ───────────────────────────────
        cursor.execute(
            'SELECT COUNT(*) FROM public."ScheduleBased" WHERE user_name = %s',
            (user_name,)
        )
        before_count = cursor.fetchone()[0]
        log.info(f"    [SB] Records in DB before upsert: {before_count}")

        rows = [
            (
                user_id, user_name,

                # Core Work Order Fields
                r.get("SBCreMRNo"),
                r.get("SBCreWorkOrder") or "",
                r.get("SBCreWoDateTime"),
                r.get("SBCreGeneratedTtm"),
                r.get("SBCreActualDate"),
                r.get("SBCreWoCompletedDate"),
                r.get("SBCreParentCreationKey"),
                r.get("SBCreSLAHours"),
                r.get("SBCreMaintenanceHours"),

                # Flags
                r.get("IsSBCreWithDraw") or False,
                r.get("IsSbCreReschedule") or False,
                r.get("IsSBCreRework") or False,
                r.get("IsSBCreTechManual"),
                r.get("IsSBCreSupManual"),
                r.get("IsSBCreMaterial"),
                r.get("IsDraft") or False,
                r.get("IsActive") if r.get("IsActive") is not None else True,
                r.get("DeleStat") or False,

                # Remarks
                r.get("SBCreWithDrawRemarks"),
                r.get("SBCreRescheduleRemarks"),
                r.get("SBCreReworkRemarks"),

                # Technician
                r.get("SBTechName"),
                r.get("PMTechRemarks"),
                r.get("PMSBLastSBRemarks"),
                r.get("PMSBLastSBDateTime"),
                r.get("PMSBStaffAssignBy"),
                r.get("SBTechStartDateTime"),
                r.get("SBTechEndDateTime"),

                # Location
                r.get("SBCrePPMLattitude"),
                r.get("SBCrePPMLongitude"),
                r.get("LocalityCode"),
                r.get("LocalityName"),
                r.get("BuildingName"),
                r.get("FloorName"),
                r.get("SpotName"),

                # Contract & Division
                r.get("ContractCode"),
                r.get("ContractName"),
                r.get("DivisionCode"),
                r.get("DivisionName"),
                r.get("DisciplineCode"),
                r.get("DisciplineName"),

                # Stage & Frequency
                r.get("PPMStageName"),
                r.get("StageSeqNo"),
                r.get("FrequencyCode"),
                r.get("FrequencyName"),

                # Service
                r.get("ServiceTypCode"),
                r.get("ServiceTypeName"),

                # Ledger
                r.get("SBCreChargeLedgerKey"),
                r.get("SBCreCostLedgerKey"),

                # Misc
                r.get("Remarks"),
                r.get("FilePath"),
                r.get("CreatedUserID"),
                r.get("CreatedTtm"),
                r.get("UpdatedTtm"),
            )
            for r in records
        ]

        psycopg2.extras.execute_values(cursor, """
            INSERT INTO public."ScheduleBased" (
                user_id, user_name,
                "SBCreMRNo", "SBCreWorkOrder", "SBCreWoDateTime",
                "SBCreGeneratedTtm", "SBCreActualDate", "SBCreWoCompletedDate",
                "SBCreParentCreationKey", "SBCreSLAHours", "SBCreMaintenanceHours",
                "IsSBCreWithDraw", "IsSbCreReschedule", "IsSBCreRework",
                "IsSBCreTechManual", "IsSBCreSupManual", "IsSBCreMaterial",
                "IsDraft", "IsActive", "DeleStat",
                "SBCreWithDrawRemarks", "SBCreRescheduleRemarks", "SBCreReworkRemarks",
                "SBTechName", "PMTechRemarks", "PMSBLastSBRemarks",
                "PMSBLastSBDateTime", "PMSBStaffAssignBy",
                "SBTechStartDateTime", "SBTechEndDateTime",
                "SBCrePPMLattitude", "SBCrePPMLongitude",
                "LocalityCode", "LocalityName",
                "BuildingName", "FloorName", "SpotName",
                "ContractCode", "ContractName",
                "DivisionCode", "DivisionName",
                "DisciplineCode", "DisciplineName",
                "PPMStageName", "StageSeqNo",
                "FrequencyCode", "FrequencyName",
                "ServiceTypCode", "ServiceTypeName",
                "SBCreChargeLedgerKey", "SBCreCostLedgerKey",
                "Remarks", "FilePath",
                "CreatedUserID", "CreatedTtm", "UpdatedTtm"
            ) VALUES %s
            ON CONFLICT (user_name, "SBCreWorkOrder") DO UPDATE SET
                user_id                  = EXCLUDED.user_id,
                user_name                = EXCLUDED.user_name,
                "SBCreWoCompletedDate"   = EXCLUDED."SBCreWoCompletedDate",
                "IsSBCreWithDraw"        = EXCLUDED."IsSBCreWithDraw",
                "IsSbCreReschedule"      = EXCLUDED."IsSbCreReschedule",
                "IsSBCreRework"          = EXCLUDED."IsSBCreRework",
                "IsSBCreMaterial"        = EXCLUDED."IsSBCreMaterial",
                "IsActive"               = EXCLUDED."IsActive",
                "SBCreWithDrawRemarks"   = EXCLUDED."SBCreWithDrawRemarks",
                "SBCreRescheduleRemarks" = EXCLUDED."SBCreRescheduleRemarks",
                "SBCreReworkRemarks"     = EXCLUDED."SBCreReworkRemarks",
                "SBTechName"             = EXCLUDED."SBTechName",
                "PMTechRemarks"          = EXCLUDED."PMTechRemarks",
                "PMSBLastSBRemarks"      = EXCLUDED."PMSBLastSBRemarks",
                "PMSBLastSBDateTime"     = EXCLUDED."PMSBLastSBDateTime",
                "PMSBStaffAssignBy"      = EXCLUDED."PMSBStaffAssignBy",
                "SBTechStartDateTime"    = EXCLUDED."SBTechStartDateTime",
                "SBTechEndDateTime"      = EXCLUDED."SBTechEndDateTime",
                "PPMStageName"           = EXCLUDED."PPMStageName",
                "StageSeqNo"             = EXCLUDED."StageSeqNo",
                "SBCreSLAHours"          = EXCLUDED."SBCreSLAHours",
                "SBCreMaintenanceHours"  = EXCLUDED."SBCreMaintenanceHours",
                "UpdatedTtm"             = EXCLUDED."UpdatedTtm",
                updated_at               = NOW()
        """, rows, page_size=1000)

        # ── COUNT after upsert ────────────────────────────────
        cursor.execute(
            'SELECT COUNT(*) FROM public."ScheduleBased" WHERE user_name = %s',
            (user_name,)
        )
        after_count = cursor.fetchone()[0]
        log.info(f"    [SB] Records in DB after upsert: {after_count}")

        # ── Accurate split ────────────────────────────────────
        inserted = after_count - before_count
        updated  = len(records) - inserted

    except Exception as e:
        log.error(f"    ⚠️  SB batch upsert failed: {e}")
        errors = len(records)

    log.info(
        f"    SB → Sent={len(records)} | "
        f"Inserted={inserted} (new rows) | "
        f"Updated={updated} (existing rows) | "
        f"Errors={errors}"
    )
    return inserted, updated, errors