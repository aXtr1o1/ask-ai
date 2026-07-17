"""
Understanding Agent — Module Fields Registry

Purpose:
    Provides a lightweight map of every FM module to its field names.
    NO descriptions, NO enum values — just the field names.

Why:
    The Understanding Agent only needs to know what fields exist per module
    so it can decide which modules are relevant to the user's query.
    Keeping this small avoids wasting tokens on schema descriptions that
    are only needed by the Analysis Agent.

Used by:
    prompt.py  →  injected into the Understanding Agent system prompt
"""

# =============================================================================
# MODULE_FIELDS
# Key   : module name (must match keys in analysis/metadata/)
# Value : list of field names that exist in that module
# =============================================================================
MODULE_FIELDS: dict[str, list[str]] = {

    # Physical Asset Register
    # Tracks every physical asset / equipment installed in the facility.
    "assets": [
        "AssetTagNo", "AssetBarcode", "EquipmentName", "EquipmentRefNo", "SerialNo",
        "StatusName", "ConditionName", "PriorityName", "AssetTypeName",
        "DivisionName", "DisciplineName",
        "LocalityName", "BuildingName", "FloorName", "SpotName",
        "MakeName", "ModelName", "Owner", "ServiceArea", "TradeGroup",
        "DrawingNo", "Remarks",
        "OnHold", "IsSnagged", "IsScraped", "EnablePPM", "EnableBDM",
        "EnableBMS", "EnableDSM",
    ],

    # Breakdown / Reactive Maintenance (Complaints)
    # Tracks reactive work orders raised when equipment fails or a user complains.
    "bdm": [
        "ComplaintNo", "AssetTagNo", "AssetBarcode", "ClientWoNo",
        "WoStatus", "PriorityName", "StageName", "ComplaintTypeName",
        "ComplaintModeName", "ComplaintNatureName", "ServiceTypeName",
        "WoType", "ContractName",
        "AnalysisTechName", "ExecutionTechName", "Complainer", "RegisterBy",
        "LocalityName", "BuildingName", "FloorName", "SpotName",
        "DivisionName", "DisciplineName",
        "ComplainedDateTime", "AnalysisStartTime", "AnalysisEndTime",
        "ExecutionStartTime", "ExecutionEndTime", "BDMWOCompletedDate",
        "ResponseTAT", "ResolutionTAT",
    ],

    # Planned Preventive Maintenance
    # Tracks scheduled routine maintenance tasks for registered assets.
    "ppm": [
        "WorkOrder", "AssetTagNo", "EquipmentRefNo",
        "PPMStatus", "PPMStageName", "FrequencyName",
        "DivisionName", "DisciplineName", "ContractName", "EquipmentName",
        "LocalityCode", "LocalityName", "BuildingName", "FloorName", "SpotName",
        "PMTechName",
        "WoDateTime", "WoCompletedDate", "PMTechStartDateTime", "PMTechEndDateTime",
        "PMTechRemarks",
        "PPMPendingPeriod", "SLADuration",
    ],

    # Facility Audits & Remedial (Snags / Inspections)
    # Tracks audit tasks, inspections, and remedial snags from physical walkthroughs.
    "fa": [
        "RMComplaintNo",
        "RMStageName", "PriorityName", "RMCategoryName", "RMCategorySubName",
        "RMRequestDetailsDesc", "FrequencyName", "DivisionName", "ContractName",
        "RMTechName",
        "LocalityName", "BuildingName", "FloorName", "SpotName",
        "RMComplainedDateTime", "RMTeStartDateTime", "RMTeEndDateTime",
        "RMBDMWOCompletedDate",
        "RMMaintenanceHrs",
    ],

    # Schedule Booking (Housekeeping / Cleanliness Inspections)
    # Tracks pre-scheduled service bookings and cleanliness inspection tasks.
    "sb": [
        "SBRequestNo",
        "SBStatus", "SBStageName", "SBTypeName", "PriorityName",
        "ServiceTypeName", "DivisionName", "ContractName",
        "RequestedBy", "TechName",
        "LocalityName", "BuildingName", "FloorName", "SpotName",
        "BookedDateTime", "ScheduledDateTime", "CompletedDateTime",
        "Remarks",
    ],
}
