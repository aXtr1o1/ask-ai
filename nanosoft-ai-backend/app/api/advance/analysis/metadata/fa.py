"""
Analysis Metadata — fa module

Facility Audits & Remedial (Snags / Inspections).
Records represent structured audit tasks, facility inspections,
remedial snags identified during physical walkthroughs, and
quality assurance checks.
"""

FA_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "RMComplaintNo": (
        "Unique audit or remedial complaint number identifying this FA record. "
        "Primary reference ID for a facility audit task. Example: '63'."
    ),

    # --- Classification ---
    "RMStageName": (
        "Current workflow stage of the audit or remedial task. "
        "Examples: "
        "'Facility Audit Request Raised' (task created, not yet assigned to anyone), "
        "'Staf Assigned for Work Execution' (technician allocated, work is pending), "
        "'Work Execution Completed' (audit or remedial work is done). "
        "Use to track audit pipeline progress and identify backlogged tasks."
    ),
    "PriorityName": (
        "Priority level of the audit or remedial task. "
        "Known values: 'P1 Critical', 'P2 High', 'P3 Medium', 'P4 Low'. "
        "P2 High is typical for safety-related audits such as pest control. "
        "Filter to find high-priority pending audits."
    ),
    "RMCategoryName": (
        "High-level category of the audit or remedial task defining its purpose. "
        "Examples: 'Pest Control Checks', 'Housekeeping Inspection', "
        "'Electrical Safety Audit'. Groups audit records by their broad category."
    ),
    "RMCategorySubName": (
        "Sub-category or specific audit checklist item within the main category. "
        "Examples: 'RODENT ACTIVITY', 'COCKROACH ACTIVITY', "
        "'FLOOR CLEANLINESS', 'WASHROOM CLEANLINESS', 'DB PANEL CHECK'. "
        "The most granular classification of the audit type."
    ),
    "RMRequestDetailsDesc": (
        "Descriptive text for the audit or remedial task explaining the work "
        "required. Examples: 'Pest Control', 'Monthly Housekeeping Audit', "
        "'Quarterly Electrical Audit'."
    ),
    "FrequencyName": (
        "How often this audit or remedial task recurs. "
        "Known values: 'MONTHLY', 'QUARTERLY', 'HALFYEARLY', 'ANNUAL'. "
        "Use to filter by audit schedule frequency."
    ),
    "DivisionName": (
        "Service division responsible for carrying out the audit. "
        "Examples: 'Housekeeping', 'Electrical System'."
    ),
    "ContractName": (
        "Maintenance contract under which this audit task falls. "
        "Examples: 'Facility Management Residential Area', "
        "'Ground Handling Equipment Maintenance'."
    ),

    # --- Personnel ---
    "RMTechName": (
        "Name of the technician, inspector, or janitor assigned to execute "
        "the audit or remedial work. Null if not yet assigned, which means "
        "the task is awaiting staff allocation."
    ),

    # --- Location ---
    "LocalityName": (
        "Geographic locality or area where the audit is taking place. "
        "Examples: 'Doha', 'Ajman', 'Dubai'."
    ),
    "BuildingName": (
        "Building or property being audited. "
        "Examples: 'Building 1 - Residential High Rise', 'Reef Mall'."
    ),
    "FloorName": (
        "Floor level within the building where the audit or snag is located. "
        "Examples: 'Floor 1', 'Floor 2', '1st Level'."
    ),
    "SpotName": (
        "Specific spot, room, or zone within the floor being audited. "
        "Examples: 'Garbage Room', 'Common Area'."
    ),

    # --- Timestamps ---
    "RMComplainedDateTime": (
        "Date when the audit or remedial task was created or raised in the system. "
        "Format: 'DD-MM-YYYY'. Represents the start of the audit lifecycle."
    ),
    "RMTeStartDateTime": (
        "Date and time when the technician started executing the audit or remedial work. "
        "Null if the work has not yet started."
    ),
    "RMTeEndDateTime": (
        "Date and time when the technician completed the audit or remedial work. "
        "Null if the work is still in progress. "
        "Elapsed time between RMTeStartDateTime and RMTeEndDateTime gives execution duration."
    ),
    "RMBDMWOCompletedDate": (
        "Date when the audit or remedial work order was officially completed and closed. "
        "Null for open or still-in-progress tasks. This is the final completion date."
    ),

    # --- Metrics ---
    "RMMaintenanceHrs": (
        "Planned or allocated maintenance effort for this audit or remedial task, "
        "expressed in minutes. Examples: 60 (1 hour), 90 (1.5 hours), 120 (2 hours). "
        "Represents the budgeted time for the task."
    ),
}
