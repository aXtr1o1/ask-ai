import psycopg2.extras
from .config import log

# UPSERT — assets
# BATCH insert using execute_values → 1000 records in ONE SQL call
# No memory spike — records freed immediately after insert

def upsert_assets(cursor, records: list, user_id: int, user_name: str):
    inserted = updated = errors = 0
    try:
        # deduplicate by AssetTagNo — keep last occurrence
        seen = {}
        for r in records:
            key = r.get("AssetTagNo") or ""
            seen[key] = r
        records = list(seen.values())

        rows = [
            (
                user_id, user_name,
                r.get("AssetTagNo") or "",        r.get("AssetBarcode") or "",
                r.get("EquipmentName") or "",     r.get("EquipmentRefNo"),
                r.get("SerialNo"),                r.get("StatusName") or "",
                r.get("ConditionName") or "",     r.get("PriorityName") or "",
                r.get("OnHold") or False,         r.get("IsSnagged") or False,
                r.get("IsScraped") or False,      r.get("LocalityName") or "",
                r.get("BuildingName") or "",      r.get("FloorName") or "",
                r.get("SpotName") or "",          r.get("Longitude"),
                r.get("Latitude"),                r.get("AssetTypeName") or "",
                r.get("DivisionName") or "",      r.get("DisciplineName") or "",
                r.get("Owner") or "",             r.get("IsEnablePPM") or False,
                r.get("IsEnableBDM") or False,    r.get("IsEnableBMS") or False,
                r.get("IsEnableDSM") or False,    r.get("MakeName"),
                r.get("ModelName"),               r.get("YearOfManuf") or 0,
                r.get("LifeInYear"),              r.get("PurDate"),
                r.get("PurValue"),                r.get("InstalledDate"),
                r.get("ScrapDate"),               r.get("ScrapValue"),
                r.get("ServiceAreaName"),         r.get("TradeGroupName"),
                r.get("DrawingNo"),               r.get("Remarks"),
            )
            for r in records
        ]

        psycopg2.extras.execute_values(cursor, """
            INSERT INTO "Asset" (
                user_id, user_name,
                "AssetTagNo", "AssetBarcode", "EquipmentName", "EquipmentRefNo",
                "SerialNo", "StatusName", "ConditionName", "PriorityName",
                "OnHold", "IsSnagged", "IsScraped",
                "LocalityName", "BuildingName", "FloorName", "SpotName",
                "Longitude", "Latitude", "AssetTypeName",
                "DivisionName", "DisciplineName", "Owner",
                "IsEnablePPM", "IsEnableBDM", "IsEnableBMS", "IsEnableDSM",
                "MakeName", "ModelName", "YearOfManuf", "LifeInYear",
                "PurDate", "PurValue", "InstalledDate", "ScrapDate", "ScrapValue",
                "ServiceAreaName", "TradeGroupName", "DrawingNo", "Remarks"
            ) VALUES %s
            ON CONFLICT ("AssetTagNo") DO UPDATE SET
                user_name       = EXCLUDED.user_name,
                "StatusName"    = EXCLUDED."StatusName",
                "ConditionName" = EXCLUDED."ConditionName",
                "PriorityName"  = EXCLUDED."PriorityName",
                "OnHold"        = EXCLUDED."OnHold",
                "IsSnagged"     = EXCLUDED."IsSnagged",
                "IsScraped"     = EXCLUDED."IsScraped",
                "FloorName"     = EXCLUDED."FloorName",
                "SpotName"      = EXCLUDED."SpotName",
                "IsEnablePPM"   = EXCLUDED."IsEnablePPM",
                "IsEnableBDM"   = EXCLUDED."IsEnableBDM",
                "IsEnableBMS"   = EXCLUDED."IsEnableBMS",
                "IsEnableDSM"   = EXCLUDED."IsEnableDSM",
                "Remarks"       = EXCLUDED."Remarks",
                updated_at      = NOW()
        """, rows, page_size=1000)

        inserted = len(records)

    except Exception as e:
        log.error(f"    ⚠️  Asset batch upsert failed: {e}")
        errors = len(records)

    log.info(f"    Assets → Upserted: {inserted} | Errors: {errors}")
    return inserted, updated, errors
