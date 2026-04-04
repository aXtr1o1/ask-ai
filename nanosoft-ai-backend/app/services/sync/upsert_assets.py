import psycopg2.extras
from .config import log


# ─────────────────────────────────────────────────────────────
# UPSERT — Assets
# Uses COUNT before/after to accurately split insert vs update
# ─────────────────────────────────────────────────────────────
def upsert_assets(cursor, records: list, user_id: int, user_name: str):
    inserted = updated = errors = 0
    try:
        # ── Deduplicate by AssetTagNo — keep last occurrence ──
        seen = {}
        for r in records:
            key = r.get("AssetTagNo") or ""
            seen[key] = r
        records = list(seen.values())

        # ── COUNT before upsert ───────────────────────────────
        cursor.execute(
            'SELECT COUNT(*) FROM public."Asset" WHERE user_name = %s',
            (user_name,)
        )
        before_count = cursor.fetchone()[0]
        log.info(f"    [Assets] Records in DB before upsert: {before_count}")

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
            INSERT INTO public."Asset" (
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
                user_id         = EXCLUDED.user_id,
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

        # ── COUNT after upsert ────────────────────────────────
        cursor.execute(
            'SELECT COUNT(*) FROM public."Asset" WHERE user_name = %s',
            (user_name,)
        )
        after_count = cursor.fetchone()[0]
        log.info(f"    [Assets] Records in DB after upsert: {after_count}")

        # ── Accurate split ────────────────────────────────────
        inserted = after_count - before_count
        updated  = len(records) - inserted

    except Exception as e:
        log.error(f"    ⚠️  Asset batch upsert failed: {e}")
        errors = len(records)

    log.info(
        f"    Assets → Sent={len(records)} | "
        f"Inserted={inserted} (new rows) | "
        f"Updated={updated} (existing rows) | "
        f"Errors={errors}"
    )
    return inserted, updated, errors