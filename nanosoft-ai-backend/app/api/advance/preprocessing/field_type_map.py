"""
Preprocessing — Field Type Map

Registry: module → { column_name → type_tag }

Type tags:
    "text"        — string field, strip whitespace, None → ""
    "bool"        — boolean field, normalise to Python bool
    "int"         — integer field, None/empty → None
    "bigint"      — same as int (DB bigint → Python int)
    "float"       — numeric field (DB numeric/decimal), None/empty → None
    "numeric_str" — money/value stored as text (e.g. "25000.00") → float
    "datetime"    — date/datetime string → "YYYY-MM-DD HH:MM:SS" or None

Coverage: all columns from DB schema provided 2026-07-29
Tables:   Asset · bdm · ppm · FacilityAudit · ScheduleBased

Adding a new module:
    1. Add a new key with the module name (must match retrieval module key)
    2. List every column the stored procedure returns, with its type_tag
    3. The preprocessor will auto-pick it up — no other file changes needed
"""

# fmt: off
FIELD_TYPE_MAP: dict[str, dict[str, str]] = {

    # =========================================================================
    # ASSETS  —  Physical Asset Register
    # Tracks every physical asset / equipment installed in the facility.
    # DB table: Asset
    # Total fields: 38
    # =========================================================================
    "assets": {
        # ── Identifiers ───────────────────────────────────────────────────────
        "AssetTagNo":       "text",
        "AssetBarcode":     "text",
        "EquipmentRefNo":   "text",
        "SerialNo":         "text",

        # ── Descriptive ───────────────────────────────────────────────────────
        "EquipmentName":    "text",
        "AssetTypeName":    "text",
        "DivisionName":     "text",
        "DisciplineName":   "text",
        "Owner":            "text",
        "MakeName":         "text",
        "ModelName":        "text",
        "ServiceAreaName":  "text",
        "TradeGroupName":   "text",
        "DrawingNo":        "text",
        "Remarks":          "text",

        # ── Status / Classification ───────────────────────────────────────────
        "StatusName":       "text",
        "ConditionName":    "text",
        "PriorityName":     "text",

        # ── Location ──────────────────────────────────────────────────────────
        "LocalityName":     "text",
        "BuildingName":     "text",
        "FloorName":        "text",
        "SpotName":         "text",
        "Longitude":        "text",   # stored as text in DB
        "Latitude":         "text",   # stored as text in DB

        # ── Flags (boolean) ───────────────────────────────────────────────────
        "OnHold":           "bool",
        "IsSnagged":        "bool",
        "IsScraped":        "bool",
        "IsEnablePPM":      "bool",
        "IsEnableBDM":      "bool",
        "IsEnableBMS":      "bool",
        "IsEnableDSM":      "bool",

        # ── Numeric ───────────────────────────────────────────────────────────
        "YearOfManuf":      "int",         # integer in DB
        "LifeInYear":       "int",         # integer in DB

        # ── Money (stored as text in DB, convert to float) ────────────────────
        "PurValue":         "numeric_str",
        "ScrapValue":       "numeric_str",

        # ── Dates ─────────────────────────────────────────────────────────────
        "PurDate":          "datetime",
        "InstalledDate":    "datetime",
        "ScrapDate":        "datetime",
    },

    # =========================================================================
    # BDM  —  Breakdown / Reactive Maintenance (Complaints)
    # Tracks reactive work orders raised when equipment fails or user complains.
    # DB table: bdm
    # Total fields: 39
    # =========================================================================
    "bdm": {
        # ── Identifiers ───────────────────────────────────────────────────────
        "ComplaintNo":          "text",
        "AssetTagNo":           "text",
        "AssetBarcode":         "text",
        "ClientWoNo":           "text",

        # ── Status / Classification ───────────────────────────────────────────
        "WoStatus":             "text",
        "PriorityName":         "text",
        "StageName":            "text",
        "ComplaintTypeName":    "text",
        "ComplaintHeaderName":  "text",
        "ComplaintModeName":    "text",
        "ComplaintNatureName":  "text",
        "WoTypeName":           "text",
        "ServiceTypeName":      "text",

        # ── Location ──────────────────────────────────────────────────────────
        "LocalityName":         "text",
        "LocalityCode":         "text",
        "BuildingName":         "text",
        "FloorName":            "text",
        "SpotName":             "text",

        # ── Organisation ──────────────────────────────────────────────────────
        "DivisionName":         "text",
        "DisciplineName":       "text",
        "ContractName":         "text",

        # ── People ────────────────────────────────────────────────────────────
        "ComplainerName":       "text",
        "RegisterBy":           "text",
        "AnalysisTechName":     "text",
        "ExecutionTechName":    "text",

        # ── Descriptive ───────────────────────────────────────────────────────
        "Description":          "text",
        "ResponseTAT":          "text",
        "ResolutionTAT":        "text",
        "StandByRemarks":       "text",

        # ── Datetime fields ───────────────────────────────────────────────────
        "ComplainedDateTime":   "datetime",
        "BDMWOCompletedDate":   "datetime",
        "SLACCMStartDateTime":  "datetime",
        "SLACCMEndDateTime":    "datetime",
        "SLABDMStartDateTime":  "datetime",
        "SLABDMEndDateTime":    "datetime",
        "AnalysisStartTime":    "datetime",
        "AnalysisEndTime":      "datetime",
        "ExecutionStartTime":   "datetime",
        "ExecutionEndTime":     "datetime",
    },

    # =========================================================================
    # PPM  —  Planned Preventive Maintenance
    # Tracks scheduled routine maintenance tasks for registered assets.
    # DB table: ppm
    # Total fields: 24
    # =========================================================================
    "ppm": {
        # ── Identifiers ───────────────────────────────────────────────────────
        "WorkOrder":            "text",
        "AssetTagNo":           "text",
        "EquipmentRefNo":       "text",

        # ── Status / Classification ───────────────────────────────────────────
        "PPMStatus":            "text",
        "PPMStageName":         "text",
        "FrequencyName":        "text",

        # ── Location ──────────────────────────────────────────────────────────
        "LocalityName":         "text",
        "LocalityCode":         "text",
        "BuildingName":         "text",
        "FloorName":            "text",
        "SpotName":             "text",

        # ── Asset / Equipment ─────────────────────────────────────────────────
        "EquipmentName":        "text",

        # ── Organisation ──────────────────────────────────────────────────────
        "DivisionName":         "text",
        "DisciplineName":       "text",
        "ContractName":         "text",

        # ── Technician ────────────────────────────────────────────────────────
        "PMTechName":           "text",
        "PMTechRemarks":        "text",
        "LastStandByRemarks":   "text",
        "PPMPendingPeriod":     "text",

        # ── Datetime fields ───────────────────────────────────────────────────
        "WoDateTime":           "datetime",
        "WoCompletedDate":      "datetime",
        "PMTechStartDateTime":  "datetime",
        "PMTechEndDateTime":    "datetime",

        # ── Numeric ───────────────────────────────────────────────────────────
        "SLADuration":          "int",    # integer in DB, default 0
    },

    # =========================================================================
    # FA  —  Facility Audit & Remedial (Snags / Inspections)
    # Tracks audit tasks, inspections, and remedial snags from walkthroughs.
    # DB table: FacilityAudit
    # Total fields: 58
    # =========================================================================
    "fa": {
        # ── Identifiers ───────────────────────────────────────────────────────
        "RMCCMComplaintIDPK":       "bigint",  # primary key reference
        "RMCCMComplaintCode":       "text",
        "RMComplaintNo":            "text",
        "RMXComplaintNo":           "text",

        # ── Status / Stage ────────────────────────────────────────────────────
        "RMBDMStageDesc":           "text",
        "RMStageSeqNo":             "text",
        "RMStageName":              "text",
        "PriorityName":             "text",
        "RMCategoryName":           "text",
        "RMCategorySubName":        "text",
        "FrequencyCode":            "text",
        "FrequencyName":            "text",

        # ── Location ──────────────────────────────────────────────────────────
        "LocalityCode":             "text",
        "LocalityName":             "text",
        "BuildingCode":             "text",
        "BuildingName":             "text",
        "FloorName":                "text",
        "SpotName":                 "text",
        "BDMLongitude":             "text",
        "BDMLattitude":             "text",

        # ── Organisation ──────────────────────────────────────────────────────
        "ContractCode":             "text",
        "ContractName":             "text",
        "DivisionCode":             "text",
        "DivisionName":             "text",

        # ── Descriptive ───────────────────────────────────────────────────────
        "RMRequestDetailsDesc":     "text",
        "RMTechnicalFindings":      "text",
        "RMMaintenanceRemarks":     "text",
        "RMOverDueTime":            "text",
        "RMETADate":                "text",
        "RMResponseTime":           "text",
        "RMResolutionTime":         "text",
        "RMFlowSeqNo":              "text",
        "RMTotalAmount":            "text",
        "RMManPower":               "text",
        "RMManHours":               "text",

        # ── Technician ────────────────────────────────────────────────────────
        "RMTechName":               "text",
        "RMTechRemarks":            "text",
        "ReworkRemarks":            "text",
        "RMWithdrawRemarks":        "text",

        # ── Audit / Metadata ──────────────────────────────────────────────────
        "Remarks":                  "text",
        "FilePath":                 "text",
        "CreatedTtm":               "text",
        "UpdatedTtm":               "text",

        # ── Flags (boolean) ───────────────────────────────────────────────────
        "IsRMBMS":                  "bool",
        "IsRMRework":               "bool",
        "IsRMWithdraw":             "bool",
        "IsRMTechManual":           "bool",
        "IsRMCCMAnaliyseClosed":    "bool",
        "IsDraft":                  "bool",
        "IsActive":                 "bool",
        "DeleStat":                 "bool",

        # ── Numeric ───────────────────────────────────────────────────────────
        "RMCCMComplaintIDPK":       "bigint",  # duplicated above for clarity
        "RMDownloadStat":           "int",
        "CreatedUserID":            "int",
        "RMMaintenanceHrs":         "float",   # numeric in DB

        # ── Datetime fields ───────────────────────────────────────────────────
        "RMComplainedDateTime":     "datetime",
        "RMBDMWOCompletedDate":     "datetime",
        "RMXComplaintDate":         "datetime",
        "RMTeStartDateTime":        "datetime",
        "RMTeEndDateTime":          "datetime",
    },

    # =========================================================================
    # SB  —  Schedule Based (Housekeeping / Cleanliness Inspections)
    # Tracks pre-scheduled service bookings and cleanliness inspection tasks.
    # DB table: ScheduleBased
    # Total fields: 54
    # =========================================================================
    "sb": {
        # ── Identifiers ───────────────────────────────────────────────────────
        "SBCreMRNo":                "text",
        "SBCreWorkOrder":           "text",

        # ── Stage / Status ────────────────────────────────────────────────────
        "PPMStageName":             "text",
        "StageSeqNo":               "text",
        "FrequencyCode":            "text",
        "FrequencyName":            "text",
        "ServiceTypCode":           "text",
        "ServiceTypeName":          "text",

        # ── Location ──────────────────────────────────────────────────────────
        "LocalityCode":             "text",
        "LocalityName":             "text",
        "BuildingName":             "text",
        "FloorName":                "text",
        "SpotName":                 "text",
        "SBCrePPMLattitude":        "text",
        "SBCrePPMLongitude":        "text",

        # ── Organisation ──────────────────────────────────────────────────────
        "ContractCode":             "text",
        "ContractName":             "text",
        "DivisionCode":             "text",
        "DivisionName":             "text",
        "DisciplineCode":           "text",
        "DisciplineName":           "text",

        # ── Technician / Staff ────────────────────────────────────────────────
        "SBTechName":               "text",
        "PMTechRemarks":            "text",
        "PMSBLastSBRemarks":        "text",
        "PMSBStaffAssignBy":        "text",

        # ── Remarks ───────────────────────────────────────────────────────────
        "SBCreWithDrawRemarks":     "text",
        "SBCreRescheduleRemarks":   "text",
        "SBCreReworkRemarks":       "text",

        # ── Audit / Metadata ──────────────────────────────────────────────────
        "Remarks":                  "text",
        "FilePath":                 "text",
        "CreatedTtm":               "text",
        "UpdatedTtm":               "text",

        # ── Flags (boolean) ───────────────────────────────────────────────────
        "IsSBCreWithDraw":          "bool",
        "IsSbCreReschedule":        "bool",
        "IsSBCreRework":            "bool",
        "IsSBCreTechManual":        "bool",
        "IsSBCreSupManual":         "bool",
        "IsSBCreMaterial":          "bool",
        "IsDraft":                  "bool",
        "IsActive":                 "bool",
        "DeleStat":                 "bool",

        # ── Numeric (bigint keys) ─────────────────────────────────────────────
        "SBCreParentCreationKey":   "bigint",
        "SBCreChargeLedgerKey":     "bigint",
        "SBCreCostLedgerKey":       "bigint",

        # ── Numeric (float) ───────────────────────────────────────────────────
        "SBCreSLAHours":            "float",
        "SBCreMaintenanceHours":    "float",

        # ── Numeric (integer) ─────────────────────────────────────────────────
        "CreatedUserID":            "int",

        # ── Datetime fields ───────────────────────────────────────────────────
        "SBCreWoDateTime":          "datetime",
        "SBCreGeneratedTtm":        "datetime",
        "SBCreActualDate":          "datetime",
        "SBCreWoCompletedDate":     "datetime",
        "PMSBLastSBDateTime":       "datetime",
        "SBTechStartDateTime":      "datetime",
        "SBTechEndDateTime":        "datetime",
    },
}
