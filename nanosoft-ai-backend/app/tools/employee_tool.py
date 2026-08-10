from langchain.tools import tool
import json
import logging
from fastapi import HTTPException
from app.api.models.schemas import *
from app.models.schemas import *
from app.tools.tool_utils import resolveDate, getTime, logger
from datetime import date, timedelta
from app.api.routes.employee import get_employees

# EMPLOYEE TOOL
# =====================================================
@tool(
    description="""
Use this tool to query employee master records, staff profiles
in the facility management system.

The input schema carries the full field-level knowledge for filtering. When generating the payload:

- For filtering or listing employees by a specific attribute (department, designation, nationality,
  shift, gender, employment type, boolean flags such as is_active, is_attendance_enable, etc.) —
  populate the relevant fields and keep is_aggregate as False.

- For a grouped count or distribution across a workforce dimension (how many employees per
  department, by nationality, by shift, by designation, by gender, by organisation, or any other
  category) — set is_aggregate to True, set group_by_columns to the column the user wants to
  group by, and set aggregate_function to COUNT, SUM, or AVG depending on what the user needs.

Valid values for group_by_columns:
OrganisationName, DepartmentName, DesignationName, ClassificationName, Branch,
NatureOfWorkName, EmployeeTypeName, EmploymentTypeName, ShiftName, EmpGenderName,
NationalityName, CountryName, IsActive, IsAttendanceEnable, EmployeeGroupName,
EmpGradeName, EmpTitleName

Do NOT use this tool for work orders, asset equipment, or contract records.
""",
    args_schema=EmployeeInput
)
def EMPLOYEE(
    user_name=None,
    user_id=None,
    employee_id=None,
    employee_code=None,
    employee_name=None,
    first_name=None,
    last_name=None,
    organisation=None,
    department=None,
    designation=None,
    classification=None,
    branch=None,
    nature_of_work=None,
    employee_type=None,
    employment_type=None,
    shift_name=None,
    shift_code=None,
    gender=None,
    marital_status=None,
    nationality=None,
    country=None,
    employee_group=None,
    emp_grade=None,
    emp_title=None,
    vehicle_no=None,
    is_active=None,
    is_attendance_enable=None,
    is_single_punch=None,
    keyword=None,
    date_from=None,
    date_to=None,
    limit=None,
    offset=None,
    is_aggregate=False,
    group_by_columns=None,
    aggregate_function=None,
) -> str:
    if not user_name:
        logger.error("EMPLOYEE called without user_name")
        return "Error: user_name is required. It is set from the authenticated request."

    logger.info(f"EMPLOYEE TOOL TRIGGERED for user_name: {user_name}")

    resolved_date_from, resolved_date_to = getTime(date_from, date_to)

    payload = {
        "user_name":            user_name,
        "user_id":              user_id,
        "employee_id":          employee_id,
        "employee_code":        employee_code,
        "employee_name":        employee_name,
        "first_name":           first_name,
        "last_name":            last_name,
        "organisation":         organisation,
        "department":           department,
        "designation":          designation,
        "classification":       classification,
        "branch":               branch,
        "nature_of_work":       nature_of_work,
        "employee_type":        employee_type,
        "employment_type":      employment_type,
        "shift_name":           shift_name,
        "shift_code":           shift_code,
        "gender":               gender,
        "marital_status":       marital_status,
        "nationality":          nationality,
        "country":              country,
        "employee_group":       employee_group,
        "emp_grade":            emp_grade,
        "emp_title":            emp_title,
        "vehicle_no":           vehicle_no,
        "is_active":            is_active,
        "is_attendance_enable": is_attendance_enable,
        "is_single_punch":      is_single_punch,
        "keyword":              keyword,
        "date_from":            resolved_date_from,
        "date_to":              resolved_date_to,
        "limit":                limit,
        "offset":               0,
        "is_aggregate":         is_aggregate,
        "group_by_columns":     group_by_columns,
        "aggregate_function":   aggregate_function,
    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    if "offset" not in clean_payload:
        clean_payload["offset"] = 0

    if is_aggregate:
        logger.info("[EMPLOYEE] AGGREGATE MODE | group_by=%s | function=%s", group_by_columns, aggregate_function)

    logger.info("[EMPLOYEE PAYLOAD FROM AI]:\n%s", json.dumps(clean_payload, indent=2, default=str, ensure_ascii=False))

    try:
        logger.info("[EMPLOYEE] Calling get_employees directly")
        req = EmployeeRequest(**clean_payload)
        result = get_employees(req)
        logger.info("[EMPLOYEE] Data processed successfully")
        return json.dumps(result)
    except HTTPException as e:
        logger.error("[EMPLOYEE] API error: %s", e.detail)
        return f"API Error: {e.detail}"
    except Exception as e:
        logger.error("[EMPLOYEE] Tool error: %s", str(e), exc_info=True)
        return f"Error calling EMPLOYEE: {str(e)}"
