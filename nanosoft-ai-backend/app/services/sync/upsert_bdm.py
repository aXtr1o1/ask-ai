import psycopg2.extras
from .config import log


# ─────────────────────────────────────────────────────────────
# UPSERT — BDM
# Uses COUNT before/after to accurately split insert vs update
# ─────────────────────────────────────────────────────────────
def upsert_bdm(cursor, records: list, user_id: int, user_name: str):
    inserted = updated = errors = 0
    try:
        # ── Deduplicate by ComplaintNo — keep last occurrence ─
        seen = {}
        for r in records:
            key = r.get("ComplaintNo") or ""
            seen[key] = r
        records = list(seen.values())

        # ── COUNT before upsert ───────────────────────────────
        cursor.execute(
            'SELECT COUNT(*) FROM public.bdm WHERE user_name = %s',
            (user_name,)
        )
        before_count = cursor.fetchone()[0]
        log.info(f"    [BDM] Records in DB before upsert: {before_count}")

        rows = [
            (
                user_id, user_name,
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
            )
            for r in records
        ]

        psycopg2.extras.execute_values(cursor, """
            INSERT INTO public.bdm (
                user_id, user_name,
                "ComplaintNo", "AssetTagNo", "AssetBarcode", "ClientWoNo",
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
            ) VALUES %s
            ON CONFLICT (user_name, "ComplaintNo") DO UPDATE SET
                user_id              = EXCLUDED.user_id,
                user_name            = EXCLUDED.user_name,
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
                "ExecutionEndTime"   = EXCLUDED."ExecutionEndTime",
                updated_at           = NOW()
        """, rows, page_size=1000)

        # ── COUNT after upsert ────────────────────────────────
        cursor.execute(
            'SELECT COUNT(*) FROM public.bdm WHERE user_name = %s',
            (user_name,)
        )
        after_count = cursor.fetchone()[0]
        log.info(f"    [BDM] Records in DB after upsert: {after_count}")

        # ── Accurate split ────────────────────────────────────
        inserted = after_count - before_count
        updated  = len(records) - inserted

    except Exception as e:
        log.error(f"    ⚠️  BDM batch upsert failed: {e}")
        errors = len(records)

    log.info(
        f"    BDM → Sent={len(records)} | "
        f"Inserted={inserted} (new rows) | "
        f"Updated={updated} (existing rows) | "
        f"Errors={errors}"
    )
    return inserted, updated, errors