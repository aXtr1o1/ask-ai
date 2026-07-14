"""
Analysis — Question Definitions

Each question declares:
  - id:           unique identifier used in the API request
  - question:     the full question text sent to the LLM
  - modules:      which data sources (JSON files) to load
  - filter_fields: per module — { actual_column_name: "description of what this field means" }
                   The column name IS the key. The description is the metadata for the LLM.
                   The retrieval step uses these keys directly to filter and project columns.

No routes, no data loading here — pure question configuration.
"""

QUESTIONS: dict = {
    "Q1": {
        "id": "Q1",
        "question": "Show everything related to a specific piece of equipment, including its current information, maintenance history, repairs, inspections, and scheduled activities.",
        "modules": ["assets", "bdm", "fa", "ppm"],
        "filter_values": {
                    "assets": {
                                "AssetTagNo": "DM-HVAC-FCU-13734"
                    },
                    "bdm": {
                                "AssetTagNo": "DM-HVAC-FCU-13734"
                    },
                    "ppm": {
                                "AssetTagNo": "DM-HVAC-FCU-13734"
                    },
                    "fa": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    }
        },
        "filter_fields": {
                    "assets": {
                                "AssetTagNo": "Unique identifier of the specific equipment[cite: 1]",
                                "EquipmentName": "Name or type description of the equipment[cite: 1]",
                                "StatusName": "Current operational status of the asset (e.g. Online, Offline)[cite: 1]",
                                "ConditionName": "Physical state or condition of the equipment[cite: 1]",
                                "PriorityName": "Priority level assignment for the asset[cite: 1]",
                                "BuildingName": "Building facility where the equipment is located[cite: 1]",
                                "FloorName": "Floor level inside the building[cite: 1]",
                                "MakeName": "Manufacturer brand name[cite: 1]",
                                "ModelName": "Model identification sequence[cite: 1]"
                    },
                    "bdm": {
                                "ComplaintNo": "Breakdown or corrective repair request ticket number[cite: 2]",
                                "WoStatus": "Current active status of the repair order (e.g. Open / Closed)[cite: 2]",
                                "ComplaintNatureName": "The documented nature of the breakdown failure[cite: 2]",
                                "ComplainedDateTime": "Timestamp when the equipment issue was reported[cite: 2]",
                                "BDMWOCompletedDate": "Timestamp when the breakdown fix was finalized[cite: 2]"
                    },
                    "fa": {
                                "RMComplaintNo": "Facility audit inspection ticket identifier[cite: 3]",
                                "RMCategoryName": "Inspection category type[cite: 3]",
                                "RMStageName": "Current execution workflow stage of the inspection[cite: 3]",
                                "RMComplainedDateTime": "Date when the inspection request was raised[cite: 3]"
                    },
                    "ppm": {
                                "WorkOrder": "Scheduled preventive maintenance task number[cite: 4]",
                                "PPMStatus": "Status of the scheduled maintenance activity (e.g. Open)[cite: 4]",
                                "PPMStageName": "Allocation or processing state of the maintenance checklist[cite: 4]",
                                "FrequencyName": "Recurrence timeframe pattern (e.g. QUARTERLY)[cite: 4]",
                                "WoDateTime": "Planned or initial system date for the scheduled activity[cite: 4]"
                    }
        }
    },
    "Q2": {
        "id": "Q2",
        "question": "Find all equipment installed in a particular location and display every activity carried out on it.",
        "modules": ["assets", "bdm", "fa", "ppm", "sb"],
        "filter_values": {
                    "assets": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "bdm": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "fa": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "ppm": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "sb": {
                                "BuildingName": "Al Safia Park"
                    }
        },
        "filter_fields": {
                    "assets": {
                                "LocalityName": "Geographic locality or area where the equipment is installed",
                                "BuildingName": "Name of the building facility",
                                "FloorName": "Floor level inside the building",
                                "SpotName": "Specific zone or room location",
                                "AssetTagNo": "Unique asset tag identifier",
                                "EquipmentName": "Name or type description of the equipment"
                    },
                    "bdm": {
                                "LocalityName": "Geographic locality linked to the breakdown complaint",
                                "BuildingName": "Name of the building where the breakdown occurred",
                                "ComplaintNo": "Breakdown work order tracking identifier",
                                "ComplaintNatureName": "The specific breakdown issue reported at the location",
                                "WoStatus": "Current status of the repair request (Open / Closed)"
                    },
                    "fa": {
                                "LocalityName": "Geographic locality of the facility audit inspection",
                                "BuildingName": "Name of the building undergoing inspection",
                                "FloorName": "Floor level where the inspection takes place",
                                "SpotName": "Specific area or room inspected",
                                "RMComplaintNo": "Audit tracking request number",
                                "RMRequestDetailsDesc": "Description of the audit activity carried out"
                    },
                    "ppm": {
                                "LocalityName": "Geographic locality where the preventive maintenance is scheduled",
                                "BuildingName": "Name of the building for the PPM task",
                                "FloorName": "Floor level for the scheduled maintenance",
                                "SpotName": "Specific apartment or zone location",
                                "WorkOrder": "Unique PPM work order number",
                                "PPMStatus": "Current status of the maintenance task (e.g. Open)"
                    },
                    "sb": {
                                "LocalityName": "Geographic locality under the service book contract",
                                "BuildingName": "Name of the building area for the service book task",
                                "SBCreWorkOrder": "Service book generated schedule order key",
                                "PPMStageName": "Current workflow allocation phase of the activity"
                    }
        }
    },
    "Q3": {
        "id": "Q3",
        "question": "Show all maintenance activities completed within a specified time period along with the people responsible and the current progress.",
        "modules": ["bdm", "fa", "ppm", "sb"],
        "filter_values": {
                    "bdm": {
                                "WoStatus": "Closed"
                    },
                    "fa": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "ppm": {
                                "PPMStatus": "Closed"
                    },
                    "sb": {
                                "BuildingName": "Al Safia Park"
                    }
        },
        "filter_fields": {
                    "bdm": {
                                "ComplainedDateTime": "Timestamp when the breakdown complaint was opened[cite: 2]",
                                "BDMWOCompletedDate": "Timestamp when the breakdown activity was completed[cite: 2]",
                                "ExecutionTechName": "The technician or person responsible for executing the repair[cite: 2]",
                                "WoStatus": "Current status tracking the progress of the work order (e.g. Open / Closed)[cite: 2]",
                                "StageName": "Detailed workflow progress stage description[cite: 2]"
                    },
                    "fa": {
                                "RMComplainedDateTime": "System date when the inspection request was raised[cite: 3]",
                                "RMBDMWOCompletedDate": "Completion date of the facility audit activity[cite: 3]",
                                "RMTechName": "The designated technician or person responsible for the audit[cite: 3]",
                                "RMStageName": "Current workflow tracking and operational progress status[cite: 3]"
                    },
                    "ppm": {
                                "WoDateTime": "Date when the preventive maintenance work order was generated[cite: 4]",
                                "WoCompletedDate": "Date when the preventive maintenance activity was finalized[cite: 4]",
                                "PMTechName": "The technician or personnel responsible for the maintenance task[cite: 4]",
                                "PPMStatus": "Overall task progress status (e.g. Open)[cite: 4]",
                                "PPMStageName": "Current operational or allocation progress stage[cite: 4]"
                    },
                    "sb": {
                                "SBCreWoDateTime": "System generation date for the scheduled service book task[cite: 5]",
                                "SBCreWoCompletedDate": "Completion date tracking for the service book activity[cite: 5]",
                                "SBTechName": "The technician or crew member assigned to the service task[cite: 5]",
                                "PPMStageName": "Current resource allocation or progress step of the task[cite: 5]"
                    }
        }
    },
    "Q4": {
        "id": "Q4",
        "question": "List all equipment that is currently unavailable or requires special attention, along with the reason and its maintenance history.",
        "modules": ["assets", "bdm"],
        "filter_values": {
                    "assets": {
                                "StatusName": "Offline"
                    },
                    "bdm": {
                                "WoStatus": "Open"
                    }
        },
        "filter_fields": {
                    "assets": {
                                "AssetTagNo": "Unique identifier of the equipment requiring attention",
                                "EquipmentName": "Name or type description of the equipment",
                                "StatusName": "Current operational status of the asset (e.g. Offline, Online)",
                                "ConditionName": "Physical state or condition of the equipment (e.g. Good)",
                                "PriorityName": "Priority level indicating the urgency of attention (e.g. P2 High)",
                                "IsSnagged": "Flag identifying if the asset has active snags or defects",
                                "IsScraped": "Flag identifying if the asset has been decommissioned or scraped"
                    },
                    "bdm": {
                                "ComplaintNo": "Breakdown work order tracking number representing maintenance history",
                                "WoStatus": "Current status of the repair work order (Open / Closed)",
                                "ComplaintNatureName": "The specific breakdown issue or reason why attention is required",
                                "Description": "Detailed technician notes regarding the actions carried out",
                                "ComplainedDateTime": "Timestamp when the equipment issue was reported"
                    }
        }
    },
    "Q5": {
        "id": "Q5",
        "question": "Show all planned work for equipment that matches a specific maintenance cycle, location, or responsible team.",
        "modules": ["ppm", "sb", "fa"],
        "filter_values": {
                    "ppm": {
                                "BuildingName": "Building 1 - Residential High Rise",
                                "PPMStatus": "Open",
                                "FrequencyName": "MONTHLY"
                    },
                    "sb": {
                                "BuildingName": "Al Safia Park",
                                "FrequencyName": "MONTHLY"
                    },
                    "fa": {
                                "BuildingName": "Building 1 - Residential High Rise",
                                "FrequencyName": "MONTHLY"
                    }
        },
        "filter_fields": {
                    "ppm": {
                                "FrequencyName": "The maintenance cycle recurrence interval (e.g. QUARTERLY) [cite: 15]",
                                "LocalityName": "Geographic locality or area of the planned work [cite: 15]",
                                "BuildingName": "Building facility name where maintenance is planned [cite: 15]",
                                "PMTechName": "The specific technician or team member responsible [cite: 15]",
                                "DivisionName": "The operational service division responsible for the work [cite: 15]",
                                "PPMStatus": "Current status of the planned work order (e.g. Open) [cite: 15]"
                    },
                    "sb": {
                                "FrequencyName": "The service book maintenance cycle recurrence (e.g. MONTHLY) [cite: 18]",
                                "LocalityName": "Geographic locality linked to the scheduled service task [cite: 18]",
                                "BuildingName": "Building facility name for the service book task [cite: 18]",
                                "SBTechName": "The technician or person responsible for the service task [cite: 18]",
                                "DivisionName": "Service division category handling the contract work [cite: 18]"
                    },
                    "fa": {
                                "FrequencyName": "The facility audit maintenance cycle interval (e.g. MONTHLY) [cite: 10]",
                                "LocalityName": "Geographic locality under inspection [cite: 10]",
                                "BuildingName": "Building facility undergoing the planned audit [cite: 10]",
                                "RMTechName": "The technician or auditor responsible for the activity [cite: 10]",
                                "DivisionName": "The service division handling the audit request [cite: 10]"
                    }
        }
    },
    "Q6": {
        "id": "Q6",
        "question": "Display every repair request raised for a particular piece of equipment, including how it was reported, its urgency, and the actions taken.",
        "modules": ["assets", "bdm"],
        "filter_values": {
                    "assets": {
                                "AssetTagNo": "DM-HVAC-FCU-13734"
                    },
                    "bdm": {
                                "AssetTagNo": "DM-HVAC-FCU-13734"
                    }
        },
        "filter_fields": {
                    "assets": {
                                "AssetTagNo": "Unique identification tag assigned to the specific equipment[cite: 1]",
                                "EquipmentName": "Name or type of the equipment[cite: 1]"
                    },
                    "bdm": {
                                "AssetTagNo": "Asset tag linking the repair request to the specific piece of equipment[cite: 2]",
                                "ComplaintNo": "Unique repair request tracking identifier number[cite: 2]",
                                "ComplaintModeName": "How the repair request was reported (e.g. By Call, By Mail)[cite: 2]",
                                "PriorityName": "The urgency or priority level of the repair request (e.g. P4 Low, P3 Medium)[cite: 2]",
                                "ComplaintNatureName": "The documented nature of the breakdown failure[cite: 2]",
                                "Description": "Actions taken or steps required to fix the equipment issue[cite: 2]",
                                "WoStatus": "Current status tracking the progress of the repair request[cite: 2]"
                    }
        }
    },
    "Q7": {
        "id": "Q7",
        "question": "Show all inspection activities carried out for a specific location, including findings, responsible personnel, and completion details.",
        "modules": ["fa"],
        "filter_values": {
                    "fa": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    }
        },
        "filter_fields": {
                    "fa": {
                                "LocalityName": "Geographic locality or area where the inspection was carried out",
                                "BuildingName": "Name of the building facility under inspection",
                                "FloorName": "Floor level inside the building where the inspection took place",
                                "SpotName": "Specific zone, room, or area inspected",
                                "RMRequestDetailsDesc": "Description or type of the inspection activity carried out",
                                "RMTechnicalFindings": "Documented findings or observations discovered during the inspection",
                                "RMTechName": "The technician or auditor responsible for carrying out the inspection",
                                "RMBDMWOCompletedDate": "Completion date and time details for the inspection activity",
                                "RMStageName": "Current operational or completion progress status of the inspection ticket"
                    }
        }
    },
    "Q8": {
        "id": "Q8",
        "question": "Find all scheduled work that has been postponed, reassigned, repeated, or cancelled, and explain its current status.",
        "modules": ["sb", "bdm"],
        "filter_values": {
                    "sb": {
                                "BuildingName": "Al Safia Park"
                    },
                    "bdm": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    }
        },
        "filter_fields": {
                    "sb": {
                                "IsSbCreReschedule": "Flag indicating if the scheduled service task has been postponed or rescheduled[cite: 5]",
                                "SBCreRescheduleRemarks": "Explanation or remarks detailing why the work was postponed[cite: 5]",
                                "IsSBCreRework": "Flag indicating if the scheduled work needs to be repeated[cite: 5]",
                                "SBCreReworkRemarks": "Remarks detailing why the scheduled activity must be repeated[cite: 5]",
                                "IsSBCreWithDraw": "Flag indicating if the scheduled service task has been cancelled or withdrawn[cite: 5]",
                                "SBCreWithDrawRemarks": "Explanation or remarks for the cancelled scheduled work[cite: 5]",
                                "PPMStageName": "The current workflow assignment or progress status of the task[cite: 5]"
                    },
                    "bdm": {
                                "ComplaintNo": "Unique complaint or work order number for the repair request",
                                "WoStatus": "Current status of the corrective repair work order (Open/Closed)",
                                "StageName": "Current operational execution stage of the repair activity",
                                "ComplaintNatureName": "Nature or type of the complaint / defect reported",
                                "StandByRemarks": "Remarks or notes on why work is on standby or pending",
                                "BuildingName": "Building where the corrective repair was raised"
                    }
        }
    },
    "Q9": {
        "id": "Q9",
        "question": "Show every maintenance activity performed on equipment belonging to a particular area, team, or service provider.",
        "modules": ["assets", "bdm", "fa", "ppm", "sb"],
        "filter_values": {
                    "assets": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "bdm": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "fa": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "ppm": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "sb": {
                                "BuildingName": "Al Safia Park"
                    }
        },
        "filter_fields": {
                    "assets": {
                                "LocalityName": "Geographic locality or area of the equipment",
                                "BuildingName": "Building name where the equipment is located",
                                "DivisionName": "Service division team responsible for the asset",
                                "ContractName": "Name of the service provider contract linked to the asset",
                                "AssetTagNo": "Unique identifier of the equipment"
                    },
                    "bdm": {
                                "LocalityName": "Geographic locality or area where the repair was performed",
                                "BuildingName": "Building facility name for the breakdown activity",
                                "DivisionName": "The operational service team handling the repair",
                                "ContractName": "Name of the service provider contract executing the repair",
                                "ComplaintNo": "Breakdown work order tracking identifier"
                    },
                    "fa": {
                                "LocalityName": "Geographic locality or area of the audit activity",
                                "BuildingName": "Building facility name where the audit was conducted",
                                "DivisionName": "The operational service team executing the audit",
                                "ContractName": "Name of the service provider contract handling the audit"
                    },
                    "ppm": {
                                "LocalityName": "Geographic locality or area of the scheduled maintenance",
                                "BuildingName": "Building facility name for the preventive maintenance task",
                                "DivisionName": "The operational service team handling the maintenance task",
                                "ContractName": "Name of the service provider contract managing the PPM task"
                    },
                    "sb": {
                                "LocalityName": "Geographic locality or area of the service book activity",
                                "BuildingName": "Building facility name under the service book task",
                                "DivisionName": "The operational service team handling the service book task",
                                "ContractName": "Name of the service provider contract executing the work order"
                    }
        }
    },
    "Q10": {
        "id": "Q10",
        "question": "Display equipment that has unresolved repair requests together with any planned or scheduled maintenance.",
        "modules": ["assets", "bdm", "ppm", "sb"],
        "filter_values": {
                    "assets": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "bdm": {
                                "BuildingName": "Building 1 - Residential High Rise",
                                "WoStatus": "Open"
                    },
                    "ppm": {
                                "BuildingName": "Building 1 - Residential High Rise",
                                "PPMStatus": "Open"
                    },
                    "sb": {
                                "BuildingName": "Al Safia Park"
                    }
        },
        "filter_fields": {
                    "assets": {
                                "AssetTagNo": "Unique identification tag assigned to the specific equipment",
                                "EquipmentName": "Name or type of the equipment",
                                "StatusName": "Operational status of the asset (e.g. Online, Offline)"
                    },
                    "bdm": {
                                "AssetTagNo": "Asset tag linking the breakdown complaint to the specific piece of equipment",
                                "ComplaintNo": "Unique repair request tracking identifier number",
                                "WoStatus": "Current status of the work order (filtered for 'Open' to show unresolved requests)",
                                "ComplaintNatureName": "The specific breakdown issue reported",
                                "StageName": "Detailed workflow progress stage description"
                    },
                    "ppm": {
                                "AssetTagNo": "Asset tag linking the planned preventive maintenance to the equipment",
                                "WorkOrder": "Unique PPM work order number",
                                "PPMStatus": "Status of the maintenance task (e.g. Open)",
                                "FrequencyName": "The maintenance cycle recurrence interval (e.g. QUARTERLY)",
                                "WoDateTime": "Planned system date for the scheduled activity"
                    },
                    "sb": {
                                "SBCreWorkOrder": "Service book generated schedule order key",
                                "PPMStageName": "Current resource allocation or progress step of the scheduled task",
                                "FrequencyName": "The service book maintenance cycle recurrence (e.g. MONTHLY)",
                                "BuildingName": "Building facility name for the service book task"
                    }
        }
    },
    "Q11": {
        "id": "Q11",
        "question": "Show all work performed by a specific technician across every type of maintenance activity.",
        "modules": ["bdm", "fa", "ppm", "sb"],
        "filter_values": {
                    "bdm": {
                                "AnalysisTechName": "eashaktech"
                    },
                    "fa": {
                                "RMTechName": "eashaktech"
                    },
                    "ppm": {
                                "PMTechName": "Technician"
                    },
                    "sb": {
                                "BuildingName": "Al Safia Park"
                    }
        },
        "filter_fields": {
                    "bdm": {
                                "ExecutionTechName": "The technician or person responsible for executing the repair work",
                                "AnalysisTechName": "The technician responsible for analyzing the breakdown",
                                "ComplaintNo": "Breakdown work order tracking identifier",
                                "WoStatus": "Current status of the repair request (Open / Closed)",
                                "ComplaintNatureName": "The specific breakdown issue handled by the technician",
                                "Description": "Actions or notes provided regarding the completed repair"
                    },
                    "fa": {
                                "RMTechName": "The designated technician or auditor carrying out the inspection activity",
                                "RMComplaintNo": "Audit tracking request number",
                                "RMStageName": "Current operational progress status of the audit workflow",
                                "RMRequestDetailsDesc": "Description of the audit or pest control activity performed"
                    },
                    "ppm": {
                                "PMTechName": "The technician or team member assigned to the preventive maintenance task",
                                "WorkOrder": "Unique PPM work order number",
                                "PPMStatus": "Status of the maintenance task (e.g. Open)",
                                "EquipmentName": "Type or name of the equipment under maintenance",
                                "BuildingName": "Building facility where the task was executed"
                    },
                    "sb": {
                                "SBTechName": "The technician or crew member assigned to the scheduled service book task",
                                "SBCreWorkOrder": "Service book generated schedule order key",
                                "PPMStageName": "Allocation phase state of the service book activity",
                                "ContractName": "Name of the maintenance contract under which work was performed"
                    }
        }
    },
    "Q12": {
        "id": "Q12",
        "question": "Find maintenance activities that exceeded the expected completion time and summarize where they occurred.",
        "modules": ["bdm", "fa"],
        "filter_values": {
                    "bdm": {
                                "BuildingName": "Building 1 - Residential High Rise",
                                "ResolutionTAT": "NCOT"
                    },
                    "fa": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    }
        },
        "filter_fields": {
                    "bdm": {
                                "ComplaintNo": "Breakdown work order tracking identifier number",
                                "ResponseTAT": "Turnaround time status indicating if response met or exceeded SLA (e.g., ROT, NROT)",
                                "ResolutionTAT": "Turnaround time status indicating if resolution met or exceeded SLA (e.g., COT, NCOT)",
                                "LocalityName": "Geographic locality or area where the overdue activity occurred",
                                "BuildingName": "Building facility name linked to the breakdown complaint",
                                "FloorName": "Floor level inside the building facility",
                                "WoStatus": "Current tracking status of the work order (e.g., Closed, Open)"
                    },
                    "fa": {
                                "RMComplaintNo": "Facility audit inspection ticket identifier",
                                "RMOverDueTime": "Tracked metric indicating if or by how much the audit activity exceeded its timeline",
                                "LocalityName": "Geographic area where the audit delay occurred",
                                "BuildingName": "Name of the building facility undergoing inspection",
                                "FloorName": "Floor level associated with the audit request"
                    }
        }
    },
    "Q13": {
        "id": "Q13",
        "question": "Search for equipment or maintenance records using a keyword and show every related activity.",
        "modules": ["assets"],
        "filter_values": {
                    "assets": {
                                "id": 57465,
                                "user_id": 1,
                                "user_name": "poc",
                                "AssetTagNo": "AA-DV-DV-3817",
                                "AssetBarcode": "112303819",
                                "EquipmentName": "Pushback Tractor",
                                "StatusName": "Online",
                                "ConditionName": "Good",
                                "PriorityName": "P4 Low",
                                "OnHold": False,
                                "IsSnagged": False,
                                "IsScraped": False,
                                "LocalityName": "Ajman",
                                "BuildingName": "Building 2 - Residential High Rise",
                                "FloorName": "Parking Floor 5",
                                "SpotName": "Parking Area 5",
                                "DivisionName": "Duty Vehicles",
                                "DisciplineName": "Duty Vehicles",
                                "IsEnablePPM": True,
                                "IsEnableBDM": True,
                                "IsEnableBMS": False,
                                "IsEnableDSM": False,
                                "MakeName": "Schopf",
                                "ModelName": "2003",
                                "YearOfManuf": 0,
                                "LifeInYear": 0,
                                "PurDate": "",
                                "PurValue": 0,
                                "ScrapValue": 0,
                                "EquipmentRefNo": "",
                                "SerialNo": "",
                                "Longitude": "",
                                "Latitude": "",
                                "AssetTypeName": "",
                                "Owner": "",
                                "PurDate": "",
                                "InstalledDate": "",
                                "ScrapDate": "",
                                "ServiceAreaName": "",
                                "TradeGroupName": "",
                                "DrawingNo": "",
                                "Remarks": ""
                    }
        },
        "filter_fields": {
                    "assets": {
                                "AssetTagNo": "Unique asset tag identifier matching keywords[cite: 1]",
                                "EquipmentName": "Name or type description of the equipment matching keywords[cite: 1]",
                                "Remarks": "General remarks text field searchable by keyword[cite: 1]"
                    }
        }
    },
    "Q14": {
        "id": "Q14",
        "question": "Show all work carried out for a particular service agreement, grouped by location and type of work.",
        "modules": ["bdm"],
        "filter_values": {
                    "bdm": {
                                "id": 16359,
                                "user_id": 1,
                                "user_name": "poc",
                                "ComplaintNo": "589",
                                "WoStatus": "Open",
                                "PriorityName": "P4 Low",
                                "StageName": "Complaint / Service Request Raised",
                                "ComplainedDateTime": "31-12-2025 14:59:03",
                                "LocalityName": "Terminal - A2",
                                "LocalityCode": "T - A2",
                                "BuildingName": "Mountain _6",
                                "ComplaintTypeName": "Corrective Maintenance",
                                "ComplaintHeaderName": "ANA Approval Flow",
                                "ComplaintModeName": "By Mail",
                                "ComplaintNatureName": "Weighscale Display flickering",
                                "WoTypeName": "General",
                                "ServiceTypeName": "Plumbing Services",
                                "DivisionName": "Baggage Handling System",
                                "ComplainerName": "ganapathy",
                                "RegisterBy": "helpdesk",
                                "ResponseTAT": "SNA",
                                "SLACCMStartDateTime": "31-12-2025 20:59:03",
                                "SLACCMEndDateTime": "31-12-2025 22:59:03",
                                "SLABDMEndDateTime": "01-01-2026 02:59:03",
                                "AssetBarcode": "",
                                "ClientWoNo": "",
                                "BDMWOCompletedDate": "",
                                "FloorName": "",
                                "SpotName": "",
                                "AnalysisTechName": "",
                                "ExecutionTechName": "",
                                "ResolutionTAT": "",
                                "SLABDMStartDateTime": "",
                                "AnalysisStartTime": "",
                                "AnalysisEndTime": "",
                                "ExecutionStartTime": "",
                                "ExecutionEndTime": "",
                                "StandByRemarks": ""
                    }
        },
        "filter_fields": {
                    "bdm": {
                                "ContractName": "Name of the service provider contract or agreement",
                                "LocalityName": "Geographic locality or area linked to the complaint",
                                "BuildingName": "Building name for location grouping",
                                "ComplaintTypeName": "Classification of the type of work (e.g., Corrective Maintenance, Service Request)",
                                "ServiceTypeName": "Specific functional service domain (e.g., Plumbing Services, Air Conditioning Services)",
                                "ComplaintNo": "Unique breakdown tracking identifier"
                    }
        }
    },
    "Q15": {
        "id": "Q15",
        "question": "Display equipment that has required repeated repairs or inspections and summarize its maintenance history.",
        "modules": ["fa"],
        "filter_values": {
                    "fa": {
                                "id": 1,
                                "user_id": 1,
                                "user_name": "poc",
                                "RMComplaintNo": "63",
                                "RMComplainedDateTime": "03-12-2026",
                                "RMRequestDetailsDesc": "Pest Control",
                                "RMDownloadStat": "0",
                                "RMMaintenanceHrs": "60",
                                "RMFlowSeqNo": "1",
                                "RMBDMStageDesc": "",
                                "RMXComplaintNo": "63",
                                "RMXComplaintDate": "03-12-2026 09:00:00",
                                "IsRMWithdraw": False,                                
                                "IsDraft": False,
                                "IsActive": True,
                                "DeleStat": False,
                                "RMTechName": "Technician",
                                "LocalityCode": "DM",
                                "LocalityName": "Doha",
                                "BuildingCode": "B1",
                                "BuildingName": "Building 1 - Residential High Rise",
                                "FloorName": "Floor 1",
                                "SpotName": "Garbage Room",
                                "ContractCode": "50010",
                                "ContractName": "Facility Management Residential Area",
                                "DivisionCode": "HK",
                                "DivisionName": "Housekeeping",
                                "RMStageSeqNo": "11",
                                "RMStageName": "Staf Assigned for Work Execution",
                                "FrequencyCode": "M",
                                "FrequencyName": "MONTHLY",
                                "PriorityName": "P2 High",
                                "RMCategoryName": "Pest Control Checks",
                                "RMCategorySubName": "RODENT ACTIVITY",
                                "Remarks": "Generated through SmartFM",
                                "RMCCMComplaintIDPK": "63",
                                "RMBDMWOCompletedDate": "",
                                "RMOverDueTime": "",
                                "RMETADate": "",
                                "RMTotalAmount": "",
                                "RMManPower": "",
                                "RMManHours": "",
                                "RMResponseTime": "",
                                "RMResolutionTime": "",
                                "IsRMBMS": "",
                                "IsRMRework": "",
                                "IsRMTechManual": "",
                                "IsRMCCMAnaliyseClosed": "",
                                "ReworkRemarks": "",
                                "RMWithdrawRemarks": "",
                                "RMTechRemarks": "",
                                "RMTeStartDateTime": "",
                                "RMTeEndDateTime": "",
                                "BDMLongitude": "",
                                "BDMLattitude": ""

                    }
        },
        "filter_fields": {
                    "fa": {
                                "RMComplaintNo": "Inspection ticket identifier tracking historical audits[cite: 3]",
                                "IsRMRework": "Flag indicating if the inspection or audit activity required rework[cite: 3]",
                                "RMRequestDetailsDesc": "Description detailing the specific inspection activity carried out[cite: 3]"
                    }
        }
    },
    "Q16": {
        "id": "Q16",
        "question": "Show all activities that were withdrawn, repeated, postponed, inactive, or still in draft, together with the responsible personnel.",
        "modules": ["ppm"],
        "filter_values": {
                    "ppm": {
                                "id": 108422,
                                "user_id": 1,
                                "user_name": "poc",
                                "WorkOrder": "50010-DM-536-2025",
                                "AssetTagNo": "DM-HVAC-FCU-13284",
                                "EquipmentRefNo": "",
                                "PPMStatus": "Open",
                                "PPMStageName": "Preliminary Confirmed & Open",
                                "FrequencyName": "QUARTERLY",
                                "WoDateTime": "31-12-2025",
                                "WoCompletedDate": "",
                                "LocalityName": "Doha",
                                "LocalityCode": "DM",
                                "BuildingName": "Building 1 - Residential High Rise",
                                "FloorName": "Floor 10",
                                "SpotName": "Appartement-1004",
                                "EquipmentName": "FCU",
                                "DivisionName": "HVAC System",
                                "DisciplineName": "FCU",
                                "ContractName": "Facility Management Residential Area",
                                "PMTechName": "",
                                "PMTechStartDateTime": "",
                                "PMTechEndDateTime": "",
                                "PMTechRemarks": "",
                                "LastStandByRemarks": "",
                                "PPMPendingPeriod": "",
                                "SLADuration": 60
                    }
        },
        "filter_fields": {
                    "ppm": {
                                "LocalityName": "Geographic area of the scheduled maintenance task[cite: 4]",
                                "BuildingName": "Building name for location tracking[cite: 4]",
                                "DivisionName": "The responsible team or service division handling the PPM[cite: 4]",
                                "FrequencyName": "The maintenance type cycle (e.g. QUARTERLY)[cite: 4]",
                                "PPMStageName": "Detailed workflow progress stage description[cite: 4]",
                                "PPMStatus": "Overall completion status of the maintenance task (e.g. Open)[cite: 4]"
                    }
        }
    },
    "Q17": {
        "id": "Q17",
        "question": "Generate a summary of work grouped by location, responsible team, work type, progress, urgency, and completion status.",
        "modules": ["sb"],
        "filter_values": {
                    "sb": {
                            "id": 1,
                            "user_id": 1,
                            "user_name": "poc",
                            "SBCreMRNo": "",
                            "SBCreWorkOrder": "AA-1-2026",
                            "SBCreWoDateTime": "02-03-2026",
                            "SBCreGeneratedTtm": "26-03-2026 16:52:28",
                            "SBCreActualDate": "02-03-2026 00:00:00",
                            "SBCreWoCompletedDate": "",
                            "SBCreParentCreationKey": 1,
                            "SBCreSLAHours": "",
                            "SBCreMaintenanceHours": "",
                            "IsSBCreWithDraw": False,
                            "IsSbCreReschedule": False,
                            "IsSBCreRework": False,
                            "IsSBCreTechManual": "",
                            "IsSBCreSupManual": "",
                            "IsSBCreMaterial": "",
                            "IsDraft": False,
                            "IsActive": True,
                            "DeleStat": False,
                            "SBCreWithDrawRemarks": "",
                            "SBCreRescheduleRemarks": "",
                            "SBCreReworkRemarks": "",
                            "SBTechName": "",
                            "PMTechRemarks": "",
                            "PMSBLastSBRemarks": "",
                            "PMSBLastSBDateTime": "",
                            "PMSBStaffAssignBy": "",
                            "SBTechStartDateTime": "",
                            "SBTechEndDateTime": "",
                            "SBCrePPMLattitude": "",
                            "SBCrePPMLongitude": "",
                            "LocalityCode": "AA",
                            "LocalityName": "Ajman",
                            "BuildingName": "Al Safia Park",
                            "FloorName": "",
                            "SpotName": "",
                            "ContractCode": 50012,
                            "ContractName": "Environmental Services - Annual Contract",
                            "DivisionCode": "ENV",
                            "DivisionName": "Envrionmental Services",
                            "DisciplineCode": "LSC",
                            "DisciplineName": "Landscaping",
                            "PPMStageName": "Staff Yet to be Allocated",
                            "StageSeqNo": 1,
                            "FrequencyCode": "M",
                            "FrequencyName": "MONTHLY",
                            "ServiceTypCode": 114,
                            "ServiceTypeName": "Environmental Services",
                            "SBCreChargeLedgerKey": 1,
                            "SBCreCostLedgerKey": 0,
                            "Remarks": "Generated"
                    }
        },
        "filter_fields": {
                    "sb": {
                                "LocalityName": "Geographic location sector under the contract schedule[cite: 5]",
                                "BuildingName": "Building name for location grouping[cite: 5]",
                                "DivisionName": "The responsible team or service division handling the service book task[cite: 5]",
                                "FrequencyName": "The service book type of work recurrence pattern (e.g. MONTHLY)[cite: 5]",
                                "PPMStageName": "The workflow phase tracking current task progress[cite: 5]",
                                "SBCreWoCompletedDate": "Field indicating completion tracking data[cite: 5]"
                    }
        }
    },
    "Q18": {
        "id": "Q18",
        "question": "Compare maintenance performance across different locations by considering repair frequency, completion time, work status, and overall equipment condition.",
        "modules": ["assets", "bdm"],
        "filter_values": {
                    "assets": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "bdm": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    }
        },
        "filter_fields": {
                    "assets": {
                                "LocalityName": "Geographic locality or area for cross-location comparison[cite: 1]",
                                "BuildingName": "Building facility name under the specified location[cite: 1]",
                                "ConditionName": "Overall physical condition score of the equipment (e.g. Good)[cite: 1]",
                                "StatusName": "Operational status tracking whether equipment is Online or Offline[cite: 1]",
                                "AssetTagNo": "Unique asset identifier to correlate location with equipment health[cite: 1]"
                    },
                    "bdm": {
                                "LocalityName": "Geographic locality linked to breakdown tracking[cite: 2]",
                                "ComplaintNo": "Breakdown request tracking number used to compute repair frequency[cite: 2]",
                                "ComplainedDateTime": "Timestamp when the breakdown repair request was registered[cite: 2]",
                                "BDMWOCompletedDate": "Timestamp when the repair was resolved, used to compute completion time[cite: 2]",
                                "WoStatus": "Current work status state of the repair request (Open / Closed)[cite: 2]",
                                "StageName": "Detailed workflow phase describing ongoing repair progress[cite: 2]"
                    }
        }
    },
    "Q19": {
        "id": "Q19",
        "question": "Show the complete lifecycle of a piece of equipment from installation through every planned activity, repair, inspection, and its current condition.",
        "modules": ["assets", "bdm", "fa", "ppm"],
        "filter_values": {
                    "assets": {
                                "AssetTagNo": "DM-HVAC-FCU-13734"
                    },
                    "bdm": {
                                "AssetTagNo": "DM-HVAC-FCU-13734"
                    },
                    "ppm": {
                                "AssetTagNo": "DM-HVAC-FCU-13734"
                    },
                    "fa": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    }
        },
        "filter_fields": {
                    "assets": {
                                "AssetTagNo": "Unique asset tag identifier tracking the specific equipment sequence[cite: 1]",
                                "InstalledDate": "The historical installation date marking the start of the equipment lifecycle[cite: 1]",
                                "PurDate": "The purchase date of the asset item[cite: 1]",
                                "ConditionName": "Current physical health score or condition of the equipment (e.g. Good)[cite: 1]",
                                "StatusName": "Current real-time operational status (e.g. Online, Offline)[cite: 1]",
                                "ScrapDate": "Decommissioning or scrap date marking the final phase of the equipment lifecycle[cite: 1]"
                    },
                    "bdm": {
                                "AssetTagNo": "Asset tag linking historical repair actions back to the specific piece of equipment[cite: 2]",
                                "ComplaintNo": "Breakdown corrective work order tracking number[cite: 2]",
                                "ComplaintNatureName": "The reported nature of the equipment failure[cite: 2]",
                                "WoStatus": "Current workflow status of the repair event (Open / Closed)[cite: 2]"
                    },
                    "fa": {
                                "RMComplaintNo": "Facility audit inspection ticket tracking periodic audit activities[cite: 3]",
                                "RMRequestDetailsDesc": "Description text detailing the specific audit or inspection checklist item[cite: 3]",
                                "RMStageName": "Operational lifecycle progress status of the inspection event[cite: 3]"
                    },
                    "ppm": {
                                "AssetTagNo": "Asset tag linking planned preventive maintenance schedules to the equipment lifecycle[cite: 4]",
                                "WorkOrder": "Unique scheduled preventive maintenance work order tracking code[cite: 4]",
                                "FrequencyName": "Recurrence maintenance cycle category (e.g. QUARTERLY)[cite: 4]",
                                "PPMStatus": "Current status tracking the execution of the scheduled event[cite: 4]"
                    }
        }
    },
    "Q20": {
        "id": "Q20",
        "question": "Generate a comprehensive report showing equipment information, maintenance activities, repair history, inspections, schedules, responsible personnel, completion performance, and an overall summary by location and work type.",
        "modules": ["assets", "bdm", "fa", "ppm", "sb"],
        "filter_values": {
                    "assets": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "bdm": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "fa": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "ppm": {
                                "BuildingName": "Building 1 - Residential High Rise"
                    },
                    "sb": {
                                "BuildingName": "Al Safia Park"
                    }
        },
        "filter_fields": {
                    "assets": {
                                "AssetTagNo": "Unique identification tag assigned to the specific equipment",
                                "EquipmentName": "Name or type description of the equipment",
                                "StatusName": "Current operational status of the asset (e.g. Online, Offline)",
                                "ConditionName": "Physical state or condition of the equipment (e.g. Good)",
                                "PriorityName": "Priority level assigned to the asset (e.g. P2 High)",
                                "LocalityName": "Geographic locality or area for location summary",
                                "BuildingName": "Building facility name where the asset is located",
                                "FloorName": "Floor level inside the building",
                                "SpotName": "Specific zone or room location",
                                "MakeName": "Brand or manufacturer name",
                                "ModelName": "Model identification sequence",
                                "InstalledDate": "The historical installation date of the asset"
                    },
                    "bdm": {
                                "ComplaintNo": "Breakdown or corrective repair request ticket identifier",
                                "ComplaintModeName": "How the breakdown repair request was reported",
                                "PriorityName": "Urgency or priority level of the repair request",
                                "ComplaintNatureName": "The documented nature of the breakdown failure",
                                "Description": "Detailed technician notes regarding the actions taken",
                                "ExecutionTechName": "The technician or person responsible for executing the repair",
                                "AnalysisTechName": "The technician responsible for analyzing the breakdown",
                                "ComplainedDateTime": "Timestamp when the breakdown issue was reported",
                                "BDMWOCompletedDate": "Timestamp when the breakdown fix was completed",
                                "ResponseTAT": "Turnaround time status indicating if response met or exceeded SLA",
                                "ResolutionTAT": "Turnaround time status indicating if resolution met or exceeded SLA",
                                "WoStatus": "Current active status tracking the progress of the work order",
                                "ComplaintTypeName": "Classification of the type of work",
                                "LocalityName": "Geographic locality linked to the breakdown tracking"
                    },
                    "fa": {
                                "RMComplaintNo": "Facility audit inspection ticket identifier",
                                "RMRequestDetailsDesc": "Description text detailing the specific audit or inspection request",
                                "RMTechnicalFindings": "Documented findings or observations discovered during the inspection",
                                "RMTechName": "The designated technician or auditor responsible for the activity",
                                "RMComplainedDateTime": "System date when the inspection request was raised",
                                "RMBDMWOCompletedDate": "Completion date and time details for the inspection activity",
                                "RMOverDueTime": "Tracked metric indicating if the audit activity exceeded its timeline",
                                "RMStageName": "Current operational execution status of the audit workflow",
                                "FrequencyName": "The facility audit maintenance cycle interval",
                                "RMCategoryName": "The type of audit work performed",
                                "LocalityName": "Geographic area under inspection"
                    },
                    "ppm": {
                                "WorkOrder": "Scheduled preventive maintenance task number",
                                "PPMStatus": "Overall completion status of the maintenance task (e.g. Open)",
                                "PPMStageName": "Detailed workflow progress stage description",
                                "FrequencyName": "The maintenance type cycle recurrence interval (e.g. QUARTERLY)",
                                "WoDateTime": "Planned or initial system date for the scheduled activity",
                                "WoCompletedDate": "Date when the preventive maintenance activity was finalized",
                                "PMTechName": "The technician or team member assigned to the task",
                                "DivisionName": "The responsible team or service division handling the PPM",
                                "LocalityName": "Geographic area of the scheduled maintenance task"
                    },
                    "sb": {
                                "SBCreWorkOrder": "Service book generated schedule order key",
                                "SBCreWoDateTime": "System generation date for the scheduled service book task",
                                "SBCreWoCompletedDate": "Completion date tracking for the service book activity",
                                "SBTechName": "The technician or crew member assigned to the scheduled service book task",
                                "PPMStageName": "The workflow phase tracking current task progress",
                                "FrequencyName": "The service book maintenance cycle recurrence pattern",
                                "ServiceTypeName": "Type of service book activity performed",
                                "ContractName": "Name of the service provider contract agreement",
                                "LocalityName": "Geographic location sector under the contract schedule"
                    }
        }
    }
}
