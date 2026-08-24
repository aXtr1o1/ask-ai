"""
Analysis Metadata — bdm module

Breakdown / Reactive Maintenance.
Records represent reactive work orders raised when equipment fails,
a user complains, or an emergency repair is needed.

Field names verified against actual SP response data.
"""

BDM_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "ComplaintNo": (
        "Unique complaint / work order number. Primary reference ID for a BDM record. "
        "Example: '1716','1842'"
    ),
    "AssetTagNo": (
        "Asset tag number identifying the equipment associated with this complaint. "
        "Cross-references with the Asset module. "
        "Example: 'DM-HVAC-FCU-13734','DXB-EL-LT-1024'"
    ),
    "AssetBarcode": (
        "Barcode of the asset linked to this complaint. "
        "Example: '11273816','119263818'"
    ),
    "ClientWoNo": (
        "Client's own work order reference, if applicable. "
        "Example: 'CL-10021','WO-45872'"
    ),
    "LocalityCode": (
        "Short code for the locality. "
        "Example: 'RUW','DXB'"
    ),

    # --- Classification ---
    "WoStatus": (
        "Current lifecycle status of the work order. "
    ),

   "WoTypeName": (
    "Category describing the work order type."
    ),

    "PriorityName": (
        "Priority level of the complaint. "
    ),

    "StageName": (
        "Detailed workflow stage of the work order. More granular than WoStatus. "
    ),

    "ComplaintTypeName": (
    "General category describing the nature of the maintenance work."
    ),

    "ComplaintModeName": (
        "Channel through which the complaint was received. "
    ),

    "ComplaintNatureName": (
        "Free-text description of the problem reported. "
        "CRITICAL: Do NOT hardcode search strings for this field into filter_values. "
        "Must be placed in filter_fields for dynamic text searching. "
        "Example: 'AC not cooling'."
    ),

    "ComplaintHeaderName": (
        "Approval flow type for this complaint. "
        "Example: 'Without Approval Flow','Standard Approval'"
    ),
    "ServiceTypeName": (
        "Type of service. "
    ),

    "ContractName": (
        "Maintenance contract responsible for resolving this complaint. "
        "Example: 'Canon Maintenance Contract','Pest Control'"
    ),

    "Description": (
        "Detailed free-text description of the complaint entered during registration. "
        "Example: 'Water leakage near entrance','Split AC not cooling in office'"
    ),

    "StandByRemarks": (
        "Remarks entered when the work order was put on standby. "
        "Example: 'Waiting for spare parts','Awaiting client approval'"
    ),

    # --- Personnel ---
    "AnalysisTechName": (
        "Technician assigned to analyze the complaint. Blank if not yet assigned. "
        "Example: 'Mohamed Ali','Ramesh Kumar'"
    ),

    "ExecutionTechName": (
        "Technician assigned to perform the repair or service work. Blank if execution has not started. "
        "Example: 'John Peter','Suresh Babu'"
    ),

    "ComplainerName": (
        "Name of the person who raised the complaint. "
        "Example: 'Waleed','Gobinath'"
    ),

    "RegisterBy": (
        "Username of the system user who registered the complaint. "
        "Example: 'admin','serviceuser'"
    ),

    # --- Location ---
    "LocalityName": (
        "Geographic locality. "
        "Example: 'Ruwi','Dubai'"
    ),

    "BuildingName": (
        "Building where the complaint originates. "
        "Example: 'Building 1','Reef Mall'"
    ),

    "FloorName": (
        "Floor within the building. "
        "Example: 'Ground Floor','Floor 2'"
    ),

    "SpotName": (
        "Specific spot, room, or zone on the floor. "
        "Example: 'Reception','Office 201'"
    ),

    "DivisionName": (
        "Maintenance division responsible. "
        "Example: 'HVAC System','Electrical System'"
    ),

    "DisciplineName": (
        "Technical sub-category within the division. "
        "Example: 'Split Unit-HA','Printer-BA'"
    ),

    # --- Timestamps ---
    "ComplainedDateTime": (
    "Date and time the complaint was raised. Format: DD-MM-YYYY HH:MM:SS, always populated. "
    "Example: '15-07-2026 09:30:15'."
    ),

    "AnalysisStartTime": (
    "Timestamp technician began analysis, format DD-MM-YYYY HH:MM:SS. "
    "Null if analysis has not started. Example: '15-07-2026 09:45:00'."
    ),

    "AnalysisEndTime": (
        "Date and time analysis was completed. Null if in progress. "
        "Example: '15-07-2026 10:30:00','18-07-2026 15:45:00'"
    ),

    "ExecutionStartTime": (
        "Date and time execution/repair work started. Null if not yet started. "
        "Example: '15-07-2026 11:00:00','18-07-2026 16:00:00'"
    ),

    "ExecutionEndTime": (
        "Date and time execution was completed. Null if in progress. "
        "Example: '15-07-2026 12:45:00','18-07-2026 17:20:00'"
    ),

    "BDMWOCompletedDate": (
        "Date and time the work order was fully closed. Null for open work orders. "
        "Example: '15-07-2026 13:00:00','18-07-2026 17:30:00'"
    ),

    "SLACCMStartDateTime": (
        "SLA response start deadline — when the response must begin by. "
        "Example: '15-07-2026 09:35:00','18-07-2026 14:50:00'"
    ),

    "SLABDMStartDateTime": (
        "SLA resolution start time indicating when the resolution SLA period begins. "
        "Example: '15-07-2026 09:40:00','18-07-2026 14:55:00'"
    ),

    "SLACCMEndDateTime": (
        "SLA response end deadline — when the response must be completed by. "
        "Example: '15-07-2026 10:00:00','18-07-2026 15:15:00'"
    ),

    "SLABDMEndDateTime": (
        "SLA resolution deadline — when the full resolution must be completed by. "
        "Example: '15-07-2026 17:00:00','18-07-2026 20:00:00'"
    ),

    # --- SLA / TAT ---
    "ResponseTAT": (
        "Whether the response met the required turnaround time threshold. "
        "Example: 'NROT','Within SLA'"
    ),

    "ResolutionTAT": (
        "Resolution Turnaround Time status. "
        "Example: 'SNA','Achieved'"
    ),
}
