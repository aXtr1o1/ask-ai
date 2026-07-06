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

    # ─────────────────────────────────────────────────────────────────────────
    "Q1": {
        "id": "Q1",
        "question": "Generate a Building Performance Report.",
        "modules": ["bdm", "ppm", "fa", "assets"],
        "filter_fields": {
            "bdm": {
                "BuildingName":  "Name of the building",
                "LocalityName":  "Geographic locality or area",
                "DivisionName":  "Service division handling the work order",
                "PriorityName":  "Priority level of the work order",
                "WoStatus":      "Current status of the work order",
                "ComplaintNo":   "Unique complaint or work order number",
            },
            "ppm": {
                "BuildingName":  "Name of the building",
                "LocalityName":  "Geographic locality or area",
                "DivisionName":  "Service division handling the planned maintenance",
                "PPMStatus":     "Current status of the planned preventive maintenance",
                "WorkOrder":     "Unique PPM work order number",
            },
            "fa": {
                "BuildingName":     "Name of the building",
                "LocalityName":     "Geographic locality or area",
                "DivisionName":     "Service division",
                "PriorityName":     "Priority level",
                "RMStageName":      "Current stage of the remedial maintenance",
                "RMComplaintNo":    "Remedial maintenance complaint number",
                "RMMaintenanceHrs": "Hours spent on remedial maintenance",
            },
            "assets": {
                "BuildingName":  "Name of the building",
                "LocalityName":  "Geographic locality or area",
                "DivisionName":  "Service division",
                "PriorityName":  "Priority level of the asset",
                "StatusName":    "Current operational status of the asset",
                "ConditionName": "Physical condition of the asset",
                "AssetTagNo":    "Unique asset tag identifier",
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Q2": {
        "id": "Q2",
        "question": "Why has maintenance cost increased this quarter?",
        "modules": ["bdm", "ppm", "assets"],
        "filter_fields": {
            "bdm": {
                "BuildingName":        "Name of the building",
                "LocalityName":        "Geographic locality or area",
                "DivisionName":        "Service division",
                "PriorityName":        "Priority level of the work order",
                "WoStatus":            "Current status of the work order",
                "ComplaintNo":         "Unique complaint or work order number",
                "ComplainedDateTime":  "Date and time the complaint was raised",
            },
            "ppm": {
                "BuildingName":  "Name of the building",
                "LocalityName":  "Geographic locality or area",
                "DivisionName":  "Service division",
                "PPMStatus":     "Current status of the planned maintenance",
                "WorkOrder":     "Unique PPM work order number",
                "WoDateTime":    "Date and time the PPM work order was created",
            },
            "assets": {
                "BuildingName":  "Name of the building",
                "LocalityName":  "Geographic locality or area",
                "DivisionName":  "Service division",
                "PriorityName":  "Priority level of the asset",
                "StatusName":    "Current operational status of the asset",
                "ConditionName": "Physical condition of the asset",
                "AssetTagNo":    "Unique asset tag identifier",
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Q3": {
        "id": "Q3",
        "question": "Which technicians are carrying the heaviest workload right now?",
        "modules": ["bdm", "ppm"],
        "filter_fields": {
            "bdm": {
                "BuildingName":      "Name of the building",
                "LocalityName":      "Geographic locality or area",
                "DivisionName":      "Service division",
                "PriorityName":      "Priority level",
                "WoStatus":          "Current status of the work order",
                "ComplaintNo":       "Unique complaint or work order number",
                "AnalysisTechName":  "Technician assigned to analyse the complaint",
                "ExecutionTechName": "Technician assigned to execute the work",
            },
            "ppm": {
                "BuildingName":  "Name of the building",
                "LocalityName":  "Geographic locality or area",
                "DivisionName":  "Service division",
                "PPMStatus":     "Current status of the planned maintenance",
                "WorkOrder":     "Unique PPM work order number",
                "PMTechName":    "Technician assigned to the planned maintenance task",
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Q4": {
        "id": "Q4",
        "question": "Which equipment is approaching the end of its useful life?",
        "modules": ["assets"],
        "filter_fields": {
            "assets": {
                "EquipmentName": "Type or name of the equipment",
                "BuildingName":  "Name of the building",
                "LocalityName":  "Geographic locality or area",
                "DivisionName":  "Service division",
                "PriorityName":  "Priority level of the asset",
                "StatusName":    "Current operational status of the asset",
                "ConditionName": "Physical condition rating of the asset",
                "AssetTagNo":    "Unique asset tag identifier",
                "MakeName":      "Manufacturer or make of the equipment",
                "ModelName":     "Model name of the equipment",
                "FloorName":     "Floor where the asset is located",
                "SpotName":      "Specific spot or location of the asset on that floor",
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Q5": {
        "id": "Q5",
        "question": "How many routine checks are overdue right now?",
        "modules": ["ppm"],
        "filter_fields": {
            "ppm": {
                "BuildingName":     "Name of the building",
                "LocalityName":     "Geographic locality or area",
                "DivisionName":     "Service division",
                "EquipmentName":    "Type or name of the equipment",
                "PPMStatus":        "Current status of the planned maintenance",
                "WorkOrder":        "Unique PPM work order number",
                "WoDateTime":       "Date and time the PPM work order was created",
                "PPMPendingPeriod": "Number of days the PPM task has been pending or overdue",
            },
        },
    },

}
