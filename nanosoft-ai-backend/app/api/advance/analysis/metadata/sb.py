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
        "Format: 'AA-1-2026'. "
        "Example: 'AA-1-2026','RUW-15-2026'"
    ),

    # --- Classification ---
    "PPMStageName": (
        "Current workflow stage of the schedule booking. "
    ),

    "FrequencyName": (
        "How often this booking recurs. "
    ),

    "ServiceTypeName": (
        "Category of service. "
    ),

    "DivisionName": (
        "Service division responsible for delivery. "
        "Example: 'Housekeeping','HVAC System'"
    ),

    "DisciplineName": (
        "Technical sub-category within the division. "
        "Example: 'Landscaping','Split Unit-HA'"
    ),

    "ContractName": (
        "Maintenance contract under which this booking is scheduled. "
        "Example: 'Environmental Services - Annual Contract','Facility Management Residential Area'"
    ),

    "LocalityCode": (
        "Short locality code. "
        "Example: 'AA','RUW'"
    ),

    "Remarks": (
        "Free-text remarks for this booking. "
        "Example: 'Generated','Scheduled successfully'"
    ),

    # --- Personnel ---
    "SBTechName": (
        "Name of the technician assigned to this booking. Null if not yet allocated. "
        "Example: 'Mohamed Ali','Ramesh Kumar'"
    ),

    "PMTechRemarks": (
        "Remarks entered by the technician during or after completing the service work. "
        "Example: 'Service completed','Area cleaned successfully'"
    ),

    "PMSBLastSBRemarks": (
        "Most recent standby remarks entered when this booking was paused. "
        "Example: 'Waiting for approval','Materials unavailable'"
    ),

    "PMSBLastSBDateTime": (
        "Date and time of the most recent standby event. "
        "Example: '15-07-2026 10:30:00','18-07-2026 14:15:00'"
    ),

    "PMSBStaffAssignBy": (
        "Name or ID of the person who assigned the technician to this booking. "
        "Example: 'admin','supervisor01'"
    ),

    # --- Location ---
    "LocalityName": (
        "Geographic locality. "
        "Example: 'Ajman','Doha'"
    ),

    "BuildingName": (
        "Building where the service will be performed. "
        "Example: 'Al Safia Park','Building 1 - Residential High Rise'"
    ),

    "FloorName": (
        "Floor within the building. Null if floor-level tracking is not applicable. "
        "Example: 'Ground Floor','Floor 2'"
    ),

    "SpotName": (
        "Specific spot, room, or zone. Null if not recorded. "
        "Example: 'Reception','Common Area'"
    ),

    # --- Timestamps ---
    "SBCreWoDateTime": (
        "Scheduled date and time for this booking. Format: 'DD-MM-YYYY HH:MM:SS'. "
        "Example: '15-07-2026 09:00:00','20-07-2026 14:30:00'"
    ),

    "SBCreGeneratedTtm": (
        "Date and time this booking record was system-generated. "
        "Format: 'DD-MM-YYYY HH:MM:SS'. "
        "Example: '15-07-2026 08:45:00','20-07-2026 14:15:00'"
    ),

    "SBCreActualDate": (
        "Actual date of the booking. Format: 'DD-MM-YYYY HH:MM:SS'. "
        "Example: '15-07-2026 09:05:00','20-07-2026 14:35:00'"
    ),

    "SBCreWoCompletedDate": (
        "Date and time the booking was completed and closed. Null if still open. "
        "Example: '15-07-2026 11:30:00','20-07-2026 17:00:00'"
    ),

    "SBTechStartDateTime": (
        "Date and time the technician started the work. Null if not started. "
        "Example: '15-07-2026 09:10:00','20-07-2026 14:40:00'"
    ),

    "SBTechEndDateTime": (
        "Date and time the technician completed the work. Null if not finished. "
        "Example: '15-07-2026 11:15:00','20-07-2026 16:45:00'"
    ),

    # --- SLA / Metrics ---
    "SBCreSLAHours": (
        "SLA target in hours within which this booking must be completed. "
        "Example: '24','48'"
    ),

    "SBCreMaintenanceHours": (
        "Planned maintenance duration in hours for the scheduled service. "
        "Example: '2','8'"
    ),

    # --- Flags ---
    "IsSBCreWithDraw": (
        "Boolean — true if this booking has been withdrawn. "
        "Example: 'true','false'"
    ),
    "SBCreWithDrawRemarks": (
        "Remarks entered when this booking was withdrawn. "
        "Example: 'Duplicate booking','Client cancelled the service'"
    ),

    "IsSbCreReschedule": (
        "Boolean — true if this booking has been rescheduled. "
        "Example: 'true','false'"
    ),

    "SBCreRescheduleRemarks": (
        "Remarks entered when this booking was rescheduled. "
        "Example: 'Rescheduled due to holiday','Client requested new date'"
    ),

    "IsSBCreRework": (
        "Boolean — true if this booking has been marked for rework. "
        "Example: 'true','false'"
    ),

    "SBCreReworkRemarks": (
        "Remarks entered when this booking was marked for rework. "
        "Example: 'Cleaning incomplete','Area requires reinspection'"
    ),

    "SBCreMRNo": (
        "Maintenance request number from which this schedule booking was generated. "
        "Example: 'MR-10021','MR-10548'"
    ),

    "SBCreParentCreationKey": (
        "Internal parent reference used to link this booking with its originating record. "
        "Example: 'PK-001245','PK-004812'"
    ),

    # --- Flags ---
    "IsSBCreTechManual": (
        "Boolean — true if the technician assignment or update was entered manually. "
        "Example: 'true','false'"
    ),

    "IsSBCreSupManual": (
        "Boolean — true if the supervisor manually updated this booking. "
        "Example: 'true','false'"
    ),

    "IsSBCreMaterial": (
        "Boolean — true if materials are required or allocated for this booking. "
        "Example: 'true','false'"
    ),

    "IsDraft": (
        "Boolean — true if this booking is saved as a draft and not yet finalized. "
        "Example: 'true','false'"
    ),

    "IsActive": (
        "Boolean — true if this booking record is currently active. "
        "Example: 'true','false'"
    ),

    "DeleStat": (
        "Deletion status flag indicating whether this record has been marked as deleted. "
        "Example: 'true','false'"
    ),

   
   # --- Location ---
    "SBCrePPMLattitude": (
        "GPS latitude coordinate indicating the schedule booking location. "
        "Example: '25.2048','24.4539'"
    ),

    "SBCrePPMLongitude": (
        "GPS longitude coordinate indicating the schedule booking location. "
        "Example: '55.2708','54.3773'"
    ),

    # --- Classification Codes ---
    "ContractCode": (
        "Unique code identifying the maintenance contract. "
        "Example: 'CNT001','AMC2026'"
    ),

    "DivisionCode": (
        "Unique code identifying the responsible service division. "
        "Example: 'DIV001','DIV015'"
    ),

    "DisciplineCode": (
        "Unique code identifying the technical discipline. "
        "Example: 'DIS001','DIS025'"
    ),

    "StageSeqNo": (
        "Sequence number representing the current workflow stage. "
    ),

    "FrequencyCode": (
        "Code representing the maintenance frequency. "
        "Example: 'MTH','ANN'"
    ),

    "ServiceTypCode": (
        "Code representing the service type. "
        "Example: 'ENV','HKP'"
    ),

    # --- Financial References ---
    "SBCreChargeLedgerKey": (
        "Ledger key used to identify the charge account for this booking. "
        "Example: 'CLK001','CLK025'"
    ),

    "SBCreCostLedgerKey": (
        "Ledger key used to identify the cost account for this booking. "
        "Example: 'CST001','CST025'"
    ),

    # --- Attachments ---
    "FilePath": (
        "Path to the document or file attachment associated with this schedule booking. "
        "Example: '/uploads/service_report.pdf','/attachments/image_001.jpg'"
    ),

    # --- Audit Information ---
    "CreatedUserID": (
        "Identifier of the user who created this schedule booking record. "
        "Example: 'admin','tech001'"
    ),

    "CreatedTtm": (
        "Date and time when this schedule booking record was created. "
        "Example: '15-07-2026 09:15:00','18-07-2026 14:20:00'"
    ),

    "UpdatedTtm": (
        "Date and time when this schedule booking record was last updated. "
        "Example: '15-07-2026 17:30:00','18-07-2026 18:10:00'"
    ),
}
