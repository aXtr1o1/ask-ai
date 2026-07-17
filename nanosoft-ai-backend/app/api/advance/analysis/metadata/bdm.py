"""
Analysis Metadata — bdm module

Breakdown / Reactive Maintenance (Complaints).
Records represent reactive work orders raised when equipment fails,
a user complains, or an emergency repair is needed.
"""

BDM_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "ComplaintNo": (
        "Unique complaint or work order number assigned to this breakdown ticket. "
        "Primary reference ID for a BDM record. Example: '1617'."
    ),
    "AssetTagNo": (
        "Asset tag number of the equipment or asset linked to this complaint. "
        "Allows cross-referencing breakdown tickets with the assets module."
    ),
    "AssetBarcode": (
        "Barcode of the asset associated with this complaint, used for quick "
        "scanning and lookup during on-site maintenance."
    ),
    "ClientWoNo": (
        "Client's own work order number or reference code, if the client tracks "
        "this complaint in their own system."
    ),

    # --- Classification ---
    "WoStatus": (
        "Current lifecycle status of the breakdown work order. "
        "Known values: 'Open' (work order is active, pending resolution), "
        "'Closed' (work order has been completed and closed). "
        "Filter on 'Open' for all unresolved complaints or 'Closed' for historical records."
    ),
    "PriorityName": (
        "Priority or urgency level of the complaint. "
        "Known values (in descending urgency): "
        "'P1 Critical' (emergency, life-safety or critical system failure), "
        "'P2 High' (high urgency, significant impact on operations), "
        "'P3 Medium' (moderate urgency, planned response acceptable), "
        "'P4 Low' (low urgency, minimal impact). "
        "Filter on this to find high-urgency or critical complaints."
    ),
    "StageName": (
        "Detailed process stage showing where the complaint currently sits in the "
        "workflow. Examples: "
        "'Complaint / Service Request Raised' (newly created, no action yet), "
        "'Staff Assigned for Analysis / Job Estimation' (technician allocated), "
        "'Complaint / Service Request - Closed' (fully resolved and closed). "
        "More granular than WoStatus."
    ),
    "ComplaintTypeName": (
        "Category of the complaint or work order type. "
        "Examples: 'Service Request' (user-initiated service), "
        "'Corrective Maintenance' (fixing a broken or failing system), "
        "'Emergency' (critical failure requiring immediate response)."
    ),
    "ComplaintModeName": (
        "Channel or medium through which the complaint was received. "
        "Known values: 'By Call' (phone call), 'By Mail' (email), "
        "'By Mobile Portal' (mobile app), 'By Web Portal' (web platform). "
        "Useful for analysing complaint intake channel trends."
    ),
    "ComplaintNatureName": (
        "Short description of the nature or problem reported in the complaint. "
        "Examples: 'FCH issue', 'LIGHTS NOT WORKING', 'Ac is not working', "
        "'Water leakage in common area', 'Chiller vibration'. "
        "Free-form text describing the issue raised."
    ),
    "ServiceTypeName": (
        "Type of service associated with this complaint. "
        "Examples: 'Air Conditioning Services', 'Electrical Services', "
        "'Housekeeping Services', 'Ground Handling Services', 'Catering Services'."
    ),
    "WoType": (
        "Work order type classification used for internal reporting and "
        "contract billing purposes."
    ),
    "ContractName": (
        "Name of the maintenance contract or vendor responsible for resolving "
        "this complaint. Examples: 'Facility Management Residential Area', "
        "'BTC - POC - Maintenance of Al Barsha Building', "
        "'Ground Handling Equipment Maintenance'."
    ),

    # --- Personnel ---
    "AnalysisTechName": (
        "Name of the technician assigned to analyse the complaint and estimate "
        "the work scope. May be blank if no technician has been assigned yet. "
        "A blank value here indicates a compliance gap in assignment."
    ),
    "ExecutionTechName": (
        "Name of the technician assigned to execute the actual repair or service. "
        "May be blank if execution has not started. "
        "A blank value on a closed work order is a critical compliance gap."
    ),
    "Complainer": (
        "Name or identity of the person or entity who raised or reported this complaint."
    ),
    "RegisterBy": (
        "Name or username of the system user who registered and created this "
        "complaint in the system."
    ),

    # --- Location ---
    "LocalityName": (
        "Geographic locality, city, or area where the complaint was reported. "
        "Examples: 'Bur Dubai', 'Doha', 'Ajman', 'Terminal - A2'."
    ),
    "BuildingName": (
        "Building or site where the complaint originates. "
        "Examples: 'Bhawan Tower Al Barsha', 'Building 1 - Residential High Rise', "
        "'WATER TREATMENT PLANT', 'CANTEEN'."
    ),
    "FloorName": (
        "Floor level within the building where the problem is located. "
        "May be null for buildings where floor tracking is not applicable."
    ),
    "SpotName": (
        "Specific spot, room, or zone within the floor where the issue was found. "
        "May be null if the exact spot was not recorded."
    ),
    "DivisionName": (
        "Maintenance service division responsible for handling this complaint. "
        "Examples: 'HVAC System', 'Electrical System', 'Plumbing System', "
        "'Housekeeping', 'Low Voltage'."
    ),
    "DisciplineName": (
        "Technical discipline or sub-category within the division. "
        "More specific than DivisionName; used for detailed workload breakdowns."
    ),

    # --- Timestamps ---
    "ComplainedDateTime": (
        "Date and time when the complaint was originally raised or reported. "
        "Format: 'DD-MM-YYYY HH:MM:SS'. Represents the start of the complaint lifecycle."
    ),
    "AnalysisStartTime": (
        "Date and time when the assigned technician started analysing the complaint. "
        "Null if analysis has not yet begun. Used to calculate response time."
    ),
    "AnalysisEndTime": (
        "Date and time when the complaint analysis phase was completed. "
        "Null if analysis is still in progress. "
        "Elapsed time between AnalysisStartTime and AnalysisEndTime gives analysis duration."
    ),
    "ExecutionStartTime": (
        "Date and time when the physical repair or execution work started. "
        "Null if execution has not yet begun."
    ),
    "ExecutionEndTime": (
        "Date and time when the physical repair or execution work was completed. "
        "Null if execution is still in progress."
    ),
    "BDMWOCompletedDate": (
        "Date and time when the entire work order was officially closed. "
        "Null for open work orders. This is the final completion timestamp."
    ),

    # --- SLA / TAT ---
    "ResponseTAT": (
        "Response Turnaround Time (TAT) status — whether the initial response to "
        "the complaint met the SLA target. "
        "Known values: "
        "'ROT' (Responded On Time — SLA met, technician responded within target), "
        "'SNA' (SLA Not Achieved — response was delayed and breached the SLA window), "
        "blank or null (not yet evaluated, complaint is still early-stage or open). "
        "Filter on 'SNA' to find all complaints with delayed responses."
    ),
    "ResolutionTAT": (
        "Resolution Turnaround Time (TAT) status — whether the complaint was fully "
        "resolved within the SLA resolution window. "
        "Known values: "
        "'COT' (Closed On Time — resolved within the SLA window), "
        "'SNA' (SLA Not Achieved — resolution breached the SLA deadline), "
        "blank or null (not yet resolved, complaint is still open). "
        "Filter on 'COT' for on-time closures or 'SNA' for SLA breaches."
    ),
}
