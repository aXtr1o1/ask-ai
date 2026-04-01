import psycopg2.extras
from .config import log
def upsert_bdm(cursor, records: list, user_id: int, user_name: str):
    inserted = updated = errors = 0
    try:
        seen = {}
        for r in records:
            key = r.get("ComplaintNo") or ""
            seen[key] = r
        records = list(seen.values())

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
            INSERT INTO bdm (
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
            ON CONFLICT (user_id, "ComplaintNo") DO UPDATE SET
                user_id         = EXCLUDED.user_id,
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

        inserted = len(records)

    except Exception as e:
        log.error(f"    ⚠️  BDM batch upsert failed: {e}")
        errors = len(records)

    log.info(f"    BDM → Upserted: {inserted} | Errors: {errors}")
    return inserted, updated, errors
