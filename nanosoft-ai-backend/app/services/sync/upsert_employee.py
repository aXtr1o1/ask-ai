import psycopg2.extras
from datetime import datetime
from .config import log


# ─────────────────────────────────────────────────────────────
# DATE / DATETIME PARSERS — API sends DD-MM-YYYY or DD-MM-YYYY HH:MM:SS
# Returns a Python date/datetime object or None if unparseable
# ─────────────────────────────────────────────────────────────
_DATE_FORMATS = [
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%m-%d-%Y",
    "%m/%d/%Y",
]

_DATETIME_FORMATS = [
    "%d-%m-%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%d-%m-%Y",
    "%Y-%m-%d",
]

def _parse_date(value):
    """Parse a date string. Returns a date object or None."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None

def _parse_datetime(value):
    """Parse a datetime string. Returns a datetime object or None."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


# ─────────────────────────────────────────────────────────────
# UPSERT — Employee Master
# Primary key: EmployeeIDPK
# Uses COUNT before/after to accurately split insert vs update
# ─────────────────────────────────────────────────────────────
def upsert_employee(cursor, records: list, user_id: int, user_name: str):
    inserted = updated = errors = 0
    try:
        # ── Deduplicate by EmployeeIDPK — keep last occurrence ─
        seen = {}
        for r in records:
            key = r.get("EmployeeIDPK")
            if key is not None:
                seen[key] = r
        records = list(seen.values())

        if not records:
            log.info("    [Employee] No records to upsert after dedup.")
            return 0, 0, 0

        # ── COUNT before upsert ───────────────────────────────
        cursor.execute(
            "SELECT COUNT(*) FROM public.employee_master WHERE user_name = %s",
            (user_name,)
        )
        before_count = cursor.fetchone()[0]
        log.info(f"    [Employee] Records in DB before upsert: {before_count}")

        rows = [
            (
                user_id, user_name,
                r.get("EmployeeIDPK"),
                r.get("EmployeeCode"),
                r.get("EmployeeFullName"),
                r.get("FirstName"),
                r.get("LastName"),
                _parse_date(r.get("EmpDateofBirth")),
                r.get("EmpGenderName"),
                r.get("MaritalStatus"),
                r.get("NationalityName"),
                r.get("CountryName"),
                _parse_date(r.get("EmpDateOfJoin")),
                r.get("ProbationPeriod"),
                _parse_date(r.get("DateofConfirmation")),
                _parse_date(r.get("LeftJobOnDate")),
                _parse_datetime(r.get("CreatedTtm")),
                r.get("OrganisationName"),
                r.get("DepartmentName"),
                r.get("DesignationName"),
                r.get("ClassificationName"),
                r.get("Branch"),
                r.get("NatureOfWorkName"),
                r.get("EmployeeTypeName"),
                r.get("EmploymentTypeName"),
                r.get("ShiftName"),
                r.get("ShiftCode"),
                r.get("IsAttendanceEnable") or False,
                r.get("IsSinglePunch") or False,
                r.get("WorkHours"),
                r.get("WrkPerDay"),
                r.get("IsActive") or False,
                r.get("Remarks"),
                r.get("EmployeeGroupName"),
                r.get("EmpGradeName"),
                r.get("EmpTitleName"),
                r.get("Color"),
                r.get("VehicleNo"),
            )
            for r in records
        ]

        psycopg2.extras.execute_values(cursor, """
            INSERT INTO public.employee_master (
                user_id, user_name,
                "EmployeeIDPK", "EmployeeCode", "EmployeeFullName",
                "FirstName", "LastName",
                "EmpDateofBirth", "EmpGenderName", "MaritalStatus",
                "NationalityName", "CountryName",
                "EmpDateOfJoin", "ProbationPeriod", "DateofConfirmation", "LeftJobOnDate",
                "CreatedTtm",
                "OrganisationName", "DepartmentName", "DesignationName",
                "ClassificationName", "Branch",
                "NatureOfWorkName", "EmployeeTypeName", "EmploymentTypeName",
                "ShiftName", "ShiftCode",
                "IsAttendanceEnable", "IsSinglePunch",
                "WorkHours", "WrkPerDay",
                "IsActive",
                "Remarks",
                "EmployeeGroupName", "EmpGradeName", "EmpTitleName",
                "Color", "VehicleNo"
            ) VALUES %s
            ON CONFLICT ("EmployeeIDPK") DO UPDATE SET
                user_id                = EXCLUDED.user_id,
                user_name              = EXCLUDED.user_name,
                "EmployeeCode"         = EXCLUDED."EmployeeCode",
                "EmployeeFullName"     = EXCLUDED."EmployeeFullName",
                "FirstName"            = EXCLUDED."FirstName",
                "LastName"             = EXCLUDED."LastName",
                "EmpDateofBirth"       = EXCLUDED."EmpDateofBirth",
                "EmpGenderName"        = EXCLUDED."EmpGenderName",
                "MaritalStatus"        = EXCLUDED."MaritalStatus",
                "NationalityName"      = EXCLUDED."NationalityName",
                "CountryName"          = EXCLUDED."CountryName",
                "EmpDateOfJoin"        = EXCLUDED."EmpDateOfJoin",
                "ProbationPeriod"      = EXCLUDED."ProbationPeriod",
                "DateofConfirmation"   = EXCLUDED."DateofConfirmation",
                "LeftJobOnDate"        = EXCLUDED."LeftJobOnDate",
                "CreatedTtm"           = EXCLUDED."CreatedTtm",
                "OrganisationName"     = EXCLUDED."OrganisationName",
                "DepartmentName"       = EXCLUDED."DepartmentName",
                "DesignationName"      = EXCLUDED."DesignationName",
                "ClassificationName"   = EXCLUDED."ClassificationName",
                "Branch"               = EXCLUDED."Branch",
                "NatureOfWorkName"     = EXCLUDED."NatureOfWorkName",
                "EmployeeTypeName"     = EXCLUDED."EmployeeTypeName",
                "EmploymentTypeName"   = EXCLUDED."EmploymentTypeName",
                "ShiftName"            = EXCLUDED."ShiftName",
                "ShiftCode"            = EXCLUDED."ShiftCode",
                "IsAttendanceEnable"   = EXCLUDED."IsAttendanceEnable",
                "IsSinglePunch"        = EXCLUDED."IsSinglePunch",
                "WorkHours"            = EXCLUDED."WorkHours",
                "WrkPerDay"            = EXCLUDED."WrkPerDay",
                "IsActive"             = EXCLUDED."IsActive",
                "Remarks"              = EXCLUDED."Remarks",
                "EmployeeGroupName"    = EXCLUDED."EmployeeGroupName",
                "EmpGradeName"         = EXCLUDED."EmpGradeName",
                "EmpTitleName"         = EXCLUDED."EmpTitleName",
                "Color"                = EXCLUDED."Color",
                "VehicleNo"            = EXCLUDED."VehicleNo",
                updated_at             = NOW()
        """, rows, page_size=1000)

        # ── COUNT after upsert ────────────────────────────────
        cursor.execute(
            "SELECT COUNT(*) FROM public.employee_master WHERE user_name = %s",
            (user_name,)
        )
        after_count = cursor.fetchone()[0]
        log.info(f"    [Employee] Records in DB after upsert: {after_count}")

        # ── Accurate split ────────────────────────────────────
        inserted = after_count - before_count
        updated  = len(records) - inserted

    except Exception as e:
        log.error(f"    ⚠️  Employee batch upsert failed: {e}")
        errors = len(records)

    log.info(
        f"    Employee → Sent={len(records)} | "
        f"Inserted={inserted} (new rows) | "
        f"Updated={updated} (existing rows) | "
        f"Errors={errors}"
    )
    return inserted, updated, errors
