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

def upsert_floor(cursor, records: list, user_id: int, user_name: str):
    inserted = updated = errors = 0
    try:
        seen = {}
        for r in records:
            key = r.get("FloorIDPK")
            if key is not None:
                seen[key] = r
        records = list(seen.values())

        cursor.execute(
            'SELECT COUNT(*) FROM public.floor WHERE user_name = %s',
            (user_name,)
        )
        before_count = cursor.fetchone()[0]
        log.info(f"    [Floor] Records in DB before upsert: {before_count}")

        rows = [
            (
                user_id, user_name,
                r.get("FloorIDPK"), r.get("FloorCode"), r.get("FloorName"),
                r.get("IsNonContract"), r.get("FloorArea"), r.get("FloorLatitude"), r.get("FloorLongitude"),
                r.get("IsDefault"), r.get("IsDraft", False), r.get("Remarks"), r.get("LocalityID"),
                r.get("BuildingID"), r.get("IsActive", True), r.get("DeleStat", False),
                r.get("CreatedUserID"), parse_date(r.get("CreatedTtm")), parse_date(r.get("UpdatedTtm")),
                r.get("LocalityCode"), r.get("LocalityName"), r.get("BuildingCode"), r.get("BuildingName")
            )
            for r in records
        ]

        psycopg2.extras.execute_values(cursor, """
            INSERT INTO public.floor (
                user_id, user_name, "FloorIDPK", "FloorCode", "FloorName",
                "IsNonContract", "FloorArea", "FloorLatitude", "FloorLongitude",
                "IsDefault", "IsDraft", "Remarks", "LocalityID", "BuildingID",
                "IsActive", "DeleStat", "CreatedUserID", "CreatedTtm", "UpdatedTtm",
                "LocalityCode", "LocalityName", "BuildingCode", "BuildingName"
            ) VALUES %s
            ON CONFLICT ("FloorIDPK") DO UPDATE SET
                user_id = EXCLUDED.user_id,
                user_name = EXCLUDED.user_name,
                "FloorCode" = EXCLUDED."FloorCode",
                "FloorName" = EXCLUDED."FloorName",
                "IsNonContract" = EXCLUDED."IsNonContract",
                "FloorArea" = EXCLUDED."FloorArea",
                "FloorLatitude" = EXCLUDED."FloorLatitude",
                "FloorLongitude" = EXCLUDED."FloorLongitude",
                "IsDefault" = EXCLUDED."IsDefault",
                "IsDraft" = EXCLUDED."IsDraft",
                "Remarks" = EXCLUDED."Remarks",
                "LocalityID" = EXCLUDED."LocalityID",
                "BuildingID" = EXCLUDED."BuildingID",
                "IsActive" = EXCLUDED."IsActive",
                "DeleStat" = EXCLUDED."DeleStat",
                "CreatedUserID" = EXCLUDED."CreatedUserID",
                "CreatedTtm" = EXCLUDED."CreatedTtm",
                "UpdatedTtm" = EXCLUDED."UpdatedTtm",
                "LocalityCode" = EXCLUDED."LocalityCode",
                "LocalityName" = EXCLUDED."LocalityName",
                "BuildingCode" = EXCLUDED."BuildingCode",
                "BuildingName" = EXCLUDED."BuildingName"
        """, rows, page_size=1000)

        cursor.execute(
            'SELECT COUNT(*) FROM public.floor WHERE user_name = %s',
            (user_name,)
        )
        after_count = cursor.fetchone()[0]
        log.info(f"    [Floor] Records in DB after upsert: {after_count}")

        inserted = max(0, after_count - before_count)
        updated = len(records) - inserted
        return inserted, updated, 0

    except Exception as e:
        log.error(f"    [Floor] Upsert error: {e}")
        return 0, 0, len(records)
