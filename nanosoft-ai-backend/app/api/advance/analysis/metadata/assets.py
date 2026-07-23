"""
Analysis Metadata — assets module

Physical Asset Register.
Records represent individual physical assets and equipment
registered in the facility management system.

Field names verified against actual SP response data.
"""

ASSETS_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "AssetTagNo": (
        "Unique tag number for the asset. Primary reference ID. "
        "Format: 'RUW-HA-SU-13853'."
    ),
    "AssetBarcode": (
        "Barcode printed on the asset label for scanning. "
        "Example: '48126333953'."
    ),
    "EquipmentRefNo": (
        "Equipment reference number for cross-referencing with PPM work orders."
    ),
    "SerialNo": (
        "Manufacturer serial number. Used for warranty tracking."
    ),
    "DrawingNo": (
        "Engineering drawing number associated with this asset."
    ),

    # --- Classification ---
    "StatusName": (
        "Operational status of the asset. "
        "Known values: 'Online' (active and working), 'Offline' (inactive or decommissioned)."
    ),
    "ConditionName": (
        "Physical condition of the asset. "
        "Known values: 'Good', 'Fair', 'Bad'."
    ),
    "PriorityName": (
        "Criticality level of the asset. "
        "Known values: 'P1 Critical', 'P2 High', 'P3 Medium', 'P4 Low'."
    ),
    "AssetTypeName": (
        "Physical classification of the asset. "
        "Known values: 'Fixed' (permanently installed), 'Movable' (portable). "
        "May be null if not classified."
    ),
    "DivisionName": (
        "Maintenance division responsible for this asset. "
        "Examples: 'Home Appliances', 'Business Appliance', 'HVAC System', "
        "'Electrical System', 'Fire Fighting and Alarm system'."
    ),
    "DisciplineName": (
        "Technical sub-category within the division. "
        "Examples: 'Split Unit-HA', 'Printer-BA', 'FCU', 'SMDB'."
    ),

    # --- Equipment Details ---
    "EquipmentName": (
        "Name or description of the asset. "
        "Examples: 'Split Unit 5 - GREE - Livo GEN4 Inverter', 'Printer 1 - Canon - imageRUNNER 2925i'."
    ),
    "MakeName": (
        "Manufacturer or brand. Examples: 'GREE', 'Canon', 'Carrier', 'ABB'."
    ),
    "ModelName": (
        "Model number or name. "
        "Examples: 'GREE Livo GEN4 Inverter', 'PIXMA G4770', 'imageRUNNER 2925i'."
    ),
    "Owner": (
        "Owner or responsible person/department assigned to this asset."
    ),
    "TradeGroupName": (
        "Trade group for maintenance planning. Example: 'Owned'."
    ),
    "ServiceAreaName": (
        "Service area or zone designation for this asset."
    ),
    "Remarks": (
        "Free-text remarks or observations about the asset."
    ),

    # --- Location ---
    "LocalityName": (
        "Geographic locality where the asset is installed. "
        "Examples: 'Ruwi', 'Dubai', 'Al Quoz', 'Ajman'."
    ),
    "BuildingName": (
        "Building where the asset is installed. "
        "Examples: 'Building 1', 'Reef Mall', 'Bhawan Tower Al Barsha'."
    ),
    "FloorName": (
        "Floor within the building. Examples: 'Ground Floor', 'Floor 1', 'Floor 2'."
    ),
    "SpotName": (
        "Specific spot or zone within the floor. Examples: 'Reception', 'Office'."
    ),
    "Longitude": (
        "GPS longitude coordinate of the asset location."
    ),
    "Latitude": (
        "GPS latitude coordinate of the asset location."
    ),

    # --- Purchase / Installation ---
    "PurDate": (
        "Purchase date of the asset. Format: 'DD-MM-YYYY'."
    ),
    "PurValue": (
        "Purchase value / cost of the asset. Example: '4999.00'."
    ),
    "InstalledDate": (
        "Date the asset was installed. Format: 'DD-MM-YYYY'."
    ),
    "YearOfManuf": (
        "Year the asset was manufactured. Example: 2026."
    ),
    "LifeInYear": (
        "Expected operational lifespan of the asset in years. Example: 60."
    ),
    "ScrapDate": (
        "Date the asset was scrapped or written off. Null if still in service."
    ),
    "ScrapValue": (
        "Residual or scrap value at the time of decommission. Example: '0.00'."
    ),

    # --- Flags ---
    "OnHold": (
        "Boolean — true means operations on this asset are currently on hold."
    ),
    "IsSnagged": (
        "Boolean — true means a snag was recorded during audit or inspection."
    ),
    "IsScraped": (
        "Boolean — true means this asset has been scrapped and is no longer in service."
    ),
    "IsEnablePPM": (
        "Boolean — true means PPM work orders can be generated for this asset."
    ),
    "IsEnableBDM": (
        "Boolean — true means breakdown complaints can be raised against this asset."
    ),
    "IsEnableBMS": (
        "Boolean — true means this asset is integrated with the Building Management System."
    ),
    "IsEnableDSM": (
        "Boolean — true means Demand Side Management is enabled for this asset."
    ),
}
