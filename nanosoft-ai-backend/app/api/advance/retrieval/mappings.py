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
    "ServiceAreaName":   "service_area",
    "TradeGroupName":    "trade_group",
    "DrawingNo":        "drawing_no",
    "Remarks":          "remarks",
    "Keyword":          "keyword",
    "date_from":        "date_from",
    "date_to":          "date_to",
}

ASSETS_BOOL_MAPPINGS: dict[str, str] = {
    "OnHold":           "on_hold",
    "IsSnagged":        "is_snagged",
    "IsScraped":        "is_scraped",
    "IsEnablePPM":      "enable_ppm",
    "IsEnableBDM":      "enable_bdm",
    "IsEnableBMS":      "enable_bms",
    "IsEnableDSM":      "enable_dsm",
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
    "ComplaintHeaderName":  "complaint_header",
    "ComplaintModeName":    "complaint_mode",
    "ComplaintNatureName":  "complaint_nature",
    "WoTypeName":           "wo_type",
    "ServiceTypeName":      "service_type",
    "ContractName":         "contract",
    "AnalysisTechName":     "analysis_tech",
    "ExecutionTechName":    "execution_tech",
    "ComplainerName":       "complainer",
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
    "SBCreMRNo":          "work_order",
    "PPMStageName":       "stage",
    "ServiceTypeName":   "service_type",
    "FrequencyName":     "frequency",
    "DivisionName":      "division",
    "DisciplineName":    "discipline",
    "ContractName":      "contract",
    "SBTechName":         "tech",
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


CONTRACT_MAPPINGS: dict[str, str] = {
    "ContractIDPK":         "contract_id",
    "ContractCode":         "contract_code",
    "ContractName":         "contract_name",
    "CustomerName":         "customer_name",
    "ContractTypeName":     "contract_type",
    "ContractCategName":    "contract_categ",
    "ContractGroupName":    "contract_group",
    "OrganisationName":     "organisation",
    "ContStStatus":         "status",
    "ContStTypes":          "status_type",
    "TaxName":              "tax_name",
    "Period":               "period",
    "ConPaymentTermsName":  "payment_terms",
    "Keyword":              "keyword",
    "date_from":            "date_from",
    "date_to":              "date_to",
}

CONTRACT_BOOL_MAPPINGS: dict[str, str] = {
    "IsActive":       "is_active",
    "IsDraft":        "is_draft",
    "IsRenewal":      "is_renewal",
    "IsExtended":     "is_extended",
    "IsTerminate":    "is_terminate",
    "IsNonContract":  "is_non_contract",
    "IsPPM":          "is_ppm",
    "IsBDM":          "is_bdm",
    "IsDSM":          "is_dsm",
    "IsIncident":     "is_incident",
    "IsCase":         "is_case",
}

CONTRACT_NUMERIC_MAPPINGS: dict[str, str] = {}


EMPLOYEE_MAPPINGS: dict[str, str] = {
    "EmployeeIDPK":       "employee_id",
    "EmployeeCode":       "employee_code",
    "EmployeeFullName":   "employee_name",
    "FirstName":          "first_name",
    "LastName":           "last_name",
    "OrganisationName":   "organisation",
    "DepartmentName":     "department",
    "DesignationName":    "designation",
    "ClassificationName": "classification",
    "Branch":             "branch",
    "NatureOfWorkName":   "nature_of_work",
    "EmployeeTypeName":   "employee_type",
    "EmploymentTypeName": "employment_type",
    "ShiftName":          "shift_name",
    "ShiftCode":          "shift_code",
    "EmpGenderName":      "gender",
    "MaritalStatus":      "marital_status",
    "NationalityName":    "nationality",
    "CountryName":        "country",
    "EmployeeGroupName":  "employee_group",
    "EmpGradeName":       "emp_grade",
    "EmpTitleName":       "emp_title",
    "VehicleNo":          "vehicle_no",
    "Keyword":            "keyword",
    "date_from":          "date_from",
    "date_to":            "date_to",
}

EMPLOYEE_BOOL_MAPPINGS: dict[str, str] = {
    "IsActive":             "is_active",
    "IsAttendanceEnable":   "is_attendance_enable",
    "IsSinglePunch":        "is_single_punch",
}

EMPLOYEE_NUMERIC_MAPPINGS: dict[str, str] = {}


LOCATION_MAPPINGS: dict[str, str] = {
    "LocalityCode":          "locality_code",
    "LocalityName":          "locality_name",
    "CityCode":              "city_code",
    "CityName":              "city",
    "LocalityGroupCode":     "locality_group",
    "LocalityGroupName":     "locality_group",
    "AdminLocalityTypeName": "admin_locality_type",
    "Remarks":               "keyword",
    "Keyword":               "keyword",
    "date_from":             "date_from",
    "date_to":               "date_to",
}

LOCATION_BOOL_MAPPINGS: dict[str, str] = {
    "IsActive":        "is_active",
    "IsDraft":         "is_draft",
    "IsPortalDisplay": "is_portal_display",
    "IsNonContract":   "is_non_contract",
    "IsDefault":       "is_default",
}

LOCATION_NUMERIC_MAPPINGS: dict[str, str] = {}

BUILDING_MAPPINGS: dict[str, str] = {
    "BuildingCode":        "building_code",
    "BuildingName":        "building_name",
    "LocalityCode":        "locality_code",
    "LocalityName":        "locality",
    "AssBuildingTypeName": "ass_building_type",
    "Keyword":             "keyword",
    "date_from":           "date_from",
    "date_to":             "date_to",
}

BUILDING_BOOL_MAPPINGS: dict[str, str] = {
    "IsActive":        "is_active",
    "IsDraft":         "is_draft",
    "IsNonContract":   "is_non_contract",
    "IsDefault":       "is_default",
}

BUILDING_NUMERIC_MAPPINGS: dict[str, str] = {}

FLOOR_MAPPINGS: dict[str, str] = {
    "FloorCode":    "floor_code",
    "FloorName":    "floor_name",
    "BuildingCode": "building_code",
    "BuildingName": "building",
    "LocalityCode": "locality_code",
    "LocalityName": "locality",
    "Keyword":      "keyword",
    "date_from":    "date_from",
    "date_to":      "date_to",
}

FLOOR_BOOL_MAPPINGS: dict[str, str] = {
    "IsActive":        "is_active",
    "IsDraft":         "is_draft",
    "IsNonContract":   "is_non_contract",
    "IsDefault":       "is_default",
}

FLOOR_NUMERIC_MAPPINGS: dict[str, str] = {}

SPOT_MAPPINGS: dict[str, str] = {
    "SpotCode":     "spot_code",
    "SpotName":     "spot_name",
    "BuildingCode": "building_code",
    "BuildingName": "building",
    "FloorCode":    "floor",
    "FloorName":    "floor",
    "LocalityCode": "locality_code",
    "LocalityName": "locality",
    "SpotTypeName": "spot_type",
    "Keyword":      "keyword",
    "date_from":    "date_from",
    "date_to":      "date_to",
}

SPOT_BOOL_MAPPINGS: dict[str, str] = {
    "IsActive":      "is_active",
    "IsDraft":       "is_draft",
    "IsOccupancy":   "is_occupied",
    "IsParking":     "is_parking",
    "IsAllocated":   "is_allocated",
    "IsNonContract": "is_non_contract",
}

SPOT_NUMERIC_MAPPINGS: dict[str, str] = {}

ALL_MAPPINGS: dict[str, tuple[dict, dict, dict]] = {
    "assets":    (ASSETS_MAPPINGS,    ASSETS_BOOL_MAPPINGS,    ASSETS_NUMERIC_MAPPINGS),
    "bdm":       (BDM_MAPPINGS,       BDM_BOOL_MAPPINGS,       BDM_NUMERIC_MAPPINGS),
    "ppm":       (PPM_MAPPINGS,       PPM_BOOL_MAPPINGS,       PPM_NUMERIC_MAPPINGS),
    "fa":        (FA_MAPPINGS,        FA_BOOL_MAPPINGS,        FA_NUMERIC_MAPPINGS),
    "sb":        (SB_MAPPINGS,        SB_BOOL_MAPPINGS,        SB_NUMERIC_MAPPINGS),
    "contracts": (CONTRACT_MAPPINGS,  CONTRACT_BOOL_MAPPINGS,  CONTRACT_NUMERIC_MAPPINGS),
    "employees": (EMPLOYEE_MAPPINGS,  EMPLOYEE_BOOL_MAPPINGS,  EMPLOYEE_NUMERIC_MAPPINGS),
    "location":  (LOCATION_MAPPINGS,  LOCATION_BOOL_MAPPINGS,  LOCATION_NUMERIC_MAPPINGS),
    "building":  (BUILDING_MAPPINGS,  BUILDING_BOOL_MAPPINGS,  BUILDING_NUMERIC_MAPPINGS),
    "floor":     (FLOOR_MAPPINGS,     FLOOR_BOOL_MAPPINGS,     FLOOR_NUMERIC_MAPPINGS),
    "spot":      (SPOT_MAPPINGS,      SPOT_BOOL_MAPPINGS,      SPOT_NUMERIC_MAPPINGS),
}
