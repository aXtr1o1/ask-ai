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
        "StatusName", "ConditionName", "PriorityName",
        "LocalityName", "BuildingName", "FloorName", "SpotName",
        "Longitude", "Latitude",
        "AssetTypeName", "DivisionName", "DisciplineName",
        "MakeName", "ModelName", "Owner", "ServiceAreaName", "TradeGroupName",
        "DrawingNo", "Remarks",
        "OnHold", "IsSnagged", "IsScraped",
        "IsEnablePPM", "IsEnableBDM", "IsEnableBMS", "IsEnableDSM",
        "YearOfManuf", "LifeInYear",
        "PurDate", "PurValue",
        "InstalledDate", "ScrapDate", "ScrapValue",
    ],

    # Breakdown / Reactive Maintenance (Complaints)
    # Tracks reactive work orders raised when equipment fails or a user complains.
    "bdm": [
        "ComplaintNo", "AssetTagNo", "AssetBarcode", "ClientWoNo",
        "WoStatus", "PriorityName", "StageName",
        "ComplainedDateTime", "BDMWOCompletedDate",
        "LocalityName", "LocalityCode",
        "BuildingName", "FloorName", "SpotName",
        "ComplaintTypeName", "ComplaintHeaderName",
        "ComplaintModeName", "ComplaintNatureName",
        "WoTypeName", "ServiceTypeName",
        "DivisionName", "DisciplineName", "ContractName",
        "Description", "ComplainerName", "RegisterBy",
        "AnalysisTechName", "ExecutionTechName",
        "ResponseTAT", "ResolutionTAT",
        "SLACCMStartDateTime", "SLACCMEndDateTime",
        "SLABDMStartDateTime", "SLABDMEndDateTime",
        "AnalysisStartTime", "AnalysisEndTime",
        "ExecutionStartTime", "ExecutionEndTime",
        "StandByRemarks",
    ],

    # Planned Preventive Maintenance
    # Tracks scheduled routine maintenance tasks for registered assets.
    "ppm": [
        "WorkOrder", "AssetTagNo", "EquipmentRefNo",
        "PPMStatus", "PPMStageName", "FrequencyName",
        "WoDateTime", "WoCompletedDate",
        "LocalityName", "LocalityCode",
        "BuildingName", "FloorName", "SpotName",
        "EquipmentName",
        "DivisionName", "DisciplineName",
        "ContractName",
        "PMTechName", "PMTechStartDateTime", "PMTechEndDateTime",
        "PMTechRemarks", "LastStandByRemarks",
        "PPMPendingPeriod", "SLADuration",
    ],

    # Facility Audits & Remedial (Snags / Inspections)
    # Tracks audit tasks, inspections, and remedial snags from physical walkthroughs.
    "fa": [
        "RMCCMComplaintIDPK", "RMCCMComplaintCode", "RMComplaintNo",
        "RMComplainedDateTime", "RMBDMWOCompletedDate", "RMOverDueTime",
        "RMETADate", "RMRequestDetailsDesc", "RMTechnicalFindings",
        "RMMaintenanceRemarks", "RMDownloadStat", "RMTotalAmount",
        "RMMaintenanceHrs", "RMManPower", "RMManHours",
        "RMFlowSeqNo", "RMBDMStageDesc", "RMXComplaintNo",
        "RMXComplaintDate", "RMResponseTime", "RMResolutionTime",
        "IsRMBMS", "IsRMRework", "IsRMWithdraw",
        "IsRMTechManual", "IsRMCCMAnaliyseClosed", "IsDraft",
        "IsActive", "DeleStat", "ReworkRemarks",
        "RMWithdrawRemarks", "RMTechName", "RMTechRemarks",
        "RMTeStartDateTime", "RMTeEndDateTime",
        "BDMLongitude", "BDMLattitude",
        "LocalityCode", "LocalityName",
        "BuildingCode", "BuildingName",
        "FloorName", "SpotName",
        "ContractCode", "ContractName",
        "DivisionCode", "DivisionName",
        "RMStageSeqNo", "RMStageName",
        "FrequencyCode", "FrequencyName",
        "PriorityName", "RMCategoryName", "RMCategorySubName",
        "Remarks", "FilePath",
        "CreatedUserID", "CreatedTtm", "UpdatedTtm",
    ],

    # Schedule Booking (Housekeeping / Cleanliness Inspections)
    # Tracks pre-scheduled service bookings and cleanliness inspection tasks.
    "sb": [
        "SBCreMRNo", "SBCreWorkOrder", "SBCreWoDateTime",
        "SBCreGeneratedTtm", "SBCreActualDate", "SBCreWoCompletedDate",
        "SBCreParentCreationKey", "SBCreSLAHours", "SBCreMaintenanceHours",
        "IsSBCreWithDraw", "IsSbCreReschedule", "IsSBCreRework",
        "IsSBCreTechManual", "IsSBCreSupManual", "IsSBCreMaterial",
        "IsDraft", "IsActive", "DeleStat",
        "SBCreWithDrawRemarks", "SBCreRescheduleRemarks", "SBCreReworkRemarks",
        "SBTechName", "PMTechRemarks", "PMSBLastSBRemarks",
        "PMSBLastSBDateTime", "PMSBStaffAssignBy",
        "SBTechStartDateTime", "SBTechEndDateTime",
        "SBCrePPMLattitude", "SBCrePPMLongitude",
        "LocalityCode", "LocalityName",
        "BuildingName", "FloorName", "SpotName",
        "ContractCode", "ContractName",
        "DivisionCode", "DivisionName",
        "DisciplineCode", "DisciplineName",
        "PPMStageName", "StageSeqNo",
        "FrequencyCode", "FrequencyName",
        "ServiceTypCode", "ServiceTypeName",
        "SBCreChargeLedgerKey", "SBCreCostLedgerKey",
        "Remarks", "FilePath",
        "CreatedUserID", "CreatedTtm",
        
    ],

    # Maintenance Contracts Register
    # Tracks all maintenance contracts, service agreements, and sub-contracts.
    "contracts": [
        "ContractIDPK", "ContractCode", "ContractName",
        "CustomerName", "OrganisationName",
        "ContractTypeName", "ContractCategName", "ContractGroupName",
        "ContStStatus", "ContStTypes",
        "ContractDate", "StartDate", "EndDate", "AnnualReviewDate", "ExtendedDate",
        "ContractValue", "ConValueBeforVat", "VatAmount", "ExtendedValue", "TotalContractValue",
        "TaxName", "Period", "ConPaymentTermsName",
        "NoOfBilling", "NoofInvoice",
        "NoofEngineer", "NoofSupervisor", "NoofPrimary",
        "ShiftNoofPrimary", "ShiftNoofSecondary",
        "IsActive", "IsDraft", "IsRenewal", "IsExtended", "IsTerminate",
        "IsNonContract", "IsPPM", "IsBDM", "IsDSM", "IsIncident", "IsCase",
    ],

    # Employee / Workforce Register
    # Tracks every employee, technician, supervisor, and staff member in the system.
    "employees": [
        "EmployeeIDPK", "EmployeeCode", "EmployeeFullName", "FirstName", "LastName",
        "EmpGenderName", "MaritalStatus", "NationalityName", "CountryName",
        "EmpDateofBirth", "EmpDateOfJoin", "ProbationPeriod", "DateofConfirmation", "LeftJobOnDate",
        "CreatedTtm",
        "OrganisationName", "DepartmentName", "DesignationName", "ClassificationName",
        "Branch", "NatureOfWorkName", "EmployeeTypeName", "EmploymentTypeName",
        "ShiftName", "ShiftCode",
        "EmployeeGroupName", "EmpGradeName", "EmpTitleName",
        "Color", "VehicleNo",
        "WorkHours", "WrkPerDay",
        "IsActive", "IsAttendanceEnable", "IsSinglePunch",
        "Remarks",
    ],

    # Location / Locality
    # Tracks location data and locality regions
    "location": [
        "LocalityCode", "LocalityName", "LocAddress1", "LocAddress2",
        "CityCode", "CityName", "LocalityGroupCode", "LocalityGroupName",
        "AdminLocalityTypeName", "IsActive", "IsDraft", "IsPortalDisplay",
        "IsNonContract", "IsDefault", "Remarks", "CreatedTtm",
    ],

    # Building
    # Tracks building master data associated with a locality
    "building": [
        "BuildingCode", "BuildingName", "LocalityCode", "LocalityName",
        "AssBuildingTypeName", "IsActive", "IsDraft", "IsNonContract",
        "IsDefault", "Remarks", "CreatedTtm",
    ],

    # Floor
    # Tracks floor master data within buildings
    "floor": [
        "FloorCode", "FloorName", "BuildingCode", "BuildingName",
        "LocalityCode", "LocalityName", "IsActive", "IsDraft",
        "IsNonContract", "IsDefault", "Remarks", "CreatedTtm",
    ],

    # Spot
    # Tracks individual spaces/spots within floors
    "spot": [
        "SpotCode", "SpotName", "BuildingCode", "BuildingName",
        "FloorCode", "FloorName", "LocalityCode", "LocalityName",
        "SpotTypeName", "IsActive", "IsDraft", "IsOccupancy",
        "IsParking", "IsAllocated", "IsNonContract", "Remarks", "CreatedTtm",
    ],
}