"""
Retrieval Mappings — Metadata Column Name -> SP Parameter Name
"""

ASSETS_MAPPINGS: dict[str, str] = {
    "AssetTagNo":       "asset_tag_no",
    "AssetBarcode":     "asset_barcode",
    "EquipmentName":    "equipment_name",
    "EquipmentRefNo":   "equipment_ref_no",
    "SerialNo":         "serial_no",
    "StatusName":       "status",
    "ConditionName":    "condition",
    "PriorityName":     "priority",
    "AssetTypeName":    "asset_type",
    "DivisionName":     "division",
    "DisciplineName":   "discipline",
    "LocalityName":     "locality",
    "BuildingName":     "building",
    "FloorName":        "floor",
    "SpotName":         "spot_name",
    "MakeName":         "make",
    "ModelName":        "model",
    "Owner":            "owner",
    "ServiceArea":      "service_area",
    "TradeGroup":       "trade_group",
    "DrawingNo":        "drawing_no",
    "Remarks":          "remarks",
    "Keyword":          "keyword",
    "date_from":        "date_from",
    "date_to":          "date_to",
}

ASSETS_BOOL_MAPPINGS: dict[str, str] = {
    "OnHold":       "on_hold",
    "IsSnagged":    "is_snagged",
    "IsScraped":    "is_scraped",
    "EnablePPM":    "enable_ppm",
    "EnableBDM":    "enable_bdm",
    "EnableBMS":    "enable_bms",
    "EnableDSM":    "enable_dsm",
}

ASSETS_NUMERIC_MAPPINGS: dict[str, str] = {}


PPM_MAPPINGS: dict[str, str] = {
    "WorkOrder":        "work_order",
    "AssetTagNo":       "asset_tag_no",
    "EquipmentRefNo":   "equipment_ref_no",
    "PPMStatus":        "status",
    "PPMStageName":     "stage",
    "FrequencyName":    "frequency",
    "DivisionName":     "division",
    "DisciplineName":   "discipline",
    "ContractName":     "contract",
    "EquipmentName":    "equipment",
    "LocalityName":     "locality",
    "LocalityCode":     "locality_code",
    "BuildingName":     "building",
    "FloorName":        "floor",
    "SpotName":         "spot_name",
    "PMTechName":       "tech",
    "Keyword":          "keyword",
    "date_from":        "date_from",
    "date_to":          "date_to",
    "WoCompletedDate":  "comp_from",
    "comp_to":          "comp_to",
}

PPM_BOOL_MAPPINGS: dict[str, str] = {}

PPM_NUMERIC_MAPPINGS: dict[str, str] = {
    "sla_min": "sla_min",
    "sla_max": "sla_max",
}


BDM_MAPPINGS: dict[str, str] = {
    "ComplaintNo":          "complaint_no",
    "AssetTagNo":           "asset_tag_no",
    "AssetBarcode":         "asset_barcode",
    "ClientWoNo":           "client_wo_no",
    "WoStatus":             "status",
    "PriorityName":         "priority",
    "StageName":            "stage",
    "ComplaintTypeName":    "complaint_type",
    "ComplaintHeader":      "complaint_header",
    "ComplaintModeName":    "complaint_mode",
    "ComplaintNatureName":  "complaint_nature",
    "WoType":               "wo_type",
    "ServiceTypeName":      "service_type",
    "ContractName":         "contract",
    "AnalysisTechName":     "analysis_tech",
    "ExecutionTechName":    "execution_tech",
    "Complainer":           "complainer",
    "RegisterBy":           "register_by",
    "LocalityName":         "locality",
    "LocalityCode":         "locality_code",
    "BuildingName":         "building",
    "FloorName":            "floor",
    "SpotName":             "spot_name",
    "DivisionName":         "division",
    "DisciplineName":       "discipline",
    "Keyword":              "keyword",
    "date_from":            "date_from",
    "date_to":              "date_to",
    "BDMWOCompletedDate":   "completed_from",
    "completed_to":         "completed_to",
}

BDM_BOOL_MAPPINGS: dict[str, str] = {}
BDM_NUMERIC_MAPPINGS: dict[str, str] = {}


FA_MAPPINGS: dict[str, str] = {
    "RMComplaintNo":        "complaint_no",
    "RMCCMComplaintCode":   "complaint_code",
    "RMXComplaintNo":       "x_complaint_no",
    "PriorityName":         "priority",
    "RMStageName":          "stage",
    "RMCategoryName":       "category",
    "RMCategorySubName":    "category_sub",
    "DivisionName":         "division",
    "ContractName":         "contract",
    "FrequencyName":        "frequency",
    "RMRequestDetailsDesc": "request_desc",
    "RMTechName":           "tech",
    "LocalityName":         "locality",
    "LocalityCode":         "locality_code",
    "BuildingName":         "building",
    "FloorName":            "floor",
    "SpotName":             "spot_name",
    "Keyword":              "keyword",
    "date_from":            "date_from",
    "date_to":              "date_to",
    "RMBDMWOCompletedDate": "comp_from",
    "comp_to":              "comp_to",
}

FA_BOOL_MAPPINGS: dict[str, str] = {
    "IsRMWithdraw": "is_withdraw",
    "IsRMRework":   "is_rework",
    "IsRMBMS":      "is_bms",
    "IsActive":     "is_active",
    "IsDraft":      "is_draft",
}

FA_NUMERIC_MAPPINGS: dict[str, str] = {}


SB_MAPPINGS: dict[str, str] = {
    "SBRequestNo":       "work_order",
    "SBStageName":       "stage",
    "ServiceTypeName":   "service_type",
    "FrequencyName":     "frequency",
    "DivisionName":      "division",
    "DisciplineName":    "discipline",
    "ContractName":      "contract",
    "TechName":          "tech",
    "LocalityName":      "locality",
    "LocalityCode":      "locality_code",
    "BuildingName":      "building",
    "FloorName":         "floor",
    "SpotName":          "spot_name",
    "Keyword":           "keyword",
    "date_from":         "date_from",
    "date_to":           "date_to",
    "CompletedDateTime": "comp_from",
    "comp_to":           "comp_to",
}

SB_BOOL_MAPPINGS: dict[str, str] = {
    "IsSBCreWithDraw":   "is_withdraw",
    "IsSbCreReschedule": "is_reschedule",
    "IsSBCreRework":     "is_rework",
    "IsActive":          "is_active",
    "IsDraft":           "is_draft",
}

SB_NUMERIC_MAPPINGS: dict[str, str] = {
    "sla_min": "sla_min",
    "sla_max": "sla_max",
}


ALL_MAPPINGS: dict[str, tuple[dict, dict, dict]] = {
    "assets": (ASSETS_MAPPINGS, ASSETS_BOOL_MAPPINGS, ASSETS_NUMERIC_MAPPINGS),
    "bdm":    (BDM_MAPPINGS,    BDM_BOOL_MAPPINGS,    BDM_NUMERIC_MAPPINGS),
    "ppm":    (PPM_MAPPINGS,    PPM_BOOL_MAPPINGS,    PPM_NUMERIC_MAPPINGS),
    "fa":     (FA_MAPPINGS,     FA_BOOL_MAPPINGS,     FA_NUMERIC_MAPPINGS),
    "sb":     (SB_MAPPINGS,     SB_BOOL_MAPPINGS,     SB_NUMERIC_MAPPINGS),
}
