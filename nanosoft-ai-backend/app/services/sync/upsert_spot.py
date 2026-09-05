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

def upsert_spot(cursor, records: list, user_id: int, user_name: str):
    inserted = updated = errors = 0
    try:
        seen = {}
        for r in records:
            key = r.get("SpotIDPK")
            if key is not None:
                seen[key] = r
        records = list(seen.values())

        cursor.execute(
            'SELECT COUNT(*) FROM public.spot WHERE user_name = %s',
            (user_name,)
        )
        before_count = cursor.fetchone()[0]
        log.info(f"    [Spot] Records in DB before upsert: {before_count}")

        rows = [
            (
                user_id, user_name,
                r.get("SpotIDPK"), r.get("SpotCode"), r.get("SpotName"), r.get("SpotNo"),
                r.get("SpotLatitude"), r.get("SpotLongitude"), r.get("SpotArea"),
                r.get("IsOccupany"), r.get("IsNonContract"), r.get("IsParking"),
                r.get("IsAllocated"), r.get("SpotRadius"), r.get("SpotRefNo"),
                r.get("IsDefault"), r.get("IsDraft", False), r.get("Remarks"), r.get("SpotTypeID"),
                r.get("LocalityID"), r.get("BuildingID"), r.get("FloorID"), r.get("AssWingID"),
                r.get("EmpGradeID"), r.get("IsActive", True), r.get("DeleStat", False),
                r.get("CreatedUserID"), parse_date(r.get("CreatedTtm")), parse_date(r.get("UpdatedTtm")),
                r.get("SpotTypeCode"), r.get("SpotTypeName"), r.get("LocalityCode"), r.get("LocalityName"),
                r.get("BuildingCode"), r.get("BuildingName"), r.get("FloorCode"), r.get("FloorName"),
                r.get("AssWingCode"), r.get("AssWingName")
            )
            for r in records
        ]

        psycopg2.extras.execute_values(cursor, """
            INSERT INTO public.spot (
                user_id, user_name, "SpotIDPK", "SpotCode", "SpotName", "SpotNo",
                "SpotLatitude", "SpotLongitude", "SpotArea", "IsOccupany", "IsNonContract",
                "IsParking", "IsAllocated", "SpotRadius", "SpotRefNo", "IsDefault", "IsDraft",
                "Remarks", "SpotTypeID", "LocalityID", "BuildingID", "FloorID", "AssWingID",
                "EmpGradeID", "IsActive", "DeleStat", "CreatedUserID", "CreatedTtm", "UpdatedTtm",
                "SpotTypeCode", "SpotTypeName", "LocalityCode", "LocalityName", "BuildingCode",
                "BuildingName", "FloorCode", "FloorName", "AssWingCode", "AssWingName"
            ) VALUES %s
            ON CONFLICT ("SpotIDPK") DO UPDATE SET
                user_id = EXCLUDED.user_id,
                user_name = EXCLUDED.user_name,
                "SpotCode" = EXCLUDED."SpotCode",
                "SpotName" = EXCLUDED."SpotName",
                "SpotNo" = EXCLUDED."SpotNo",
                "SpotLatitude" = EXCLUDED."SpotLatitude",
                "SpotLongitude" = EXCLUDED."SpotLongitude",
                "SpotArea" = EXCLUDED."SpotArea",
                "IsOccupany" = EXCLUDED."IsOccupany",
                "IsNonContract" = EXCLUDED."IsNonContract",
                "IsParking" = EXCLUDED."IsParking",
                "IsAllocated" = EXCLUDED."IsAllocated",
                "SpotRadius" = EXCLUDED."SpotRadius",
                "SpotRefNo" = EXCLUDED."SpotRefNo",
                "IsDefault" = EXCLUDED."IsDefault",
                "IsDraft" = EXCLUDED."IsDraft",
                "Remarks" = EXCLUDED."Remarks",
                "SpotTypeID" = EXCLUDED."SpotTypeID",
                "LocalityID" = EXCLUDED."LocalityID",
                "BuildingID" = EXCLUDED."BuildingID",
                "FloorID" = EXCLUDED."FloorID",
                "AssWingID" = EXCLUDED."AssWingID",
                "EmpGradeID" = EXCLUDED."EmpGradeID",
                "IsActive" = EXCLUDED."IsActive",
                "DeleStat" = EXCLUDED."DeleStat",
                "CreatedUserID" = EXCLUDED."CreatedUserID",
                "CreatedTtm" = EXCLUDED."CreatedTtm",
                "UpdatedTtm" = EXCLUDED."UpdatedTtm",
                "SpotTypeCode" = EXCLUDED."SpotTypeCode",
                "SpotTypeName" = EXCLUDED."SpotTypeName",
                "LocalityCode" = EXCLUDED."LocalityCode",
                "LocalityName" = EXCLUDED."LocalityName",
                "BuildingCode" = EXCLUDED."BuildingCode",
                "BuildingName" = EXCLUDED."BuildingName",
                "FloorCode" = EXCLUDED."FloorCode",
                "FloorName" = EXCLUDED."FloorName",
                "AssWingCode" = EXCLUDED."AssWingCode",
                "AssWingName" = EXCLUDED."AssWingName"
        """, rows, page_size=1000)

        cursor.execute(
            'SELECT COUNT(*) FROM public.spot WHERE user_name = %s',
            (user_name,)
        )
        after_count = cursor.fetchone()[0]
        log.info(f"    [Spot] Records in DB after upsert: {after_count}")

        inserted = max(0, after_count - before_count)
        updated = len(records) - inserted
        return inserted, updated, 0

    except Exception as e:
        log.error(f"    [Spot] Upsert error: {e}")
        return 0, 0, len(records)
