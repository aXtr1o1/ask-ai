"""
app/services/sync/service_catalog.py
──────────────────────────────────────
Master in-memory catalog of ALL known services.

This is the single source of truth for:
    - Which endpoints exist         (/getAssets, /getPPM, /getBDM)
    - What fields each service has  (fields_config)
    - What keywords route to it     (routing_keywords)
    - What the unique field is      (unique_field — used for upsert dedup)

How it is used:
    - client_endpoint.py  → new client onboarding loops through this list
    - engine.py           → cron sync reads service_key + endpoint from DB
                            (already registered via onboarding)

Future:
    - Replace this in-memory dict with an API call to fetch the catalog
      dynamically. The structure stays the same — just swap get_all_services()
      to make an HTTP request instead of returning the hardcoded list.

Adding a new service in future:
    - Just add a new dict entry below → it will be auto-onboarded for all new clients.
"""

# ══════════════════════════════════════════════════════════════════════════════
# SERVICE CATALOG
# ══════════════════════════════════════════════════════════════════════════════

_SERVICES = [

    # ── ASSETS ────────────────────────────────────────────────────────────────
    {
        "service_key":      "assets",
        "service_name":     "Asset Management",
        "description":      "Tracks all physical assets and equipment across locations.",
        "endpoint":         "/getAssets",
        "unique_field":     "AssetTagNo",
        "routing_keywords": [
            # Generic asset terms
            "asset", "assets", "equipment", "equipments",
            # Equipment types — from real data
            "chiller", "chillers",
            "high loader", "heavy loader", "loader",
            "pushback", "pushback tractor", "towbarless",
            "fire extinguisher",
            "ahu", "air handling unit",
            "pump", "generator", "transformer",
            "vehicle", "vehicles", "duty vehicle",
            # Identification
            "barcode", "asset tag", "tag number", "serial",
            # Status / flags
            "online", "offline", "scrapped", "scrap", "snagged", "snag",
            "on hold", "hold", "retired", "active", "inactive",
            # Condition / priority
            "condition", "good", "bad", "fair", "under repair",
            "priority", "critical", "p1", "p2", "p3", "p4",
            # Classification
            "division", "discipline", "hvac", "plumbing", "electrical",
            "fire fighting", "fire alarm", "duty vehicles",
            # Location
            "building", "floor", "spot", "location", "locality", "zone",
            # Lifecycle
            "installed", "installation", "purchased", "purchase",
            "manufacture", "manufactured", "year of manufacture",
            "life", "lifespan", "scrap date",
            # BMS / PPM / BDM toggles
            "ppm enabled", "bdm enabled", "bms enabled",
            "enable ppm", "enable bdm",
            # Make / model
            "make", "model", "brand",
            "shark", "gold hofer", "schopf", "sdi", "carrier", "trane",
        ],
        "fields_config": {
            "OnHold": {
                "type": "boolean",
                "is_date": False,
                "description": "Whether the asset is currently placed on hold and not in active use. True means the asset is held and unavailable.",
                "aggregatable": False,
            },
            "PurDate": {
                "type": "date",
                "is_date": True,
                "description": "Date when the asset was purchased. Use PurDate_from and PurDate_to for filtering by purchase date range. Example values: 01-04-2026, 02-04-2025, 15-04-2026.",
                "aggregatable": False,
            },
            "MakeName": {
                "type": "string",
                "is_date": False,
                "description": "Manufacturer or brand name of the asset. Example values: SHARK, Gold Hofer, Schopf, SDI, Carrier, Trane, York.",
                "aggregatable": True,
            },
            "PurValue": {
                "type": "string",
                "is_date": False,
                "description": "Purchase value or cost of the asset in currency. Example values: 0.00, 2500.00, 35000.00, 5000.00.",
                "aggregatable": False,
            },
            "SpotName": {
                "type": "string",
                "is_date": False,
                "description": "Specific spot, room, or zone within the floor where the asset is physically placed. Example values: AHU_R1201, Trash Compactor Area, Roof, Common Area Arrivals, Parking Area 5, Electrical Room.",
                "aggregatable": False,
            },
            "FloorName": {
                "type": "string",
                "is_date": False,
                "description": "Floor within the building where the asset is located. Example values: Ground Floor, Roof Level, Roof Top, Apron Level, Parking Floor 5, Floor 1, Floor 9.",
                "aggregatable": True,
            },
            "IsScraped": {
                "type": "boolean",
                "is_date": False,
                "description": "Whether the asset has been scrapped or permanently retired from service. True means the asset is scrapped and no longer in use.",
                "aggregatable": False,
            },
            "IsSnagged": {
                "type": "boolean",
                "is_date": False,
                "description": "Whether the asset has an active snag or defect logged against it. True means a snag exists and the asset has a recorded defect or punch item.",
                "aggregatable": False,
            },
            "ModelName": {
                "type": "string",
                "is_date": False,
                "description": "Model name or number of the asset as specified by the manufacturer. Example values: AST-2P, SHARK, SDI 2045, 2003.",
                "aggregatable": True,
            },
            "ScrapDate": {
                "type": "date",
                "is_date": True,
                "description": "Date when the asset was officially scrapped or retired from service. Use ScrapDate_from and ScrapDate_to for date range filtering.",
                "aggregatable": False,
            },
            "AssetTagNo": {
                "type": "string",
                "is_date": False,
                "description": "Unique tag number that identifies the asset in the system. Example values: L1-HVAC-CHL-3827, AJ-DV-DV-3826, T-A1-DV-DV-3825, DM-FF&AS-FE-13802.",
                "aggregatable": False,
            },
            "LifeInYear": {
                "type": "integer",
                "is_date": False,
                "description": "Expected operational lifespan of the asset in number of years. Example values: 0 (not set), 10, 60.",
                "aggregatable": False,
            },
            "ScrapValue": {
                "type": "string",
                "is_date": False,
                "description": "Residual or scrap value of the asset at the time of disposal. Example values: 0.00, 500.00.",
                "aggregatable": False,
            },
            "StatusName": {
                "type": "string",
                "is_date": False,
                "description": "Current operational status of the asset. Example values: Online, Offline.",
                "aggregatable": True,
            },
            "IsEnableBDM": {
                "type": "boolean",
                "is_date": False,
                "description": "Whether Breakdown Maintenance (BDM) is enabled for this asset. True means BDM work orders can be raised against this asset.",
                "aggregatable": False,
            },
            "IsEnableBMS": {
                "type": "boolean",
                "is_date": False,
                "description": "Whether Building Management System (BMS) monitoring is enabled for this asset. True means the asset is integrated with BMS.",
                "aggregatable": False,
            },
            "IsEnableDSM": {
                "type": "boolean",
                "is_date": False,
                "description": "Whether Demand Side Management (DSM) is enabled for this asset. True means DSM monitoring is active for this asset.",
                "aggregatable": False,
            },
            "IsEnablePPM": {
                "type": "boolean",
                "is_date": False,
                "description": "Whether Planned Preventive Maintenance (PPM) is enabled for this asset. True means scheduled PPM work orders will be generated for this asset.",
                "aggregatable": False,
            },
            "YearOfManuf": {
                "type": "integer",
                "is_date": False,
                "description": "Year the asset was manufactured by the maker. Example values: 0 (not set), 2018, 2020, 2022. ALWAYS use this field instead of updated_at_from/to when the user specifies a manufactured year.",
                "aggregatable": True,
            },
            "AssetBarcode": {
                "type": "string",
                "is_date": False,
                "description": "Barcode number printed on the asset label used for scanning and physical identification. Example values: 44303830, 10973829, 62303827, 118303828.",
                "aggregatable": False,
            },
            "BuildingName": {
                "type": "string",
                "is_date": False,
                "description": "Name of the building where the asset is installed. Example values: Camp, Villa 4, Passenger Terminal Building T1 (Demo), Old Airport Terminal, VIP Terminal, Building 1 - Residential High Rise, Building 2 - Residential High Rise.",
                "aggregatable": True,
            },
            "DivisionName": {
                "type": "string",
                "is_date": False,
                "description": "Division or system category the asset belongs to. Example values: HVAC System, Duty Vehicles, Electrical System, Plumbing System, Fire Fighting and Alarm system, Kitchen Handling Equipments.",
                "aggregatable": True,
            },
            "LocalityName": {
                "type": "string",
                "is_date": False,
                "description": "Physical location, zone, or area where the asset is placed. Example values: Al Jurf, Terminal A1, Terminal - A2, Location 1, Ajman, Doha, Airside Area.",
                "aggregatable": True,
            },
            "PriorityName": {
                "type": "string",
                "is_date": False,
                "description": "Maintenance priority level assigned to the asset. Example values: P1 Critical, P2 High, P3 Medium, P4 Low.",
                "aggregatable": True,
            },
            "ConditionName": {
                "type": "string",
                "is_date": False,
                "description": "Current physical condition of the asset as assessed. Example values: Good, Bad, Fair, Under Repair.",
                "aggregatable": True,
            },
            "EquipmentName": {
                "type": "string",
                "is_date": False,
                "description": "Name or description of the equipment or asset type. Example values: Chiller 1, Heavy Loader, High Loader 10, Pushback Tractor, Pushback Towbarless, Fire Extinguisher.",
                "aggregatable": False,
            },
            "InstalledDate": {
                "type": "date",
                "is_date": True,
                "description": "Date when the asset was physically installed at its location. Use InstalledDate_from and InstalledDate_to for date range filtering. Example values: 01-04-2027, 02-04-2025, 30-04-2026.",
                "aggregatable": False,
            },
            "DisciplineName": {
                "type": "string",
                "is_date": False,
                "description": "Technical discipline or trade the asset belongs to. Example values: CHILLER, Duty Vehicles, Fire Extinguisher, Plumbing, Electrical.",
                "aggregatable": True,
            },
        },
    },

    # ── PPM ───────────────────────────────────────────────────────────────────
    {
        "service_key":      "ppm",
        "service_name":     "Planned Preventive Maintenance",
        "description":      "Tracks scheduled preventive maintenance work orders for all assets.",
        "endpoint":         "/getPPM",
        "unique_field":     "WorkOrder",
        "routing_keywords": [
            # Core PPM terms
            "ppm", "planned", "preventive", "preventative",
            "planned maintenance", "preventive maintenance",
            "scheduled maintenance", "schedule",
            # Work order
            "work order", "wo", "ppm work order",
            # Status
            "open", "closed", "completed", "pending",
            "ppm open", "ppm closed", "ppm pending",
            # Stage terms
            "allocated", "not allocated", "staff allocated",
            "technician assigned", "yet to be allocated",
            # Frequency
            "frequency", "quarterly", "monthly", "annually",
            "weekly", "bi-monthly", "yearly",
            # Equipment types commonly in PPM
            "fire extinguisher", "chiller", "ahu",
            "pump", "generator", "hvac",
            # Technician
            "technician", "tech", "pm tech",
            "assigned technician", "who is assigned",
            # SLA
            "sla", "sla duration", "due",
            "overdue", "pending period",
            # Location
            "building", "floor", "spot", "location", "locality",
            "division", "discipline", "contract",
            # Date references
            "wo date", "work order date", "completed date",
            "start date", "end date",
        ],
        "fields_config": {
            "SpotName": {
                "type": "string",
                "is_date": False,
                "description": "Specific spot or room within the floor where the PPM work order is raised for. Example values: Electrical Room, Telephone room, AHU_R1201, Common Area.",
                "aggregatable": False,
            },
            "FloorName": {
                "type": "string",
                "is_date": False,
                "description": "Floor within the building where the PPM work order asset is located. Example values: Floor 1, Floor 2, Ground Floor, Roof Level.",
                "aggregatable": True,
            },
            "PPMStatus": {
                "type": "string",
                "is_date": False,
                "description": "Current status of the PPM work order. Example values: Open, Closed. Use this to filter open or completed PPM work orders.",
                "aggregatable": True,
            },
            "WorkOrder": {
                "type": "string",
                "is_date": False,
                "description": "Unique work order number for the PPM task. Example values: 50010-DM-14264-2026, 50010-DM-14262-2026.",
                "aggregatable": False,
            },
            "AssetTagNo": {
                "type": "string",
                "is_date": False,
                "description": "Tag number of the asset this PPM work order is raised for. Example values: DM-FF&AS-FE-13802, DM-FF&AS-FE-13800, L1-HVAC-CHL-3827.",
                "aggregatable": False,
            },
            "PMTechName": {
                "type": "string",
                "is_date": False,
                "description": "Name of the technician assigned to carry out this PPM work order. Null if no technician has been assigned yet. Example values: Technician, John Smith.",
                "aggregatable": True,
            },
            "WoDateTime": {
                "type": "date",
                "is_date": True,
                "description": "Scheduled date for the PPM work order to be carried out. Use WoDateTime_from and WoDateTime_to for date range filtering. Example values: 09-11-2026, 10-05-2026, 09-02-2026.",
                "aggregatable": False,
            },
            "SLADuration": {
                "type": "integer",
                "is_date": False,
                "description": "SLA duration in minutes or hours allowed to complete this PPM work order. Example values: 30, 60, 120.",
                "aggregatable": False,
            },
            "BuildingName": {
                "type": "string",
                "is_date": False,
                "description": "Name of the building where the PPM work order asset is installed. Example values: Building 1 - Residential High Rise, Building 2 - Residential High Rise, Passenger Terminal Building T1 (Demo).",
                "aggregatable": True,
            },
            "ContractName": {
                "type": "string",
                "is_date": False,
                "description": "Name of the maintenance contract under which this PPM work order is raised. Example values: Facility Management Residential Area, Maintenance of MEP Equipments (DEMO).",
                "aggregatable": True,
            },
            "DivisionName": {
                "type": "string",
                "is_date": False,
                "description": "Division or system category the PPM asset belongs to. Example values: Fire Fighting and Alarm system, HVAC System, Electrical System, Plumbing System.",
                "aggregatable": True,
            },
            "LocalityName": {
                "type": "string",
                "is_date": False,
                "description": "Physical location or zone where the PPM work order asset is located. Example values: Doha, Terminal A1, Terminal - A2, Ajman, Al Jurf.",
                "aggregatable": True,
            },
            "PPMStageName": {
                "type": "string",
                "is_date": False,
                "description": "Current workflow stage of the PPM work order. Example values: Staff Yet to be Allocated, Technician Assigned, Work In Progress, Completed.",
                "aggregatable": True,
            },
            "EquipmentName": {
                "type": "string",
                "is_date": False,
                "description": "Name of the equipment or asset the PPM work order is raised for. Example values: Fire Extinguisher, Chiller 1, AHU, Pump, Generator.",
                "aggregatable": True,
            },
            "FrequencyName": {
                "type": "string",
                "is_date": False,
                "description": "Maintenance frequency schedule for this PPM work order. Example values: QUARTERLY, MONTHLY, ANNUALLY, WEEKLY, BI-MONTHLY.",
                "aggregatable": True,
            },
            "DisciplineName": {
                "type": "string",
                "is_date": False,
                "description": "Technical discipline of the asset this PPM is for. Example values: Fire Extinguisher, CHILLER, Plumbing, Electrical, Duty Vehicles.",
                "aggregatable": True,
            },
            "WoCompletedDate": {
                "type": "date",
                "is_date": True,
                "description": "Date and time when the PPM work order was marked as completed. Null if still open. Use WoCompletedDate_from and WoCompletedDate_to for date range filtering.",
                "aggregatable": False,
            },
            "PPMPendingPeriod": {
                "type": "integer",
                "is_date": False,
                "description": "Number of days the PPM work order has been pending past its scheduled date. Example values: 0 (not overdue), 5, 15, 30.",
                "aggregatable": False,
            },
            "PMTechEndDateTime": {
                "type": "date",
                "is_date": True,
                "description": "Date and time when the assigned technician finished working on the PPM work order. Use PMTechEndDateTime_from and PMTechEndDateTime_to for date range filtering.",
                "aggregatable": False,
            },
            "PMTechStartDateTime": {
                "type": "date",
                "is_date": True,
                "description": "Date and time when the assigned technician started working on the PPM work order. Use PMTechStartDateTime_from and PMTechStartDateTime_to for date range filtering.",
                "aggregatable": False,
            },
        },
    },

    # ── BDM / COMPLAINTS ──────────────────────────────────────────────────────
    {
        "service_key":      "complaints",
        "service_name":     "Complaint & BDM Work Orders",
        "description":      "Tracks corrective maintenance complaints and breakdown work orders.",
        "endpoint":         "/getBDM",
        "unique_field":     "ComplaintNo",
        "routing_keywords": [
            # Core complaint / BDM terms
            "complaint", "complaints", "bdm", "breakdown",
            "corrective", "corrective maintenance",
            "service request", "work order",
            # Status
            "open", "closed", "resolved", "pending",
            "complaint open", "complaint closed",
            # Stage
            "raised", "assigned", "analysis", "execution",
            "staff assigned", "work execution", "job estimation",
            # Nature of complaint — from real data
            "water leakage", "water leak", "leak",
            "light flickering", "lights not working", "lighting",
            "ac noisy", "noisy", "chiller vibration", "vibration",
            "fire related", "fire issue",
            "clean", "cleaning", "housekeeping",
            "fault", "breakdown", "not working", "issue",
            # Priority
            "priority", "critical", "p1", "p2", "p3", "p4",
            "high priority", "low priority",
            # Complaint type
            "corrective maintenance", "service request",
            # Mode
            "by call", "by portal", "community portal",
            # Technician
            "technician", "tech", "analysis tech", "execution tech",
            "assigned technician", "who attended",
            # SLA
            "sla", "response sla", "resolution sla",
            "response tat", "resolution tat",
            "sla breach", "sla missed", "overdue",
            # Division / discipline
            "division", "discipline",
            "hvac", "plumbing", "electrical", "fire fighting",
            "housekeeping", "kitchen", "civil",
            # Location
            "building", "floor", "spot", "location", "locality", "contract",
            # Date references
            "complaint date", "raised date", "completed date",
            "registered", "logged",
        ],
        "fields_config": {
            "SpotName": {
                "type": "string",
                "is_date": False,
                "description": "Specific spot or room within the floor where the complaint was raised. Example values: Common Area 9, Appartement-59, Warehouse building. Null if not specified.",
                "aggregatable": False,
            },
            "WoStatus": {
                "type": "string",
                "is_date": False,
                "description": "Current status of the complaint or BDM work order. Example values: Open, Closed. Use this to filter open or resolved complaints.",
                "aggregatable": True,
            },
            "FloorName": {
                "type": "string",
                "is_date": False,
                "description": "Floor within the building where the complaint was raised. Example values: Ground Floor, Floor 6, Floor 9. Null if the complaint is at building level.",
                "aggregatable": True,
            },
            "StageName": {
                "type": "string",
                "is_date": False,
                "description": "Current workflow stage of the complaint. Example values: Complaint / Service Request Raised, Staff Assigned for Analysis / Job Estimation, Staff Assigned for Work Execution, Complaint / Service Request - Closed.",
                "aggregatable": True,
            },
            "AssetTagNo": {
                "type": "string",
                "is_date": False,
                "description": "Tag number of the asset linked to this complaint. May be empty if no specific asset is associated. Example values: L1-HVAC-CHL-3827, T-A1-DV-DV-3825.",
                "aggregatable": False,
            },
            "RegisterBy": {
                "type": "string",
                "is_date": False,
                "description": "Username of the person who registered or created the complaint in the system. Example values: helpdesk, admin, technician, eashaktech.",
                "aggregatable": True,
            },
            "WoTypeName": {
                "type": "string",
                "is_date": False,
                "description": "Type of work order raised for the complaint. Example values: General.",
                "aggregatable": True,
            },
            "ComplaintNo": {
                "type": "string",
                "is_date": False,
                "description": "Unique complaint number identifying the BDM work order. Example values: 1261, 1260, 1255, 1252.",
                "aggregatable": False,
            },
            "ResponseTAT": {
                "type": "string",
                "is_date": False,
                "description": "Response turnaround time status indicating whether the SLA response time was met. Example values: ROT (Response On Time), SNA (SLA Not Applicable). Empty string if not yet evaluated.",
                "aggregatable": False,
            },
            "AssetBarcode": {
                "type": "string",
                "is_date": False,
                "description": "Barcode of the asset linked to this complaint. Null if no asset is associated.",
                "aggregatable": False,
            },
            "BuildingName": {
                "type": "string",
                "is_date": False,
                "description": "Name of the building where the complaint was raised. Example values: WATER TREATMENT PLANT, Warehouse building, Building 1 - Residential High Rise, Building 2 - Residential High Rise, Passenger Terminal Building T1 (Demo), Runway 18/36.",
                "aggregatable": True,
            },
            "ContractName": {
                "type": "string",
                "is_date": False,
                "description": "Name of the maintenance contract under which this complaint is raised. Example values: Maintenance of MEP Equipments (DEMO), Facility Management Residential Area.",
                "aggregatable": True,
            },
            "DivisionName": {
                "type": "string",
                "is_date": False,
                "description": "Division or system the complaint belongs to. Example values: Plumbing System, Electrical System, HVAC System, Fire Fighting and Alarm system, Housekeeping, Kitchen Handling Equipments.",
                "aggregatable": True,
            },
            "LocalityName": {
                "type": "string",
                "is_date": False,
                "description": "Physical location or zone where the complaint was raised. Example values: Terminal - A2, Airside Area, Ajman, Doha, Terminal A1.",
                "aggregatable": True,
            },
            "PriorityName": {
                "type": "string",
                "is_date": False,
                "description": "Priority level assigned to the complaint. Example values: P1 Critical, P2 High, P3 Medium, P4 Low.",
                "aggregatable": True,
            },
            "ResolutionTAT": {
                "type": "string",
                "is_date": False,
                "description": "Resolution turnaround time status indicating whether the SLA resolution time was met. Example values: COT (Completed On Time), SNA (SLA Not Applicable). Empty string if not yet evaluated.",
                "aggregatable": False,
            },
            "ComplainerName": {
                "type": "string",
                "is_date": False,
                "description": "Name of the person who raised or submitted the complaint. Example values: eashaktech, MOhamed, naina muhamed, gowthaman, technician.",
                "aggregatable": False,
            },
            "DisciplineName": {
                "type": "string",
                "is_date": False,
                "description": "Technical discipline linked to this complaint. Example values: CHILLER, Plumbing, Electrical, Fire Extinguisher. Null if not specified.",
                "aggregatable": True,
            },
            "AnalysisEndTime": {
                "type": "date",
                "is_date": True,
                "description": "Date and time when the analysis or job estimation phase was completed. Use AnalysisEndTime_from and AnalysisEndTime_to for filtering. Example: 21-04-2026 16:12:45.",
                "aggregatable": False,
            },
            "ServiceTypeName": {
                "type": "string",
                "is_date": False,
                "description": "Type of service the complaint falls under. Example values: Air Conditioning Services, Plumbing Services, Electrical Services, Environmental Services, IT Service Management.",
                "aggregatable": True,
            },
            "AnalysisTechName": {
                "type": "string",
                "is_date": False,
                "description": "Name of the technician assigned for the analysis or job estimation phase. Example values: Technician, eashaktech, Employee18 (capital cateringTech).",
                "aggregatable": True,
            },
            "ExecutionEndTime": {
                "type": "date",
                "is_date": True,
                "description": "Date and time when the execution or repair work was completed. Use ExecutionEndTime_from and ExecutionEndTime_to for filtering.",
                "aggregatable": False,
            },
            "AnalysisStartTime": {
                "type": "date",
                "is_date": True,
                "description": "Date and time when the technician started the analysis or job estimation for this complaint. Use AnalysisStartTime_from and AnalysisStartTime_to for filtering. Example: 21-04-2026 16:08:24.",
                "aggregatable": False,
            },
            "ComplaintModeName": {
                "type": "string",
                "is_date": False,
                "description": "Channel through which the complaint was submitted. Example values: By Call, By Community Portal.",
                "aggregatable": True,
            },
            "ComplaintTypeName": {
                "type": "string",
                "is_date": False,
                "description": "Type of complaint raised. Example values: Corrective Maintenance, Service Request.",
                "aggregatable": True,
            },
            "ExecutionTechName": {
                "type": "string",
                "is_date": False,
                "description": "Name of the technician assigned to execute or carry out the repair work. Example values: Technician, Employee18 (capital cateringTech). Empty if not yet assigned.",
                "aggregatable": True,
            },
            "SLABDMEndDateTime": {
                "type": "date",
                "is_date": True,
                "description": "SLA deadline date and time by which the BDM (Breakdown Maintenance) work must be completed. Use SLABDMEndDateTime_from and SLABDMEndDateTime_to for filtering. Example: 22-04-2026 04:07:34.",
                "aggregatable": False,
            },
            "SLACCMEndDateTime": {
                "type": "date",
                "is_date": True,
                "description": "SLA deadline date and time by which the CCM (Corrective / Complaint) work must be completed. Use SLACCMEndDateTime_from and SLACCMEndDateTime_to for filtering. Example: 22-04-2026 00:07:34.",
                "aggregatable": False,
            },
            "BDMWOCompletedDate": {
                "type": "date",
                "is_date": True,
                "description": "Date and time when the BDM work order was marked as fully completed. Null if still open. Use BDMWOCompletedDate_from and BDMWOCompletedDate_to for filtering. Example: 21-04-2026 16:12:45.",
                "aggregatable": False,
            },
            "ComplainedDateTime": {
                "type": "date",
                "is_date": True,
                "description": "Date and time when the complaint was originally raised or logged. Use ComplainedDateTime_from and ComplainedDateTime_to for filtering. Example: 21-04-2026 16:07:38, 20-04-2026 17:56:09.",
                "aggregatable": False,
            },
            "ExecutionStartTime": {
                "type": "date",
                "is_date": True,
                "description": "Date and time when the technician started executing or performing the repair work. Use ExecutionStartTime_from and ExecutionStartTime_to for filtering.",
                "aggregatable": False,
            },
            "ComplaintNatureName": {
                "type": "string",
                "is_date": False,
                "description": "Short description of the nature or subject of the complaint. Example values: Water leakage in common area, light flickering, AC very noisy, Chiller vibration, lights are not working, fire related issues, Need to Clean the Apartment, Water leak in catering.",
                "aggregatable": True,
            },
            "SLABDMStartDateTime": {
                "type": "date",
                "is_date": True,
                "description": "Date and time when the BDM SLA clock started for this complaint. Use SLABDMStartDateTime_from and SLABDMStartDateTime_to for filtering.",
                "aggregatable": False,
            },
            "SLACCMStartDateTime": {
                "type": "date",
                "is_date": True,
                "description": "Date and time when the CCM SLA clock started for this complaint. Use SLACCMStartDateTime_from and SLACCMStartDateTime_to for filtering. Example: 21-04-2026 22:07:34.",
                "aggregatable": False,
            },
        },
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def get_all_services() -> list:
    """
    Return the full list of all known services.

    Called by:
        - client_endpoint.py  → loops through this to onboard all services for a new client
        - Future: replace body with an HTTP call to fetch catalog from external API
    """
    return _SERVICES


def get_service(service_key: str) -> dict | None:
    """
    Return a single service by service_key.
    Returns None if not found.
    """
    for svc in _SERVICES:
        if svc["service_key"] == service_key:
            return svc
    return None