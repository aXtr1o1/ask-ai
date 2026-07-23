"""
Analysis Metadata — fa module

Facility Audits & Remedial.
Records represent structured audit tasks, facility inspections,
remedial snags, and quality assurance checks.

Field names verified against actual SP response data.
Note: FA records contain many internal DB keys — only operational fields listed here.
"""

FA_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "RMComplaintNo": (
        "Unique audit / remedial complaint number. Primary reference ID. Example: '63'."
    ),

    # --- Classification ---
    "RMStageName": (
        "Current workflow stage of the audit or remedial task. "
        "Examples: 'Facility Audit Request Raised' (created, not yet assigned), "
        "'Staf Assigned for Work Execution' (technician allocated), "
        "'Work Execution Completed' (task done)."
    ),
    "PriorityName": (
        "Priority level of the audit task. "
        "Known values: 'P1 Critical', 'P2 High', 'P3 Medium', 'P4 Low'."
    ),
    "FrequencyName": (
        "How often this audit recurs. "
        "Known values: 'MONTHLY', 'QUARTERLY', 'HALFYEARLY', 'ANNUAL'."
    ),
    "RMCategoryName": (
        "High-level category of the audit. "
        "Examples: 'Pest Control Checks', 'Housekeeping Inspection'."
    ),
    "RMCategorySubName": (
        "Specific audit checklist item within the category. "
        "Examples: 'RODENT ACTIVITY', 'COCKROACH ACTIVITY', "
        "'FLOOR CLEANLINESS', 'WASHROOM CLEANLINESS'."
    ),
    "RMRequestDetailsDesc": (
        "Description of the audit or remedial task. "
        "Examples: 'Pest Control', 'Monthly Housekeeping Audit'."
    ),
    "DivisionName": (
        "Service division responsible for the audit. "
        "Examples: 'Housekeeping', 'Electrical System'."
    ),
    "ContractName": (
        "Maintenance contract under which this audit falls. "
        "Example: 'Facility Management Residential Area'."
    ),
    "LocalityCode": (
        "Short locality code. Examples: 'DM' (Doha), 'RUW' (Ruwi)."
    ),

    # --- Personnel ---
    "RMTechName": (
        "Technician assigned to execute the audit. Null if not yet assigned."
    ),
    "RMTechRemarks": (
        "Remarks entered by the technician after completing the task."
    ),
    "RMMaintenanceRemarks": (
        "Maintenance remarks recorded during or after the task."
    ),
    "RMTechnicalFindings": (
        "Technical findings documented during the audit or inspection."
    ),
    "ReworkRemarks": (
        "Remarks entered if the task was marked for rework."
    ),

    # --- Location ---
    "LocalityName": (
        "Geographic locality. Examples: 'Doha', 'Ruwi'."
    ),
    "BuildingName": (
        "Building being audited. "
        "Example: 'Building 1 - Residential High Rise'."
    ),
    "FloorName": (
        "Floor within the building. Examples: 'Floor 1', 'Ground Floor'."
    ),
    "SpotName": (
        "Specific spot being audited. Examples: 'Garbage Room', 'Common Area'."
    ),

    # --- Timestamps ---
    "RMComplainedDateTime": (
        "Date the audit task was created. Format: 'DD-MM-YYYY'."
    ),
    "RMTeStartDateTime": (
        "Date and time the technician started the audit work. Null if not started."
    ),
    "RMTeEndDateTime": (
        "Date and time the technician completed the audit. Null if not done."
    ),
    "RMBDMWOCompletedDate": (
        "Date the audit work order was officially closed. Null if still open."
    ),
    "RMXComplaintDate": (
        "Original complaint/request date and time for this audit record. "
        "Format: 'DD-MM-YYYY HH:MM:SS'."
    ),

    # --- Metrics ---
    "RMMaintenanceHrs": (
        "Planned maintenance effort in minutes. Example: 60 (1 hour)."
    ),
    "RMManPower": (
        "Number of personnel allocated for this audit task."
    ),
    "RMManHours": (
        "Total man-hours allocated for this audit task."
    ),
    "RMTotalAmount": (
        "Total cost amount for this audit or remedial task."
    ),

    # --- Flags ---
    "IsRMRework": (
        "Boolean — true if this task has been marked for rework."
    ),
    "IsRMWithdraw": (
        "Boolean — true if this task has been withdrawn."
    ),
}
