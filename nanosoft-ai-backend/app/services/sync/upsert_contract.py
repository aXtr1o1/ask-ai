import psycopg2.extras
from datetime import datetime
from .config import log


# ─────────────────────────────────────────────────────────────
# DATE PARSER — handles DD-MM-YYYY, YYYY-MM-DD, DD/MM/YYYY, etc.
# Returns a Python date object or None if unparseable
# ─────────────────────────────────────────────────────────────
_DATE_FORMATS = [
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%m-%d-%Y",
    "%m/%d/%Y",
    "%d-%m-%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
]

def _parse_date(value):
    """Parse a date string from the API. Returns a date object or None."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None  # unparseable — store NULL instead of crashing


# ─────────────────────────────────────────────────────────────
# UPSERT — Contract Master
# Primary key: ContractIDPK
# Uses COUNT before/after to accurately split insert vs update
# ─────────────────────────────────────────────────────────────
def upsert_contract(cursor, records: list, user_id: int, user_name: str):
    inserted = updated = errors = 0
    try:
        # ── Deduplicate by ContractIDPK — keep last occurrence ─
        seen = {}
        for r in records:
            key = r.get("ContractIDPK")
            if key is not None:
                seen[key] = r
        records = list(seen.values())

        if not records:
            log.info("    [Contract] No records to upsert after dedup.")
            return 0, 0, 0

        # ── COUNT before upsert ───────────────────────────────
        cursor.execute(
            "SELECT COUNT(*) FROM public.contract_master WHERE user_name = %s",
            (user_name,)
        )
        before_count = cursor.fetchone()[0]
        log.info(f"    [Contract] Records in DB before upsert: {before_count}")

        rows = [
            (
                user_id, user_name,
                r.get("ContractIDPK"),
                r.get("ContractCode"),
                r.get("ContractName"),
                _parse_date(r.get("ContractDate")),
                r.get("ContractValue"),
                r.get("ExtendedValue"),
                r.get("TotalContractValue"),
                r.get("ConValueBeforVat"),
                r.get("VatAmount"),
                r.get("TaxName"),
                _parse_date(r.get("StartDate")),
                _parse_date(r.get("EndDate")),
                _parse_date(r.get("AnnualReviewDate")),
                _parse_date(r.get("ExtendedDate")),
                r.get("CustomerName"),
                r.get("IsNonContract") or False,
                r.get("ContractTypeName"),
                r.get("ContractCategName"),
                r.get("ContractGroupName"),
                r.get("OrganisationName"),
                r.get("ContStStatus"),
                r.get("ContStTypes"),
                r.get("IsActive") or False,
                r.get("IsDraft") or False,
                r.get("IsRenewal") or False,
                r.get("IsExtended") or False,
                r.get("IsTerminate") or False,
                r.get("IsPPM") or False,
                r.get("IsBDM") or False,
                r.get("IsDSM") or False,
                r.get("IsIncident") or False,
                r.get("IsCase") or False,
                r.get("NoOfBilling"),
                r.get("NoofInvoice"),
                r.get("Period"),
                r.get("ConPaymentTermsName"),
                r.get("NoofEngineer"),
                r.get("NoofSupervisor"),
                r.get("NoofPrimary"),
                r.get("ShiftNoofPrimary"),
                r.get("ShiftNoofSecondary"),
            )
            for r in records
        ]

        psycopg2.extras.execute_values(cursor, """
            INSERT INTO public.contract_master (
                user_id, user_name,
                "ContractIDPK", "ContractCode", "ContractName", "ContractDate",
                "ContractValue", "ExtendedValue", "TotalContractValue",
                "ConValueBeforVat", "VatAmount", "TaxName",
                "StartDate", "EndDate", "AnnualReviewDate", "ExtendedDate",
                "CustomerName", "IsNonContract",
                "ContractTypeName", "ContractCategName", "ContractGroupName",
                "OrganisationName",
                "ContStStatus", "ContStTypes",
                "IsActive", "IsDraft", "IsRenewal", "IsExtended", "IsTerminate",
                "IsPPM", "IsBDM", "IsDSM", "IsIncident", "IsCase",
                "NoOfBilling", "NoofInvoice", "Period", "ConPaymentTermsName",
                "NoofEngineer", "NoofSupervisor", "NoofPrimary",
                "ShiftNoofPrimary", "ShiftNoofSecondary"
            ) VALUES %s
            ON CONFLICT ("ContractIDPK") DO UPDATE SET
                user_id                = EXCLUDED.user_id,
                user_name              = EXCLUDED.user_name,
                "ContractCode"         = EXCLUDED."ContractCode",
                "ContractName"         = EXCLUDED."ContractName",
                "ContractDate"         = EXCLUDED."ContractDate",
                "ContractValue"        = EXCLUDED."ContractValue",
                "ExtendedValue"        = EXCLUDED."ExtendedValue",
                "TotalContractValue"   = EXCLUDED."TotalContractValue",
                "ConValueBeforVat"     = EXCLUDED."ConValueBeforVat",
                "VatAmount"            = EXCLUDED."VatAmount",
                "TaxName"              = EXCLUDED."TaxName",
                "StartDate"            = EXCLUDED."StartDate",
                "EndDate"              = EXCLUDED."EndDate",
                "AnnualReviewDate"     = EXCLUDED."AnnualReviewDate",
                "ExtendedDate"         = EXCLUDED."ExtendedDate",
                "CustomerName"         = EXCLUDED."CustomerName",
                "IsNonContract"        = EXCLUDED."IsNonContract",
                "ContractTypeName"     = EXCLUDED."ContractTypeName",
                "ContractCategName"    = EXCLUDED."ContractCategName",
                "ContractGroupName"    = EXCLUDED."ContractGroupName",
                "OrganisationName"     = EXCLUDED."OrganisationName",
                "ContStStatus"         = EXCLUDED."ContStStatus",
                "ContStTypes"          = EXCLUDED."ContStTypes",
                "IsActive"             = EXCLUDED."IsActive",
                "IsDraft"              = EXCLUDED."IsDraft",
                "IsRenewal"            = EXCLUDED."IsRenewal",
                "IsExtended"           = EXCLUDED."IsExtended",
                "IsTerminate"          = EXCLUDED."IsTerminate",
                "IsPPM"                = EXCLUDED."IsPPM",
                "IsBDM"                = EXCLUDED."IsBDM",
                "IsDSM"                = EXCLUDED."IsDSM",
                "IsIncident"           = EXCLUDED."IsIncident",
                "IsCase"               = EXCLUDED."IsCase",
                "NoOfBilling"          = EXCLUDED."NoOfBilling",
                "NoofInvoice"          = EXCLUDED."NoofInvoice",
                "Period"               = EXCLUDED."Period",
                "ConPaymentTermsName"  = EXCLUDED."ConPaymentTermsName",
                "NoofEngineer"         = EXCLUDED."NoofEngineer",
                "NoofSupervisor"       = EXCLUDED."NoofSupervisor",
                "NoofPrimary"          = EXCLUDED."NoofPrimary",
                "ShiftNoofPrimary"     = EXCLUDED."ShiftNoofPrimary",
                "ShiftNoofSecondary"   = EXCLUDED."ShiftNoofSecondary",
                updated_at             = NOW()
        """, rows, page_size=1000)

        # ── COUNT after upsert ────────────────────────────────
        cursor.execute(
            "SELECT COUNT(*) FROM public.contract_master WHERE user_name = %s",
            (user_name,)
        )
        after_count = cursor.fetchone()[0]
        log.info(f"    [Contract] Records in DB after upsert: {after_count}")

        # ── Accurate split ────────────────────────────────────
        inserted = after_count - before_count
        updated  = len(records) - inserted

    except Exception as e:
        log.error(f"    ⚠️  Contract batch upsert failed: {e}")
        errors = len(records)

    log.info(
        f"    Contract → Sent={len(records)} | "
        f"Inserted={inserted} (new rows) | "
        f"Updated={updated} (existing rows) | "
        f"Errors={errors}"
    )
    return inserted, updated, errors
