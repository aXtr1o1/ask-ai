"""
Analysis Metadata — sb module

Schedule Bookings (Housekeeping / Environmental / Cleanliness services).
Records represent pre-scheduled recurring service bookings generated
for contracts at specific locations.

Field names verified against actual SP response data.
"""

SB_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "SBCreWorkOrder": (
        "Unique schedule booking work order number. Primary reference ID. "
        "Format: 'AA-1-2026'."
    ),

    # --- Classification ---
    "PPMStageName": (
        "Current workflow stage of the schedule booking. "
        "Examples: 'Staff Yet to be Allocated' (no technician assigned), "
        "'Technician Assigned' (allocated, work pending), "
        "'Execution Completed & Closed' (done)."
    ),
    "FrequencyName": (
        "How often this booking recurs. "
        "Known values: 'MONTHLY', 'QUARTERLY', 'HALFYEARLY', 'ANNUAL'."
    ),
    "ServiceTypeName": (
        "Category of service. Examples: 'Environmental Services', "
        "'Housekeeping Services', 'Air Conditioning Services'."
    ),
    "DivisionName": (
        "Service division responsible for delivery. "
        "Examples: 'Envrionmental Services', 'Housekeeping', 'HVAC System'."
    ),
    "DisciplineName": (
        "Technical sub-category within the division. Example: 'Landscaping'."
    ),
    "ContractName": (
        "Maintenance contract under which this booking is scheduled. "
        "Example: 'Environmental Services - Annual Contract'."
    ),
    "LocalityCode": (
        "Short locality code. Examples: 'AA' (Ajman), 'DM' (Doha), 'RUW' (Ruwi)."
    ),
    "Remarks": (
        "Free-text remarks for this booking. Example: 'Generated'."
    ),

    # --- Personnel ---
    "SBTechName": (
        "Name of the technician assigned to this booking. Null if not yet allocated."
    ),
    "PMTechRemarks": (
        "Remarks entered by the technician on completion."
    ),
    "PMSBLastSBRemarks": (
        "Most recent standby remarks entered when this booking was paused."
    ),
    "PMSBLastSBDateTime": (
        "Date and time of the most recent standby event."
    ),
    "PMSBStaffAssignBy": (
        "Name or ID of the person who assigned the technician to this booking."
    ),

    # --- Location ---
    "LocalityName": (
        "Geographic locality. Examples: 'Ajman', 'Doha', 'Ruwi'."
    ),
    "BuildingName": (
        "Building where the service will be performed. Example: 'Al Safia Park'."
    ),
    "FloorName": (
        "Floor within the building. Null if floor-level tracking is not applicable."
    ),
    "SpotName": (
        "Specific spot, room, or zone. Null if not recorded."
    ),

    # --- Timestamps ---
    "SBCreWoDateTime": (
        "Scheduled date for this booking. Format: 'DD-MM-YYYY'."
    ),
    "SBCreGeneratedTtm": (
        "Date and time this booking record was system-generated. "
        "Format: 'DD-MM-YYYY HH:MM:SS'."
    ),
    "SBCreActualDate": (
        "Actual date of the booking. Format: 'DD-MM-YYYY HH:MM:SS'."
    ),
    "SBCreWoCompletedDate": (
        "Date the booking was completed and closed. Null if still open."
    ),
    "SBTechStartDateTime": (
        "Date and time the technician started the work. Null if not started."
    ),
    "SBTechEndDateTime": (
        "Date and time the technician completed the work. Null if not finished."
    ),

    # --- SLA / Metrics ---
    "SBCreSLAHours": (
        "SLA target in hours within which this booking must be completed."
    ),
    "SBCreMaintenanceHours": (
        "Planned maintenance duration in hours for this booking."
    ),

    # --- Flags ---
    "IsSBCreWithDraw": (
        "Boolean — true if this booking has been withdrawn."
    ),
    "SBCreWithDrawRemarks": (
        "Remarks entered when this booking was withdrawn."
    ),
    "IsSbCreReschedule": (
        "Boolean — true if this booking has been rescheduled."
    ),
    "SBCreRescheduleRemarks": (
        "Remarks entered when this booking was rescheduled."
    ),
    "IsSBCreRework": (
        "Boolean — true if this booking has been marked for rework."
    ),
    "SBCreReworkRemarks": (
        "Remarks entered when this booking was marked for rework."
    ),
}
