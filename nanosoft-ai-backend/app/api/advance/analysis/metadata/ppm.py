"""
Analysis Metadata — ppm module

Planned Preventive Maintenance.
Records represent scheduled, routine maintenance tasks generated
by the PPM system for registered assets at fixed intervals.
"""

PPM_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "WorkOrder": (
        "Unique PPM work order number identifying this preventive maintenance task. "
        "Format example: '50010-DM-14267-2026'."
    ),
    "AssetTagNo": (
        "Asset tag number of the equipment being maintained under this PPM task. "
        "Cross-references with the assets module."
    ),
    "EquipmentRefNo": (
        "Equipment reference number used to link this PPM task to a specific "
        "equipment record in the system."
    ),

    # --- Classification ---
    "PPMStatus": (
        "Current lifecycle status of the PPM work order. "
        "Known values: 'Open' (task is scheduled or in progress, not yet completed), "
        "'Closed' (task has been completed and signed off). "
        "Filter on 'Open' to find all pending or backlogged tasks. "
        "Filter on 'Closed' to analyse completed maintenance history."
    ),
    "PPMStageName": (
        "Detailed workflow stage of the PPM task within its lifecycle. "
        "Examples: "
        "'Staff Yet to be Allocated' (no technician assigned, task is unattended), "
        "'Technician Assigned' (technician allocated but work not yet started), "
        "'Execution Completed & Closed' (work done and order fully closed). "
        "More granular than PPMStatus; use to find tasks stuck at a specific stage."
    ),
    "FrequencyName": (
        "How often this preventive maintenance task is scheduled to recur. "
        "Known values: 'MONTHLY' (every month), 'QUARTERLY' (every 3 months), "
        "'HALFYEARLY' (every 6 months), 'ANNUAL' (once per year). "
        "Filter on this to analyse maintenance workload by frequency."
    ),
    "DivisionName": (
        "Maintenance service division responsible for this PPM task. "
        "Examples: 'HVAC System', 'Fire Fighting and Alarm system', "
        "'Electrical System', 'Plumbing System'."
    ),
    "DisciplineName": (
        "Technical discipline or sub-category of the asset being serviced. "
        "Examples: 'FCU', 'Fire Extinguisher', 'SPLIT AC UNITS'. "
        "More specific than DivisionName."
    ),
    "ContractName": (
        "Maintenance contract under which this PPM task is executed. "
        "Example: 'Facility Management Residential Area'."
    ),

    # --- Equipment ---
    "EquipmentName": (
        "Name or type of the equipment being maintained under this PPM task. "
        "Examples: 'FCU', 'Fire Extinguisher', 'AHU', 'Chiller'. "
        "Use to filter PPM tasks for a specific type of equipment."
    ),

    # --- Location ---
    "LocalityCode": (
        "Short locality code or abbreviation for the area. "
        "Example: 'DM' for Doha or Dubai Marina. Used in work order numbering."
    ),
    "LocalityName": (
        "Full name of the geographic locality or area. "
        "Examples: 'Doha', 'Al Quoz', 'Ajman'."
    ),
    "BuildingName": (
        "Name of the building where this PPM task is to be performed. "
        "Example: 'Building 1 - Residential High Rise'."
    ),
    "FloorName": (
        "Floor level within the building where the maintenance is scheduled. "
        "Examples: 'Floor 1', 'Floor 2', 'Ground Floor'."
    ),
    "SpotName": (
        "Specific spot, room, or zone on the floor where the asset is located. "
        "Examples: 'Corridor', 'Electrical Room', 'Telephone room'."
    ),

    # --- Personnel ---
    "PMTechName": (
        "Name of the PM technician assigned to carry out this maintenance task. "
        "Null if no technician has been assigned yet, indicating the task is "
        "waiting for staff allocation."
    ),

    # --- Timestamps ---
    "WoDateTime": (
        "Scheduled date for this PPM work order to be executed. "
        "Format: 'DD-MM-YYYY'. Represents when the task is planned/due."
    ),
    "WoCompletedDate": (
        "Actual date the PPM work order was completed. "
        "Null for open or pending work orders."
    ),
    "PMTechStartDateTime": (
        "Date and time when the technician physically started the maintenance work. "
        "Null if the technician has not started yet."
    ),
    "PMTechEndDateTime": (
        "Date and time when the technician completed the maintenance work. "
        "Null if the work has not been finished. "
        "Elapsed time between PMTechStartDateTime and PMTechEndDateTime gives execution duration."
    ),

    # --- Notes ---
    "PMTechRemarks": (
        "Remarks or notes entered by the PM technician after completing the task. "
        "Example: 'Work completed'. Null if the task is not yet done or remarks were not entered."
    ),

    # --- Metrics ---
    "PPMPendingPeriod": (
        "Number of days this PPM task has been pending or overdue beyond its "
        "scheduled date. A value of 0 means the task is on schedule. "
        "A positive number represents days of backlog. "
        "Null may appear for future-dated tasks not yet overdue."
    ),
    "SLADuration": (
        "SLA target duration in days within which this PPM task must be completed "
        "once it becomes due. Examples: 3 days (short SLA), 30 days (standard SLA). "
        "Compare with PPMPendingPeriod to assess whether the SLA has been breached."
    ),
}
