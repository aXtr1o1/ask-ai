import psycopg2.extras
import re
from .config import log

def parse_date(d):
    if not d: return None
    d = str(d).strip()
    m = re.match(r'(\d{2})-(\d{2})-(\d{4})(.*)', d)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}{m.group(4)}"
    return d

def upsert_building(cursor, records: list, user_id: int, user_name: str):
    inserted = updated = errors = 0
    try:
        # Deduplicate by "BuildingIDPK"
        seen = {}
        for r in records:
            key = r.get("BuildingIDPK")
            if key is not None:
                seen[key] = r
        records = list(seen.values())

        cursor.execute(
            'SELECT COUNT(*) FROM public.building WHERE user_name = %s',
            (user_name,)
        )
        before_count = cursor.fetchone()[0]
        log.info(f"    [Building] Records in DB before upsert: {before_count}")

        rows = [
            (
                user_id, user_name,
                r.get("BuildingIDPK"), r.get("BuildingCode"), r.get("BuildingName"), r.get("BuildingNo"),
                r.get("BuildingLatitude"), r.get("BulidingLongitude"), r.get("PermitNo"), r.get("MakaniNo"),
                r.get("BUPArea"), r.get("LeaseableArea"), r.get("FieldRadius"), r.get("BuildingArea"),
                r.get("NoOfFloors"), r.get("NoOfSpots"), r.get("NoOfUnits"), r.get("NoOfParkings"),
                r.get("BuiPlotNo"), r.get("IsNonContract"), r.get("IsDraft", False), r.get("IsDefault"),
                r.get("Remarks"), r.get("LocalityID"), r.get("AssBuildingTypeID"), r.get("FinLedgerID"),
                r.get("EmployeeID"), r.get("EmployeeID1"), r.get("IsActive", True), r.get("DeleStat", False),
                r.get("CreatedUserID"), parse_date(r.get("CreatedTtm")), parse_date(r.get("UpdatedTtm")), r.get("LocalityCode"),
                r.get("LocalityName"), r.get("AssBuildingTypeCode"), r.get("AssBuildingTypeName"),
                r.get("LedgerCode"), r.get("LedgerName"), r.get("EmployeeCode"), r.get("FirstName"),
                r.get("EmpContactNo1"), r.get("EmpEmailOfficial"), r.get("LastName"), r.get("EmployeeCode1"),
                r.get("FirstName1"), r.get("EmpContactNo11"), r.get("EmpEmailOfficial1"), r.get("LastName1")
            )
            for r in records
        ]

        psycopg2.extras.execute_values(cursor, """
            INSERT INTO public.building (
                user_id, user_name, "BuildingIDPK", "BuildingCode", "BuildingName", "BuildingNo",
                "BuildingLatitude", "BulidingLongitude", "PermitNo", "MakaniNo", "BUPArea", "LeaseableArea",
                "FieldRadius", "BuildingArea", "NoOfFloors", "NoOfSpots", "NoOfUnits", "NoOfParkings",
                "BuiPlotNo", "IsNonContract", "IsDraft", "IsDefault", "Remarks", "LocalityID",
                "AssBuildingTypeID", "FinLedgerID", "EmployeeID", "EmployeeID1", "IsActive", "DeleStat",
                "CreatedUserID", "CreatedTtm", "UpdatedTtm", "LocalityCode", "LocalityName",
                "AssBuildingTypeCode", "AssBuildingTypeName", "LedgerCode", "LedgerName",
                "EmployeeCode", "FirstName", "EmpContactNo1", "EmpEmailOfficial", "LastName",
                "EmployeeCode1", "FirstName1", "EmpContactNo11", "EmpEmailOfficial1", "LastName1"
            ) VALUES %s
            ON CONFLICT ("BuildingIDPK") DO UPDATE SET
                user_id = EXCLUDED.user_id,
                user_name = EXCLUDED.user_name,
                "BuildingCode" = EXCLUDED."BuildingCode",
                "BuildingName" = EXCLUDED."BuildingName",
                "BuildingNo" = EXCLUDED."BuildingNo",
                "BuildingLatitude" = EXCLUDED."BuildingLatitude",
                "BulidingLongitude" = EXCLUDED."BulidingLongitude",
                "PermitNo" = EXCLUDED."PermitNo",
                "MakaniNo" = EXCLUDED."MakaniNo",
                "BUPArea" = EXCLUDED."BUPArea",
                "LeaseableArea" = EXCLUDED."LeaseableArea",
                "FieldRadius" = EXCLUDED."FieldRadius",
                "BuildingArea" = EXCLUDED."BuildingArea",
                "NoOfFloors" = EXCLUDED."NoOfFloors",
                "NoOfSpots" = EXCLUDED."NoOfSpots",
                "NoOfUnits" = EXCLUDED."NoOfUnits",
                "NoOfParkings" = EXCLUDED."NoOfParkings",
                "BuiPlotNo" = EXCLUDED."BuiPlotNo",
                "IsNonContract" = EXCLUDED."IsNonContract",
                "IsDraft" = EXCLUDED."IsDraft",
                "IsDefault" = EXCLUDED."IsDefault",
                "Remarks" = EXCLUDED."Remarks",
                "LocalityID" = EXCLUDED."LocalityID",
                "AssBuildingTypeID" = EXCLUDED."AssBuildingTypeID",
                "FinLedgerID" = EXCLUDED."FinLedgerID",
                "EmployeeID" = EXCLUDED."EmployeeID",
                "EmployeeID1" = EXCLUDED."EmployeeID1",
                "IsActive" = EXCLUDED."IsActive",
                "DeleStat" = EXCLUDED."DeleStat",
                "CreatedUserID" = EXCLUDED."CreatedUserID",
                "CreatedTtm" = EXCLUDED."CreatedTtm",
                "UpdatedTtm" = EXCLUDED."UpdatedTtm",
                "LocalityCode" = EXCLUDED."LocalityCode",
                "LocalityName" = EXCLUDED."LocalityName",
                "AssBuildingTypeCode" = EXCLUDED."AssBuildingTypeCode",
                "AssBuildingTypeName" = EXCLUDED."AssBuildingTypeName",
                "LedgerCode" = EXCLUDED."LedgerCode",
                "LedgerName" = EXCLUDED."LedgerName",
                "EmployeeCode" = EXCLUDED."EmployeeCode",
                "FirstName" = EXCLUDED."FirstName",
                "EmpContactNo1" = EXCLUDED."EmpContactNo1",
                "EmpEmailOfficial" = EXCLUDED."EmpEmailOfficial",
                "LastName" = EXCLUDED."LastName",
                "EmployeeCode1" = EXCLUDED."EmployeeCode1",
                "FirstName1" = EXCLUDED."FirstName1",
                "EmpContactNo11" = EXCLUDED."EmpContactNo11",
                "EmpEmailOfficial1" = EXCLUDED."EmpEmailOfficial1",
                "LastName1" = EXCLUDED."LastName1"
        """, rows, page_size=1000)

        cursor.execute(
            'SELECT COUNT(*) FROM public.building WHERE user_name = %s',
            (user_name,)
        )
        after_count = cursor.fetchone()[0]
        log.info(f"    [Building] Records in DB after upsert: {after_count}")

        inserted = max(0, after_count - before_count)
        updated = len(records) - inserted
        return inserted, updated, 0

    except Exception as e:
        log.error(f"    [Building] Upsert error: {e}")
        return 0, 0, len(records)
