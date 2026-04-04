import psycopg2.extras
from .config import log


# ─────────────────────────────────────────────────────────────
# UPSERT — FacilityAudit (FA)
# Uses COUNT before/after to accurately split insert vs update
# Unique key: (user_name, RMComplaintNo)
# ─────────────────────────────────────────────────────────────
def upsert_fa(cursor, records: list, user_id: int, user_name: str):
    inserted = updated = errors = 0
    try:
        # ── Deduplicate by RMComplaintNo — keep last occurrence
        seen = {}
        for r in records:
            key = r.get("RMComplaintNo") or ""
            seen[key] = r
        records = list(seen.values())

        # ── COUNT before upsert ───────────────────────────────
        cursor.execute(
            'SELECT COUNT(*) FROM public."FacilityAudit" WHERE user_name = %s',
            (user_name,)
        )
        before_count = cursor.fetchone()[0]
        log.info(f"    [FA] Records in DB before upsert: {before_count}")

        rows = [
            (
                user_id, user_name,

                # Core Complaint Fields
                r.get("RMCCMComplaintIDPK"),
                r.get("RMCCMComplaintCode"),
                r.get("RMComplaintNo") or "",
                r.get("RMComplainedDateTime"),
                r.get("RMBDMWOCompletedDate"),
                r.get("RMOverDueTime"),
                r.get("RMETADate"),
                r.get("RMRequestDetailsDesc"),
                r.get("RMTechnicalFindings"),
                r.get("RMMaintenanceRemarks"),
                r.get("RMDownloadStat") or 0,
                r.get("RMTotalAmount"),
                r.get("RMMaintenanceHrs"),
                r.get("RMManPower"),
                r.get("RMManHours"),
                r.get("RMFlowSeqNo"),
                r.get("RMBDMStageDesc"),
                r.get("RMXComplaintNo"),
                r.get("RMXComplaintDate"),
                r.get("RMResponseTime"),
                r.get("RMResolutionTime"),

                # Flags
                r.get("IsRMBMS"),
                r.get("IsRMRework"),
                r.get("IsRMWithdraw") or False,
                r.get("IsRMTechManual"),
                r.get("IsRMCCMAnaliyseClosed"),
                r.get("IsDraft") or False,
                r.get("IsActive") if r.get("IsActive") is not None else True,
                r.get("DeleStat") or False,

                # Rework / Withdraw
                r.get("ReworkRemarks"),
                r.get("RMWithdrawRemarks"),

                # Technician
                r.get("RMTechName"),
                r.get("RMTechRemarks"),
                r.get("RMTeStartDateTime"),
                r.get("RMTeEndDateTime"),

                # Location
                r.get("BDMLongitude"),
                r.get("BDMLattitude"),
                r.get("LocalityCode"),
                r.get("LocalityName"),
                r.get("BuildingCode"),
                r.get("BuildingName"),
                r.get("FloorName"),
                r.get("SpotName"),

                # Contract & Division
                r.get("ContractCode"),
                r.get("ContractName"),
                r.get("DivisionCode"),
                r.get("DivisionName"),

                # Stage & Frequency
                r.get("RMStageSeqNo"),
                r.get("RMStageName"),
                r.get("FrequencyCode"),
                r.get("FrequencyName"),

                # Priority & Category
                r.get("PriorityName"),
                r.get("RMCategoryName"),
                r.get("RMCategorySubName"),

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
            INSERT INTO public."FacilityAudit" (
                user_id, user_name,
                "RMCCMComplaintIDPK", "RMCCMComplaintCode", "RMComplaintNo",
                "RMComplainedDateTime", "RMBDMWOCompletedDate", "RMOverDueTime",
                "RMETADate", "RMRequestDetailsDesc", "RMTechnicalFindings",
                "RMMaintenanceRemarks", "RMDownloadStat", "RMTotalAmount",
                "RMMaintenanceHrs", "RMManPower", "RMManHours",
                "RMFlowSeqNo", "RMBDMStageDesc",
                "RMXComplaintNo", "RMXComplaintDate",
                "RMResponseTime", "RMResolutionTime",
                "IsRMBMS", "IsRMRework", "IsRMWithdraw", "IsRMTechManual",
                "IsRMCCMAnaliyseClosed", "IsDraft", "IsActive", "DeleStat",
                "ReworkRemarks", "RMWithdrawRemarks",
                "RMTechName", "RMTechRemarks",
                "RMTeStartDateTime", "RMTeEndDateTime",
                "BDMLongitude", "BDMLattitude",
                "LocalityCode", "LocalityName",
                "BuildingCode", "BuildingName",
                "FloorName", "SpotName",
                "ContractCode", "ContractName",
                "DivisionCode", "DivisionName",
                "RMStageSeqNo", "RMStageName",
                "FrequencyCode", "FrequencyName",
                "PriorityName", "RMCategoryName", "RMCategorySubName",
                "Remarks", "FilePath",
                "CreatedUserID", "CreatedTtm", "UpdatedTtm"
            ) VALUES %s
            ON CONFLICT (user_name, "RMComplaintNo") DO UPDATE SET
                user_id                  = EXCLUDED.user_id,
                user_name                = EXCLUDED.user_name,
                "RMBDMWOCompletedDate"   = EXCLUDED."RMBDMWOCompletedDate",
                "RMOverDueTime"          = EXCLUDED."RMOverDueTime",
                "RMTechnicalFindings"    = EXCLUDED."RMTechnicalFindings",
                "RMMaintenanceRemarks"   = EXCLUDED."RMMaintenanceRemarks",
                "RMMaintenanceHrs"       = EXCLUDED."RMMaintenanceHrs",
                "RMResponseTime"         = EXCLUDED."RMResponseTime",
                "RMResolutionTime"       = EXCLUDED."RMResolutionTime",
                "IsRMRework"             = EXCLUDED."IsRMRework",
                "IsRMWithdraw"           = EXCLUDED."IsRMWithdraw",
                "IsRMCCMAnaliyseClosed"  = EXCLUDED."IsRMCCMAnaliyseClosed",
                "IsActive"               = EXCLUDED."IsActive",
                "ReworkRemarks"          = EXCLUDED."ReworkRemarks",
                "RMWithdrawRemarks"      = EXCLUDED."RMWithdrawRemarks",
                "RMTechName"             = EXCLUDED."RMTechName",
                "RMTechRemarks"          = EXCLUDED."RMTechRemarks",
                "RMTeStartDateTime"      = EXCLUDED."RMTeStartDateTime",
                "RMTeEndDateTime"        = EXCLUDED."RMTeEndDateTime",
                "RMStageName"            = EXCLUDED."RMStageName",
                "RMStageSeqNo"           = EXCLUDED."RMStageSeqNo",
                "UpdatedTtm"             = EXCLUDED."UpdatedTtm",
                updated_at               = NOW()
        """, rows, page_size=1000)

        # ── COUNT after upsert ────────────────────────────────
        cursor.execute(
            'SELECT COUNT(*) FROM public."FacilityAudit" WHERE user_name = %s',
            (user_name,)
        )
        after_count = cursor.fetchone()[0]
        log.info(f"    [FA] Records in DB after upsert: {after_count}")

        # ── Accurate split ────────────────────────────────────
        inserted = after_count - before_count
        updated  = len(records) - inserted

    except Exception as e:
        log.error(f"    ⚠️  FA batch upsert failed: {e}")
        errors = len(records)

    log.info(
        f"    FA → Sent={len(records)} | "
        f"Inserted={inserted} (new rows) | "
        f"Updated={updated} (existing rows) | "
        f"Errors={errors}"
    )
    return inserted, updated, errors