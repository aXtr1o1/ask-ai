from typing import Literal

# Define valid group_by columns for all tools combined using Literal for Pydantic validation.
# We use AllColumns for all schemas so the AI can intentionally pass a wrong column 
# and receive a clean error from the payload validator, rather than a harsh Pydantic crash.

AllColumns = Literal[
    "DivisionName", "DisciplineName", "BuildingName", "FloorName", 
    "LocalityName", "StatusName", "ConditionName", "PriorityName", 
    "AssetTypeName", "EquipmentName", "MakeName", "ModelName", 
    "SpotName", "TradeGroupName", "ServiceAreaName", 
    "OnHold", "IsSnagged", "IsScraped", "IsEnablePPM", "IsEnableBDM",
    "FrequencyName", "PPMStatus", "PPMStageName", "ContractName",
    "WoStatus", "StageName", "ComplaintTypeName", "ComplaintModeName", 
    "ServiceTypeName", "RMStageName", "RMCategoryName", "RMCategorySubName", 
    "IsRMWithdraw", "IsRMRework", "IsActive"
]
