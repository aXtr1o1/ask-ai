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

def upsert_location(cursor, records: list, user_id: int, user_name: str):
    inserted = updated = errors = 0
    try:
        seen = {}
        for r in records:
            key = r.get("LocalityIDPK")
            if key is not None:
                seen[key] = r
        records = list(seen.values())

        cursor.execute(
            'SELECT COUNT(*) FROM public.location WHERE user_name = %s',
            (user_name,)
        )
        before_count = cursor.fetchone()[0]
        log.info(f"    [Location] Records in DB before upsert: {before_count}")

        rows = [
            (
                user_id, user_name,
                r.get("LocalityIDPK"), r.get("LocalityCode"), r.get("LocalityName"),
                r.get("LocAddress1"), r.get("LocAddress2"), r.get("LocAddress3"),
                r.get("LocalityLatitude"), r.get("LocalityLongitude"), r.get("FieldRadius"),
                r.get("IsPortalDisplay", False), r.get("IsNonContract"), r.get("IsDefault"),
                r.get("IsDraft", False), r.get("Remarks"), r.get("LocalityGroupID"),
                r.get("CityID"), r.get("AdminLocalityTypeID"), r.get("IsActive", True),
                r.get("DeleStat", False), r.get("CreatedUserID"), parse_date(r.get("CreatedTtm")),
                parse_date(r.get("UpdatedTtm")), r.get("LocalityGroupCode"), r.get("LocalityGroupName"),
                r.get("CityCode"), r.get("CityName"), r.get("AdminLocalityTypeCode"),
                r.get("AdminLocalityTypeName")
            )
            for r in records
        ]

        psycopg2.extras.execute_values(cursor, """
            INSERT INTO public.location (
                user_id, user_name, " LocalityIDPK", "LocalityCode", "LocalityName",
                "LocAddress1", "LocAddress2", "LocAddress3", "LocalityLatitude",
                "LocalityLongitude", "FieldRadius", "IsPortalDisplay", "IsNonContract",
                "IsDefault", "IsDraft", "Remarks", "LocalityGroupID", "CityID",
                "AdminLocalityTypeID", "IsActive", "DeleStat", "CreatedUserID",
                "CreatedTtm", "UpdatedTtm", "LocalityGroupCode", "LocalityGroupName",
                "CityCode", "CityName", "AdminLocalityTypeCode", "AdminLocalityTypeName"
            ) VALUES %s
            ON CONFLICT (" LocalityIDPK") DO UPDATE SET
                user_id = EXCLUDED.user_id,
                user_name = EXCLUDED.user_name,
                "LocalityCode" = EXCLUDED."LocalityCode",
                "LocalityName" = EXCLUDED."LocalityName",
                "LocAddress1" = EXCLUDED."LocAddress1",
                "LocAddress2" = EXCLUDED."LocAddress2",
                "LocAddress3" = EXCLUDED."LocAddress3",
                "LocalityLatitude" = EXCLUDED."LocalityLatitude",
                "LocalityLongitude" = EXCLUDED."LocalityLongitude",
                "FieldRadius" = EXCLUDED."FieldRadius",
                "IsPortalDisplay" = EXCLUDED."IsPortalDisplay",
                "IsNonContract" = EXCLUDED."IsNonContract",
                "IsDefault" = EXCLUDED."IsDefault",
                "IsDraft" = EXCLUDED."IsDraft",
                "Remarks" = EXCLUDED."Remarks",
                "LocalityGroupID" = EXCLUDED."LocalityGroupID",
                "CityID" = EXCLUDED."CityID",
                "AdminLocalityTypeID" = EXCLUDED."AdminLocalityTypeID",
                "IsActive" = EXCLUDED."IsActive",
                "DeleStat" = EXCLUDED."DeleStat",
                "CreatedUserID" = EXCLUDED."CreatedUserID",
                "CreatedTtm" = EXCLUDED."CreatedTtm",
                "UpdatedTtm" = EXCLUDED."UpdatedTtm",
                "LocalityGroupCode" = EXCLUDED."LocalityGroupCode",
                "LocalityGroupName" = EXCLUDED."LocalityGroupName",
                "CityCode" = EXCLUDED."CityCode",
                "CityName" = EXCLUDED."CityName",
                "AdminLocalityTypeCode" = EXCLUDED."AdminLocalityTypeCode",
                "AdminLocalityTypeName" = EXCLUDED."AdminLocalityTypeName"
        """, rows, page_size=1000)

        cursor.execute(
            'SELECT COUNT(*) FROM public.location WHERE user_name = %s',
            (user_name,)
        )
        after_count = cursor.fetchone()[0]
        log.info(f"    [Location] Records in DB after upsert: {after_count}")

        inserted = max(0, after_count - before_count)
        updated = len(records) - inserted
        return inserted, updated, 0

    except Exception as e:
        log.error(f"    [Location] Upsert error: {e}")
        return 0, 0, len(records)
