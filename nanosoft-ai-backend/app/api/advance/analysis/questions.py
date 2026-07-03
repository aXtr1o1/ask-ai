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
        "question": "Is our response speed holding steady or getting worse over time?",
        "modules": ["bdm"],
        "filter_fields": {
            "date_from":            "ComplainedDateTime",
            "date_to":              "ComplainedDateTime",
            "analysis_start_time": "AnalysisStartTime",
            "locality":            "LocalityName",
            "building":            "BuildingName",
            "division":            "DivisionName",
            "priority":            "PriorityName",
            "status":              "WoStatus",
        },
    },
    "Q2": {
        "id": "Q2",
        "question": "Where are we seeing repeated breakdown issues piling up?",
        "modules": ["bdm", "assets", "ppm"],
        "filter_fields": {
            "division":         "DivisionName",
            "locality":         "LocalityName",
            "building":         "BuildingName",
            "priority":         "PriorityName",
            "equipment_name":   "EquipmentName",
            "nature":           "ComplaintNatureName",
        },
    },
}
