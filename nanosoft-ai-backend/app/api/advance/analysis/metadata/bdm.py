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
        "Example: '1716'."
    ),
    "AssetTagNo": (
        "Asset tag number of the equipment linked to this complaint. "
        "Cross-references with the assets module."
    ),
    "AssetBarcode": (
        "Barcode of the asset linked to this complaint."
    ),
    "ClientWoNo": (
        "Client's own work order reference, if applicable."
    ),
    "LocalityCode": (
        "Short code for the locality. Example: 'RUW' (Ruwi), 'DM' (Doha), 'DXB' (Dubai)."
    ),

    # --- Classification ---
    "WoStatus": (
        "Current lifecycle status of the work order. "
        "Known values: 'Open', 'Closed'."
    ),
    "WoTypeName": (
        "Work order type. "
        "Known values: 'Asset' (linked to a registered asset), 'General' (no specific asset)."
    ),
    "PriorityName": (
        "Priority level of the complaint. "
        "Known values: 'P1 Critical', 'P2 High', 'P3 Medium', 'P4 Low'."
    ),
    "StageName": (
        "Detailed workflow stage of the work order. More granular than WoStatus. "
        "Examples: 'Complaint / Service Request Raised', "
        "'Staff Assigned for Analysis / Job Estimation', "
        "'Work in Progress (Analyze)', "
        "'Analyze put on Standby', "
        "'Execution put on Standby', "
        "'Complaint / Service Request - Closed'."
    ),
    "ComplaintTypeName": (
        "Category of the complaint. "
        "Known values: 'Service Request', 'Corrective Maintenance', 'Emergency'."
    ),
    "ComplaintModeName": (
        "Channel through which the complaint was received. "
        "Known values: 'By Call', 'By Mail', 'By Mobile Portal', 'By Web Portal'."
    ),
    "ComplaintNatureName": (
        "Short description of the problem reported. Free-form text. "
        "Examples: 'Printer LCD Panel light not working', 'AC', 'LIGHTS NOT WORKING'."
    ),
    "ComplaintHeaderName": (
        "Approval flow type for this complaint. "
        "Example: 'Without Approval Flow'."
    ),
    "ServiceTypeName": (
        "Type of service. Examples: 'Business Appliances', 'Housekeeping Services', "
        "'Environmental Services', 'Pest control'."
    ),
    "ContractName": (
        "Maintenance contract responsible for resolving this complaint. "
        "Examples: 'Canon Maintenance Contract', 'Pest Control', "
        "'Environmental Services - Annual Contract'."
    ),
    "Description": (
        "Free-text description of the complaint entered at registration."
    ),
    "StandByRemarks": (
        "Remarks entered when the work order was put on standby."
    ),

    # --- Personnel ---
    "AnalysisTechName": (
        "Technician assigned to analyse the complaint. Blank if not yet assigned."
    ),
    "ExecutionTechName": (
        "Technician assigned to execute the repair. Blank if execution has not started."
    ),
    "ComplainerName": (
        "Name of the person who raised the complaint. Examples: 'Waleed', 'gobinath'."
    ),
    "RegisterBy": (
        "Username of the system user who registered the complaint. Example: 'admin'."
    ),

    # --- Location ---
    "LocalityName": (
        "Geographic locality. Examples: 'Ruwi', 'Doha', 'Dubai', 'Al Quoz'."
    ),
    "BuildingName": (
        "Building where the complaint originates. "
        "Examples: 'Building 1', 'Reef Mall', 'Building 1 - Residential High Rise'."
    ),
    "FloorName": (
        "Floor within the building. Examples: 'Ground Floor', 'Floor 1', 'Floor 2'."
    ),
    "SpotName": (
        "Specific spot, room, or zone on the floor. Examples: 'Reception', 'Office'."
    ),
    "DivisionName": (
        "Maintenance division responsible. Examples: 'Business Appliance', "
        "'HVAC System', 'Electrical System', 'Housekeeping'."
    ),
    "DisciplineName": (
        "Technical sub-category within the division. Examples: 'Printer-BA', 'Split Unit-HA'."
    ),

    # --- Timestamps ---
    "ComplainedDateTime": (
        "Date and time the complaint was raised. Format: 'DD-MM-YYYY HH:MM:SS'."
    ),
    "AnalysisStartTime": (
        "Date and time the technician started analysing. Null if not yet started."
    ),
    "AnalysisEndTime": (
        "Date and time analysis was completed. Null if in progress."
    ),
    "ExecutionStartTime": (
        "Date and time execution/repair work started. Null if not yet started."
    ),
    "ExecutionEndTime": (
        "Date and time execution was completed. Null if in progress."
    ),
    "BDMWOCompletedDate": (
        "Date and time the work order was fully closed. Null for open work orders."
    ),
    "SLACCMStartDateTime": (
        "SLA response start deadline — when the response must begin by."
    ),
    "SLACCMEndDateTime": (
        "SLA response end deadline — when the response must be completed by."
    ),
    "SLABDMEndDateTime": (
        "SLA resolution deadline — when the full resolution must be completed by."
    ),

    # --- SLA / TAT ---
    "ResponseTAT": (
        "Response Turnaround Time status. "
        "Known values: 'ROT' (Responded On Time — SLA met), "
        "'NROT' (Not Responded On Time — SLA breached), "
        "blank/null (not yet evaluated)."
    ),
    "ResolutionTAT": (
        "Resolution Turnaround Time status. "
        "Known values: 'COT' (Closed On Time — resolved within SLA), "
        "'SNA' (SLA Not Achieved — resolution breached), "
        "blank/null (not yet resolved)."
    ),
}
