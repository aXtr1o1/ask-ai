
# =============================================================================
# MODULE SCHEMAS
# Key   : exact column name as it appears in the retrieved JSON records
# Value : human-readable description including known enum values where relevant
# =============================================================================

MODULE_SCHEMAS = {

    # =========================================================================
    # assets  —  Physical Asset Register
    # Records represent individual physical assets, equipment, devices, or
    # machines registered in the facility management system.
    # =========================================================================
    "assets": {

        # --- Identifiers ---
        "AssetTagNo": (
            "Unique tag number or identifier assigned to the physical asset. "
            "Used as the primary reference ID for an asset record. "
            "Format example: 'AQ-ELE-SMDB-13837'."
        ),
        "AssetBarcode": (
            "Barcode number printed on the asset label for scanning purposes. "
            "Used during physical verification or inventory audits."
        ),
        "EquipmentName": (
            "Common name or short description of the equipment or asset type, "
            "such as 'Split AC', 'Chiller 2', 'AHU 01', 'Booster Pump', "
            "'smoke detector', 'Window AC', 'DB', 'SMDB'."
        ),
        "EquipmentRefNo": (
            "Equipment reference number or internal code used to cross-reference "
            "the asset with other modules such as PPM work orders."
        ),
        "SerialNo": (
            "Manufacturer serial number of the asset. Useful for warranty tracking, "
            "vendor support, and unique hardware identification."
        ),

        # --- Classification ---
        "StatusName": (
            "Current operational status of the asset. "
            "Known values: 'Online' (asset is active and working), "
            "'Offline' (asset is inactive, decommissioned, or out of service). "
            "Filter on this field to find all active or all decommissioned assets."
        ),
        "ConditionName": (
            "Physical condition or health of the asset as assessed during inspection. "
            "Known values: 'Good' (asset is in good working condition), "
            "'Fair' (asset is functional but showing wear), "
            "'Bad' (asset is deteriorated or in poor condition). "
            "Filter on this field to find assets needing replacement or attention."
        ),
        "PriorityName": (
            "Priority or criticality level of the asset to facility operations. "
            "Known values (in descending criticality): "
            "'P1 Critical' (mission-critical, immediate attention required), "
            "'P2 High' (high-priority, important to operations), "
            "'P3 Medium' (moderate priority, standard maintenance), "
            "'P4 Low' (low priority, minimal operational impact). "
            "Filter on this field to focus on critical or high-priority assets."
        ),
        "AssetTypeName": (
            "Classification of the asset by physical nature. "
            "Known values: 'Fixed' (permanently installed, cannot be relocated), "
            "'Movable' (portable or relocatable equipment). "
            "May be null if the asset type has not been classified."
        ),
        "DivisionName": (
            "Service division or department responsible for maintaining this asset. "
            "Examples: 'HVAC System', 'Electrical System', 'Plumbing System', "
            "'Fire Fighting and Alarm system', 'Housekeeping', 'Motorized', "
            "'Low Voltage'. Used to group assets by maintenance team."
        ),
        "DisciplineName": (
            "Technical discipline or specific sub-category of the asset within its division. "
            "Examples: 'FCU', 'SPLIT AC UNITS', 'WINDOW AC', 'ROOFTOP AAON', "
            "'SMDB', 'DB', 'BOOSTER PUMP', 'Smoke Detector', 'WAT - MTZ'. "
            "More granular than DivisionName."
        ),

        # --- Location ---
        "LocalityName": (
            "Geographic locality, city, or area where the asset is physically located. "
            "Examples: 'Dubai', 'Al Quoz', 'Bur Dubai', 'Ajman'. "
            "Used for location-based grouping and filtering."
        ),
        "BuildingName": (
            "Name of the building, tower, property, or site where the asset is installed. "
            "Examples: 'Reef Mall', 'Bhawan Tower Al Barsha', 'Labour camp-2', "
            "'Building 1 - Residential High Rise'."
        ),
        "FloorName": (
            "Floor level or floor name within the building where the asset is located. "
            "Examples: '1st Level', 'Ground Floor', 'First Floor', 'Floor 9'."
        ),
        "SpotName": (
            "Specific spot, room, zone, or exact location within the floor where the "
            "asset is installed. Examples: 'WASH ROOMS (M/F) - Near Nesto', 'DDC', "
            "'B04', 'Common Area'."
        ),

        # --- Hardware Details ---
        "MakeName": (
            "Manufacturer or brand name of the asset. "
            "Examples: 'Carrier', 'ABB', 'Super general', 'RR', 'OG'. "
            "May be 'Not Specified' if the manufacturer is unknown."
        ),
        "ModelName": (
            "Model number or model name of the asset as specified by the manufacturer. "
            "Examples: 'IED1502AO', 'SMAB', 'Window AC', 'Pump set'. "
            "May be 'N/A' if the model is not recorded."
        ),
        "Owner": (
            "Name of the owner or responsible person/department assigned to this asset."
        ),
        "ServiceArea": (
            "Service area or zone designation for this asset, used to group assets "
            "under a specific operational service boundary."
        ),
        "TradeGroup": (
            "Trade group or trade category the asset belongs to, used for "
            "maintenance planning and contractor assignment."
        ),
        "DrawingNo": (
            "Engineering drawing number or reference document number associated "
            "with this asset, used for technical reference and as-built documentation."
        ),
        "Remarks": (
            "Free-text remarks, notes, or observations about the asset entered "
            "during registration or maintenance visits."
        ),

        # --- Flags ---
        "OnHold": (
            "Boolean flag indicating whether maintenance or operations on this asset "
            "are currently on hold. True means the asset is paused or suspended."
        ),
        "IsSnagged": (
            "Boolean flag indicating whether this asset has been marked as snagged "
            "during an audit or inspection walkthrough. True means a snag was recorded."
        ),
        "IsScraped": (
            "Boolean flag indicating whether this asset has been scrapped or written off "
            "and is no longer in service. True means the asset is decommissioned."
        ),
        "EnablePPM": (
            "Boolean flag indicating whether Planned Preventive Maintenance (PPM) is "
            "enabled for this asset. True means PPM work orders can be generated."
        ),
        "EnableBDM": (
            "Boolean flag indicating whether Breakdown Maintenance (BDM) complaints "
            "can be raised against this asset. True means breakdown tickets are allowed."
        ),
        "EnableBMS": (
            "Boolean flag indicating whether this asset is integrated with the Building "
            "Management System (BMS). True means BMS monitoring is active."
        ),
        "EnableDSM": (
            "Boolean flag indicating whether Demand Side Management (DSM) is enabled "
            "for this asset, typically for energy-intensive equipment."
        ),
    },

    # =========================================================================
    # bdm  —  Breakdown / Reactive Maintenance (Complaints)
    # Records represent reactive work orders raised when equipment fails,
    # a user complains, or an emergency repair is needed.
    # =========================================================================
    "bdm": {

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
    },

    # =========================================================================
    # ppm  —  Planned Preventive Maintenance
    # Records represent scheduled, routine maintenance tasks generated
    # by the PPM system for registered assets at fixed intervals.
    # =========================================================================
    "ppm": {

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
    },

    # =========================================================================
    # fa  —  Facility Audits & Remedial (Snags / Inspections)
    # Records represent structured audit tasks, facility inspections,
    # remedial snags identified during physical walkthroughs, and
    # quality assurance checks.
    # =========================================================================
    "fa": {

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
    },

    # =========================================================================
    # sb  —  Schedule Booking (Housekeeping / Cleanliness Inspections)
    # Records represent pre-scheduled service bookings and cleanliness
    # inspection tasks at specific location spots.
    # =========================================================================
    "sb": {

        # --- Identifiers ---
        "SBRequestNo": (
            "Unique schedule booking request number identifying this SB record. "
            "Primary reference ID. Example: 'SB-2026-001'."
        ),

        # --- Classification ---
        "SBStatus": (
            "Current lifecycle status of the schedule booking. "
            "Known values: 'Open' (booking is scheduled or in progress, not yet completed), "
            "'Closed' (booking has been completed and closed). "
            "Filter on 'Open' to find active or upcoming bookings."
        ),
        "SBStageName": (
            "Detailed workflow stage of the schedule booking. "
            "Example: 'Service Booking Raised' (booking created, awaiting technician assignment). "
            "More granular than SBStatus."
        ),
        "SBTypeName": (
            "Type of the schedule booking defining the nature of the service. "
            "Example: 'Scheduled Service' (a pre-planned, recurring service visit)."
        ),
        "PriorityName": (
            "Priority level of the booking. "
            "Known values: 'P1 Critical', 'P2 High', 'P3 Medium', 'P4 Low'. "
            "Reflects the urgency of carrying out the booked service on time."
        ),
        "ServiceTypeName": (
            "Category of service being performed under this booking. "
            "Example: 'Air Conditioning Services'. "
            "Use to filter bookings by the type of work being scheduled."
        ),
        "DivisionName": (
            "Service division responsible for delivering this booked service. "
            "Example: 'HVAC System'."
        ),
        "ContractName": (
            "Maintenance contract under which this booking is scheduled. "
            "Example: 'Facility Management Residential Area'."
        ),

        # --- Personnel ---
        "RequestedBy": (
            "Username or name of the person who created and submitted this booking. "
            "Example: 'admin'."
        ),
        "TechName": (
            "Name of the technician assigned to carry out this scheduled visit. "
            "Null if no technician has been assigned yet."
        ),

        # --- Location ---
        "LocalityName": (
            "Geographic locality or area where the booking is to be performed. "
            "Example: 'Doha'."
        ),
        "BuildingName": (
            "Building or property where the scheduled service will take place. "
            "Example: 'Building 1 - Residential High Rise'."
        ),
        "FloorName": (
            "Floor level within the building for this booking. "
            "Example: 'Floor 3'."
        ),
        "SpotName": (
            "Specific spot, apartment, room, or zone where the service will be delivered. "
            "Example: 'Appartement-30'. For cleanliness inspections this is the inspected location."
        ),

        # --- Timestamps ---
        "BookedDateTime": (
            "Date and time when the booking was registered in the system. "
            "Format: 'DD-MM-YYYY HH:MM:SS'. Represents when the request was created."
        ),
        "ScheduledDateTime": (
            "Planned date and time when the service is scheduled to be delivered. "
            "Format: 'DD-MM-YYYY HH:MM:SS'. Used to track upcoming appointments."
        ),
        "CompletedDateTime": (
            "Date and time when the booked service was actually completed. "
            "Null for open bookings that have not yet been delivered."
        ),

        # --- Notes ---
        "Remarks": (
            "Free-text remarks, notes, or special instructions related to this booking. "
            "Example: 'Annual AC service booking for apartment block'."
        ),
    },
}

