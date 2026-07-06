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
        "question": "Where are our critical infrastructure assets suffering the highest downtime?",
        "modules": ["assets", "bdm"],
        "filter_fields": {
            "assets": {
                "StatusName":   "Operational status of the asset (e.g. Offline, Online)",
                "BuildingName":  "Name of the building where the asset is located",
                "LocalityName":  "Geographic locality or area",
                "PriorityName":  "Priority level of the asset (e.g. P2 High)",
                "AssetTagNo":    "Unique asset tag identifier",
                "DivisionName":  "Service division responsible for the asset",
                "EquipmentName": "Name or type of the equipment",
            },
            "bdm": {
                "AnalysisStartTime": "Time when reactive breakdown analysis was started",
                "AnalysisEndTime":   "Time when reactive breakdown analysis was completed",
                "BuildingName":      "Name of the building linked to the complaint",
                "LocalityName":      "Geographic locality of the complaint",
                "WoStatus":          "Current status of the work order (Open / Closed)",
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Q2": {
        "id": "Q2",
        "question": "What is the current preventive maintenance backlog risk for high-priority sites?",
        "modules": ["ppm"],
        "filter_fields": {
            "ppm": {
                "PPMStatus":        "Current status of the planned preventive maintenance (Open / Closed)",
                "BuildingName":     "Name of the building where the PPM is scheduled",
                "LocalityName":     "Geographic locality or area",
                "EquipmentName":    "Type or name of the equipment under maintenance",
                "DivisionName":     "Service division handling the maintenance task",
                "WorkOrder":        "Unique PPM work order number",
                "PPMPendingPeriod": "Number of days the PPM task has been pending or overdue",
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Q3": {
        "id": "Q3",
        "question": "Are structural cleanliness issues directly predicting spikes in reactive repairs?",
        "modules": ["fa", "bdm"],
        "filter_fields": {
            "fa": {
                "RMCategorySubName": "Sub-category of the remedial/audit issue (e.g. Rodent, Washroom, Cockroach, Floor)",
                "RMCategoryName":    "Main category of the facility audit or remedial check",
                "BuildingName":      "Name of the building where the audit issue was found",
                "LocalityName":      "Geographic locality or area",
                "RMComplaintNo":     "Unique remedial maintenance complaint number",
            },
            "bdm": {
                "BuildingName": "Name of the building where the breakdown was raised",
                "LocalityName": "Geographic locality of the complaint",
                "WoStatus":     "Current status of the work order (Open / Closed)",
                "DivisionName": "Service division handling the reactive repair",
                "ComplaintNo":  "Unique complaint or work order number",
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Q4": {
        "id": "Q4",
        "question": "Which equipment types are consistently breaching their SLA resolution windows?",
        "modules": ["bdm"],
        "filter_fields": {
            "bdm": {
                "WoStatus":     "Current status of the work order (Open / Closed)",
                "DivisionName": "Service division / equipment type associated with the complaint",
                "ResponseTAT": "Response turnaround indicator (e.g. ROT = on time, SNA = staff not assigned)",
                "ResolutionTAT": "Resolution turnaround indicator showing if SLA window was met or breached",
                "ComplaintNo":  "Unique complaint or work order number",
                "BuildingName": "Name of the building where the complaint was raised",
                "LocalityName": "Geographic locality of the complaint",
                "PriorityName": "Priority level of the work order",
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Q5": {
        "id": "Q5",
        "question": "What percentage of closed work orders suffer from critical data compliance gaps?",
        "modules": ["bdm", "ppm"],
        "filter_fields": {
            "bdm": {
                "WoStatus":          "Current status of the work order — filter for Closed records",
                "ExecutionTechName": "Technician who executed the work — blank value indicates a compliance gap",
                "AnalysisTechName":  "Technician assigned to analyse the complaint",
                "ComplaintNo":       "Unique complaint or work order number",
                "BuildingName":      "Name of the building linked to the complaint",
                "LocalityName":      "Geographic locality of the complaint",
            },
            "ppm": {
                "PPMStatus":  "Current status of the PPM work order — filter for Closed records",
                "PMTechName": "Technician assigned to the PPM task — blank value indicates a compliance gap",
                "WorkOrder":  "Unique PPM work order number",
                "BuildingName": "Name of the building for the PPM task",
                "LocalityName": "Geographic locality or area",
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Q6": {
        "id": "Q6",
        "question": "How much preventive work is still pending versus completed?",
        "modules": ["ppm"],
        "filter_fields": {
            "ppm": {
                "PPMStatus":        "Current status of the PPM work order (Open = pending, Closed = completed)",
                "WoCompletedDate":  "Date the work order was completed — blank means still pending",
                "WoDateTime":       "Scheduled date of the PPM work order",
                "WorkOrder":        "Unique PPM work order number",
                "BuildingName":     "Name of the building where the PPM is scheduled",
                "LocalityName":     "Geographic locality or area",
                "EquipmentName":    "Type or name of the equipment under maintenance",
                "PPMPendingPeriod": "Number of days the PPM task has been pending or overdue",
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Q7": {
        "id": "Q7",
        "question": "Where are we seeing repeated breakdown issues piling up?",
        "modules": ["bdm"],
        "filter_fields": {
            "bdm": {
                "ComplaintNatureName": "Nature or description of the complaint",
                "DivisionName":        "Service division responsible for the breakdown",
                "WoStatus":            "Current status of the work order",
                "BuildingName":        "Name of the building where breakdown occurred",
                "LocalityName":        "Geographic locality or area",
                "ComplaintNo":         "Unique complaint or work order number",
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Q8": {
        "id": "Q8",
        "question": "Is any contractor sitting on a high backlog of unresolved work?",
        "modules": ["bdm", "ppm"],
        "filter_fields": {
            "bdm": {
                "ContractName": "Name of the contract or contractor responsible",
                "WoStatus":     "Current status of the work order",
                "ComplaintNo":  "Unique complaint or work order number",
                "BuildingName": "Name of the building",
                "LocalityName": "Geographic locality or area",
            },
            "ppm": {
                "ContractName": "Name of the contract or contractor responsible",
                "PPMStatus":    "Current status of the planned maintenance",
                "WorkOrder":    "Unique PPM work order number",
                "BuildingName": "Name of the building",
                "LocalityName": "Geographic locality or area",
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Q9": {
        "id": "Q9",
        "question": "Which technicians are carrying the heaviest workload right now?",
        "modules": ["bdm", "ppm"],
        "filter_fields": {
            "bdm": {
                "AnalysisTechName":  "Technician assigned to analyse the complaint",
                "ExecutionTechName": "Technician assigned to execute the work",
                "WoStatus":          "Current status of the work order",
                "ComplaintNo":       "Unique complaint or work order number",
                "BuildingName":      "Name of the building",
                "PriorityName":      "Priority level of the work order",
            },
            "ppm": {
                "PMTechName":    "Technician assigned to the planned maintenance task",
                "PPMStatus":     "Current status of the planned maintenance",
                "WorkOrder":     "Unique PPM work order number",
                "BuildingName":  "Name of the building",
                "EquipmentName": "Type or name of the equipment under maintenance",
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Q10": {
        "id": "Q10",
        "question": "Which contracts need urgent attention?",
        "modules": ["bdm", "fa"],
        "filter_fields": {
            "bdm": {
                "ContractName":  "Name of the contract or contractor responsible",
                "WoStatus":      "Current status of the work order",
                "ResponseTAT":   "Response turnaround status — SNA means Staff Not Assigned (no action taken)",
                "ComplaintNo":   "Unique complaint or work order number",
                "PriorityName":  "Priority level of the work order",
                "BuildingName":  "Name of the building",
            },
            "fa": {
                "ContractName":  "Name of the contract or contractor responsible",
                "RMStageName":   "Current stage of the remedial/audit activity",
                "RMComplaintNo": "Unique audit or remedial complaint number",
                "PriorityName":  "Priority level",
                "BuildingName":  "Name of the building",
                "LocalityName":  "Geographic locality or area",
            },
        },
    },

}

