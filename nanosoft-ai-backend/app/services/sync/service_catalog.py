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
            "asset", "equipment", "barcode", "scrap", "installed",
            "model", "make", "condition", "snagged", "on hold",
        ],
        "fields_config": {
            "OnHold":         {"type": "boolean", "is_date": False, "description": "", "aggregatable": False},
            "PurDate":        {"type": "date",    "is_date": True,  "description": "", "aggregatable": False},
            "MakeName":       {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "PurValue":       {"type": "string",  "is_date": False, "description": "", "aggregatable": False},
            "SpotName":       {"type": "string",  "is_date": False, "description": "", "aggregatable": False},
            "FloorName":      {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "IsScraped":      {"type": "boolean", "is_date": False, "description": "", "aggregatable": False},
            "IsSnagged":      {"type": "boolean", "is_date": False, "description": "", "aggregatable": False},
            "ModelName":      {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "ScrapDate":      {"type": "date",    "is_date": True,  "description": "", "aggregatable": False},
            "AssetTagNo":     {"type": "string",  "is_date": False, "description": "", "aggregatable": False},
            "LifeInYear":     {"type": "integer", "is_date": False, "description": "", "aggregatable": False},
            "ScrapValue":     {"type": "string",  "is_date": False, "description": "", "aggregatable": False},
            "StatusName":     {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "IsEnableBDM":    {"type": "boolean", "is_date": False, "description": "", "aggregatable": False},
            "IsEnableBMS":    {"type": "boolean", "is_date": False, "description": "", "aggregatable": False},
            "IsEnableDSM":    {"type": "boolean", "is_date": False, "description": "", "aggregatable": False},
            "IsEnablePPM":    {"type": "boolean", "is_date": False, "description": "", "aggregatable": False},
            "YearOfManuf":    {"type": "integer", "is_date": False, "description": "", "aggregatable": True },
            "AssetBarcode":   {"type": "string",  "is_date": False, "description": "", "aggregatable": False},
            "BuildingName":   {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "DivisionName":   {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "LocalityName":   {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "PriorityName":   {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "ConditionName":  {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "EquipmentName":  {"type": "string",  "is_date": False, "description": "", "aggregatable": False},
            "InstalledDate":  {"type": "date",    "is_date": True,  "description": "", "aggregatable": False},
            "DisciplineName": {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
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
            "ppm", "planned", "preventive", "maintenance", "work order",
            "schedule", "quarterly", "frequency", "open", "closed",
            "sla", "fire extinguisher", "technician",
        ],
        "fields_config": {
            "SpotName":           {"type": "string",  "is_date": False, "description": "", "aggregatable": False},
            "FloorName":          {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "PPMStatus":          {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "WorkOrder":          {"type": "string",  "is_date": False, "description": "", "aggregatable": False},
            "AssetTagNo":         {"type": "string",  "is_date": False, "description": "", "aggregatable": False},
            "PMTechName":         {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "WoDateTime":         {"type": "date",    "is_date": True,  "description": "", "aggregatable": False},
            "SLADuration":        {"type": "integer", "is_date": False, "description": "", "aggregatable": False},
            "BuildingName":       {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "ContractName":       {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "DivisionName":       {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "LocalityName":       {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "PPMStageName":       {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "EquipmentName":      {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "FrequencyName":      {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "DisciplineName":     {"type": "string",  "is_date": False, "description": "", "aggregatable": True },
            "WoCompletedDate":    {"type": "date",    "is_date": True,  "description": "", "aggregatable": False},
            "PPMPendingPeriod":   {"type": "integer", "is_date": False, "description": "", "aggregatable": False},
            "PMTechEndDateTime":  {"type": "date",    "is_date": True,  "description": "", "aggregatable": False},
            "PMTechStartDateTime":{"type": "date",    "is_date": True,  "description": "", "aggregatable": False},
        },
    },

    # ── BDM ───────────────────────────────────────────────────────────────────
    {
        "service_key":      "complaints",
        "service_name":     "Complaint & BDM Work Orders",
        "description":      "Tracks corrective maintenance complaints and breakdown work orders.",
        "endpoint":         "/getBDM",
        "unique_field":     "ComplaintNo",
        "routing_keywords": [
            "complaint", "bdm", "breakdown", "corrective", "maintenance",
            "work order", "closed", "open", "technician", "sla",
            "priority", "ac", "noisy", "fault",
        ],
        "fields_config": {
            "SpotName":             {"type": "string", "is_date": False, "description": "", "aggregatable": False},
            "WoStatus":             {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "FloorName":            {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "StageName":            {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "AssetTagNo":           {"type": "string", "is_date": False, "description": "", "aggregatable": False},
            "RegisterBy":           {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "WoTypeName":           {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "ComplaintNo":          {"type": "string", "is_date": False, "description": "", "aggregatable": False},
            "ResponseTAT":          {"type": "string", "is_date": False, "description": "", "aggregatable": False},
            "AssetBarcode":         {"type": "string", "is_date": False, "description": "", "aggregatable": False},
            "BuildingName":         {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "ContractName":         {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "DivisionName":         {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "LocalityName":         {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "PriorityName":         {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "ResolutionTAT":        {"type": "string", "is_date": False, "description": "", "aggregatable": False},
            "ComplainerName":       {"type": "string", "is_date": False, "description": "", "aggregatable": False},
            "DisciplineName":       {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "AnalysisEndTime":      {"type": "date",   "is_date": True,  "description": "", "aggregatable": False},
            "ServiceTypeName":      {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "AnalysisTechName":     {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "ExecutionEndTime":     {"type": "date",   "is_date": True,  "description": "", "aggregatable": False},
            "AnalysisStartTime":    {"type": "date",   "is_date": True,  "description": "", "aggregatable": False},
            "ComplaintModeName":    {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "ComplaintTypeName":    {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "ExecutionTechName":    {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "SLABDMEndDateTime":    {"type": "date",   "is_date": True,  "description": "", "aggregatable": False},
            "SLACCMEndDateTime":    {"type": "date",   "is_date": True,  "description": "", "aggregatable": False},
            "BDMWOCompletedDate":   {"type": "date",   "is_date": True,  "description": "", "aggregatable": False},
            "ComplainedDateTime":   {"type": "date",   "is_date": True,  "description": "", "aggregatable": False},
            "ExecutionStartTime":   {"type": "date",   "is_date": True,  "description": "", "aggregatable": False},
            "ComplaintNatureName":  {"type": "string", "is_date": False, "description": "", "aggregatable": True },
            "SLABDMStartDateTime":  {"type": "date",   "is_date": True,  "description": "", "aggregatable": False},
            "SLACCMStartDateTime":  {"type": "date",   "is_date": True,  "description": "", "aggregatable": False},
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