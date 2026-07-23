"""
Analysis Metadata — ppm module

Planned Preventive Maintenance.
Records represent scheduled, routine maintenance tasks for registered assets.

Field names verified against actual SP response data.
"""

PPM_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "WorkOrder": (
        "Unique PPM work order number. Format: '50015-RUW-14629-2028'."
    ),
    "AssetTagNo": (
        "Asset tag number of the equipment being maintained. "
        "Cross-references with the assets module."
    ),
    "EquipmentRefNo": (
        "Equipment reference number linking this task to the equipment record."
    ),
    "LocalityCode": (
        "Short locality code. Example: 'RUW' (Ruwi), 'DM' (Doha)."
    ),

    # --- Classification ---
    "PPMStatus": (
        "Current lifecycle status of the PPM work order. "
        "Known values: 'Open' (scheduled or in progress), 'Closed' (completed)."
    ),
    "PPMStageName": (
        "Detailed workflow stage within the PPM lifecycle. "
        "Examples: 'Staff Yet to be Allocated' (no technician assigned), "
        "'Technician Assigned' (allocated, not yet started), "
        "'Execution Completed & Closed' (fully done)."
    ),
    "FrequencyName": (
        "How often this task recurs. "
        "Known values: 'MONTHLY', 'QUARTERLY', 'HALFYEARLY', 'ANNUAL'."
    ),
    "DivisionName": (
        "Maintenance division responsible. Examples: 'Home Appliances', 'HVAC System', "
        "'Fire Fighting and Alarm system', 'Electrical System'."
    ),
    "DisciplineName": (
        "Technical sub-category. Examples: 'Split Unit-HA', 'FCU', 'Fire Extinguisher'."
    ),
    "ContractName": (
        "Maintenance contract under which this task is executed. "
        "Example: 'Split Unit Maintenance', 'Facility Management Residential Area'."
    ),

    # --- Equipment ---
    "EquipmentName": (
        "Name of the equipment being maintained. "
        "Examples: 'Split Unit 5 - GREE - Livo GEN4 Inverter', 'FCU', 'AHU'."
    ),

    # --- Location ---
    "LocalityName": (
        "Geographic locality. Examples: 'Ruwi', 'Doha', 'Al Quoz'."
    ),
    "BuildingName": (
        "Building where the task is to be performed. "
        "Example: 'Building 1', 'Building 1 - Residential High Rise'."
    ),
    "FloorName": (
        "Floor within the building. Examples: 'Ground Floor', 'Floor 1', 'Floor 2'."
    ),
    "SpotName": (
        "Specific spot or zone. Examples: 'Reception', 'Office', 'Corridor'."
    ),

    # --- Personnel ---
    "PMTechName": (
        "Name of the technician assigned to this task. Null if not yet allocated."
    ),
    "LastStandByRemarks": (
        "Most recent standby remarks entered when the task was paused."
    ),
    "PMTechRemarks": (
        "Remarks entered by the technician on completion. Null if not yet done."
    ),

    # --- Timestamps ---
    "WoDateTime": (
        "Scheduled date for this PPM task. Format: 'DD-MM-YYYY'."
    ),
    "WoCompletedDate": (
        "Actual date the task was completed. Null for open tasks."
    ),
    "PMTechStartDateTime": (
        "Date and time the technician started the work. Null if not started."
    ),
    "PMTechEndDateTime": (
        "Date and time the technician completed the work. Null if not finished."
    ),

    # --- Metrics ---
    "PPMPendingPeriod": (
        "Days this task has been pending beyond its scheduled date. "
        "0 means on schedule. Positive value means overdue."
    ),
    "SLADuration": (
        "SLA target duration in days within which this task must be completed. "
        "Example: 180 (180 days from scheduled date)."
    ),
}
