"""
Analysis Metadata — employees module

Employee / Workforce Register.
Records represent individual employees, technicians, supervisors,
and staff registered in the facility management system.

Field names verified against actual employee_master table data.
"""

EMPLOYEES_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "EmployeeIDPK": (
        "Internal primary key for the employee record. "
        "Example: '1800','1801','1809'"
    ),

    "EmployeeCode": (
        "Unique alphanumeric code assigned to the employee. Primary reference ID. "
        "Example: 'E10001','E10002','E10010'"
    ),

    "EmployeeFullName": (
        "Full name of the employee as registered in the system. "
        "Example: 'Yalcin Akbulut  Akbulut','Adem  Bal','IT  Admin'"
    ),

    "FirstName": (
        "First name of the employee. "
        "Example: 'Yalcin Akbulut','Adem','IT'"
    ),

    "LastName": (
        "Last name or surname of the employee. "
        "Example: 'Akbulut','Bal','Admin'"
    ),

    # --- Organisation / Department ---
    "OrganisationName": (
        "Name of the organisation or company the employee belongs to. "
        "Example: 'Nanosoft POC'"
    ),

    "DepartmentName": (
        "Department the employee is assigned to within the organisation. "
        "Example: 'Facility Management Operations','Procurement','Housekeeping','IT - Information Technology'"
    ),

    "DesignationName": (
        "Job designation or role title of the employee. "
        "Example: 'Manager','Engineer','Supervisor','Technicians','CAFM Admin','Janitors'"
    ),

    "ClassificationName": (
        "Employee classification category. "
        "Example: 'Self'"
    ),

    "Branch": (
        "Branch or office location the employee is assigned to. "
        "Example: 'Main Branch','Dubai Office'"
    ),

    "NatureOfWorkName": (
        "Primary nature or type of work the employee performs. "
        "Example: 'FM Opertations','FM Operations','Technician','Store Keeper','Janitors','Information Technology'"
    ),

    "EmployeeTypeName": (
        "Operational type classification of the employee. Enum — use allowed values only."
    ),

    "EmploymentTypeName": (
        "Employment arrangement type. "
        "Example: 'Full-time','Part-time','Contract'"
    ),

    # --- Shift ---
    "ShiftName": (
        "Name of the shift the employee is assigned to. Enum — use allowed values only."
    ),

    "ShiftCode": (
        "Short code for the employee's shift. "
        "Example: '102','101'"
    ),

    # --- Personal Details ---
    "EmpGenderName": (
        "Gender of the employee. Enum — use allowed values only."
    ),

    "MaritalStatus": (
        "Marital status of the employee. "
        "Example: 'Married','Single',''"
    ),

    "NationalityName": (
        "Nationality of the employee. "
        "Example: 'Indian','British','Filipino'"
    ),

    "CountryName": (
        "Country of origin or residence of the employee. "
        "Example: 'India','United Kingdom','Philippines'"
    ),

    "EmpGradeName": (
        "Salary grade or pay scale classification. "
        "Example: 'Grade A','Grade B'"
    ),

    "EmpTitleName": (
        "Honorific title of the employee. "
        "Example: 'Mr.','Ms.','Dr.'"
    ),

    "Color": (
        "Color code assigned to the employee for scheduling or calendar display. "
        "Example: '#FF5733','#3498DB'"
    ),

    "VehicleNo": (
        "Vehicle number assigned to or used by the employee. "
        "Example: 'DXB-1234','AUH-5678'"
    ),

    "EmployeeGroupName": (
        "Group the employee belongs to for management or reporting purposes. "
        "Example: 'Technical Staff','Admin Group'"
    ),

    # --- Employment Dates ---
    "EmpDateofBirth": (
        "Date of birth of the employee. "
        "Example: '1985-05-15','1990-11-22'"
    ),

    "EmpDateOfJoin": (
        "Date the employee joined the organisation. "
        "Example: '2022-01-10','2023-06-01'"
    ),

    "ProbationPeriod": (
        "Duration of the probation period for the employee. "
        "Example: '3 months','6 months',''"
    ),

    "DateofConfirmation": (
        "Date the employee was confirmed as a permanent member after probation. "
        "Example: '2022-04-10','2023-12-01'"
    ),

    "LeftJobOnDate": (
        "Date the employee left the organisation. Null if still employed. "
        "Example: '2025-03-31','2024-07-15'"
    ),

    "CreatedTtm": (
        "Date and time the employee record was created. "
        "Example: '2025-09-08 09:53:41','2025-09-08 14:35:21'"
    ),

    # --- Work Parameters ---
    "WorkHours": (
        "Total scheduled work hours per cycle for the employee. "
        "Example: '8.00','0.00'"
    ),

    "WrkPerDay": (
        "Number of working hours per day for this employee. "
        "Example: '8.00','0.00'"
    ),

    "Remarks": (
        "Free-text remarks or additional notes about the employee. "
        "Example: 'On extended leave','Transferred from Riyadh office'"
    ),

    # --- Flags ---
    "IsActive": (
        "Boolean — true if the employee is currently active and employed. "
        "Example: 'true','false'"
    ),

    "IsAttendanceEnable": (
        "Boolean — true if attendance tracking is enabled for this employee. "
        "Example: 'true','false'"
    ),

    "IsSinglePunch": (
        "Boolean — true if the employee uses single-punch attendance mode (one check per shift). "
        "Example: 'true','false'"
    ),
}
