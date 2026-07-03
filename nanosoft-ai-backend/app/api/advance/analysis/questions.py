"""
Analysis — Question Definitions
Each question declares:
  - which modules (data sources) to load
  - filter_fields: { filter_key → actual column name in the JSON data }
No routes, no mock data here.
"""

QUESTIONS: dict = {
    "Q1": {
        "id": "Q1",
        "question": "Generate a Building Performance Report.",
        "modules": ["bdm", "ppm", "fa", "assets"],
        "filter_fields": {
            "bdm": {
                "building": "BuildingName",
                "locality": "LocalityName",
                "division": "DivisionName",
                "priority": "PriorityName",
                "status": "WoStatus",
                "complaints": "ComplaintNo",
            },
            "ppm": {
                "building": "BuildingName",
                "locality": "LocalityName",
                "division": "DivisionName",
                "status": "PPMStatus",
                "work_order": "WorkOrder",
            },
            "fa": {
                "building": "BuildingName",
                "locality": "LocalityName",
                "division": "DivisionName",
                "priority": "PriorityName",
                "status": "RMStageName",
                "audit": "RMComplaintNo",
                "maintenance_hours": "RMMaintenanceHrs",
            },
            "assets": {
                "building": "BuildingName",
                "locality": "LocalityName",
                "division": "DivisionName",
                "priority": "PriorityName",
                "status": "StatusName",
                "condition": "ConditionName",
                "tag": "AssetTagNo",
            }
        },
    },
    "Q2": {
        "id": "Q2",
        "question": "Why has maintenance cost increased this quarter?",
        "modules": ["bdm", "ppm", "assets"],
        "filter_fields": {
            "bdm": {
                "building": "BuildingName",
                "locality": "LocalityName",
                "division": "DivisionName",
                "priority": "PriorityName",
                "status": "WoStatus",
                "complaints": "ComplaintNo",
                "date": "ComplainedDateTime",
            },
            "ppm": {
                "building": "BuildingName",
                "locality": "LocalityName",
                "division": "DivisionName",
                "status": "PPMStatus",
                "work_order": "WorkOrder",
                "date": "WoDateTime",
            },
            "assets": {
                "building": "BuildingName",
                "locality": "LocalityName",
                "division": "DivisionName",
                "priority": "PriorityName",
                "status": "StatusName",
                "condition": "ConditionName",
                "tag": "AssetTagNo",
            }
        },
    },
    "Q3": {
        "id": "Q3",
        "question": "Which technicians are carrying the heaviest workload right now?",
        "modules": ["bdm", "ppm"],
        "filter_fields": {
            "bdm": {
                "building": "BuildingName",
                "locality": "LocalityName",
                "division": "DivisionName",
                "priority": "PriorityName",
                "status": "WoStatus",
                "complaints": "ComplaintNo",
                "tech_analysis": "AnalysisTechName",
                "tech_execution": "ExecutionTechName",
            },
            "ppm": {
                "building": "BuildingName",
                "locality": "LocalityName",
                "division": "DivisionName",
                "status": "PPMStatus",
                "work_order": "WorkOrder",
                "tech": "PMTechName",
            }
        },
    },
    "Q4": {
        "id": "Q4",
        "question": "Which equipment is approaching the end of its useful life?",
        "modules": ["assets"],
        "filter_fields": {
            "assets": {
                "equipment_name": "EquipmentName",
                "building": "BuildingName",
                "locality": "LocalityName",
                "division": "DivisionName",
                "priority": "PriorityName",
                "status": "StatusName",
                "condition": "ConditionName",
                "tag": "AssetTagNo",
                "make": "MakeName",
                "model": "ModelName",
                "floor": "FloorName",
                "spot": "SpotName",
            }
        },
    },
    "Q5": {
        "id": "Q5",
        "question": "How many routine checks are overdue right now?",
        "modules": ["ppm"],
        "filter_fields": {
            "ppm": {
                "building": "BuildingName",
                "locality": "LocalityName",
                "division": "DivisionName",
                "equipment_name": "EquipmentName",
                "status": "PPMStatus",
                "work_order": "WorkOrder",
                "date": "WoDateTime",
                "pending_period": "PPMPendingPeriod",
            }
        },
    },
}

