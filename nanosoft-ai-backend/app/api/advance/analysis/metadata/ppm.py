"""
Analysis Metadata — ppm module

Planned Preventive Maintenance.
Records represent scheduled, routine maintenance tasks for registered assets.

Field names verified against actual SP response data.
"""

PPM_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "WorkOrder": (
        "Unique PPM work order number. Format: '50015-RUW-14629-2028'. "
        "Example: '50015-RUW-14629-2028','60020-DM-18540-2029'"
    ),

    "AssetTagNo": (
        "Asset tag number of the equipment being maintained. "
        "Cross-references with the assets module. "
        "Example: 'DM-HVAC-FCU-13734','RUW-EL-LT-1024'"
    ),

    "EquipmentRefNo": (
        "Equipment reference number linking this task to the equipment record. "
        "Example: '019A','020B'"
    ),

    "LocalityCode": (
        "Short locality code. "
        "Example: 'RUW','DM'"
    ),

    # --- Classification ---
    "PPMStatus": (
        "Current lifecycle status of the PPM work order. "
    ),

    "PPMStageName": (
        "Detailed workflow stage within the PPM lifecycle. "
    ),

    "FrequencyName": (
        "How often this task recurs. "
    ),

    "DivisionName": (
        "Maintenance division responsible. "
        "Example: 'HVAC System','Electrical System'"
    ),

    "DisciplineName": (
        "Technical sub-category. "
        "Example: 'Split Unit-HA','FCU'"
    ),

    "ContractName": (
        "Maintenance contract under which this task is executed. "
        "Example: 'Split Unit Maintenance','Facility Management Residential Area'"
    ),

    # --- Equipment ---
    "EquipmentName": (
        "Name of the equipment being maintained. "
        "Example: 'Split Unit 5 - GREE - Livo GEN4 Inverter','FCU'"
    ),

    # --- Location ---
    "LocalityName": (
        "Geographic locality. "
        "Example: 'Ruwi','Doha'"
    ),

    "BuildingName": (
        "Building where the task is to be performed. "
        "Example: 'Building 1','Building 1 - Residential High Rise'"
    ),

    "FloorName": (
        "Floor within the building. "
        "Example: 'Ground Floor','Floor 2'"
    ),

    "SpotName": (
        "Specific spot or zone. "
        "Example: 'Reception','Corridor'"
    ),

    # --- Personnel ---
    "PMTechName": (
        "Name of the technician assigned to this task. Null if not yet allocated. "
        "Example: 'Mohamed Ali','Ramesh Kumar'"
    ),

    "LastStandByRemarks": (
        "Most recent remarks recorded when the PPM task was placed on standby. "
        "Example: 'Waiting for spare parts','Access not available'"
    ),

    "PMTechRemarks": (
        "Remarks entered by the technician during or after completing the maintenance task. Null if not yet done. "
        "Example: 'Maintenance completed','Filter cleaned and tested'"
    ),

    # --- Timestamps ---
    "WoDateTime": (
        "Scheduled date and time for this PPM task. Format: 'DD-MM-YYYY HH:MM:SS'. "
        "Example: '15-07-2026 09:00:00','20-07-2026 14:30:00'"
    ),

    "WoCompletedDate": (
        "Date and time the PPM task was completed. Null for open tasks. "
        "Example: '15-07-2026 11:15:00','20-07-2026 16:45:00'"
    ),

    "PMTechStartDateTime": (
        "Date and time the technician started the work. Null if not started. "
        "Example: '15-07-2026 09:15:00','20-07-2026 14:45:00'"
    ),

    "PMTechEndDateTime": (
        "Date and time the technician completed the work. Null if not finished. "
        "Example: '15-07-2026 11:00:00','20-07-2026 16:30:00'"
    ),

    # --- Metrics ---
    "PPMPendingPeriod": (
        "Days this task has been pending beyond its scheduled date. "
        "0 means on schedule. Positive value means overdue. "
        "Example: '0','15'"
    ),

    "SLADuration": (
        "SLA target duration in days within which this task must be completed. "
        "Example: '180','365'"
    ),
}
