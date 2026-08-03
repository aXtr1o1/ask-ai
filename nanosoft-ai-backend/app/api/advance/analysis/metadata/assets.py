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
        "Example: 'AA-HVAC-FA-3814','BD-CV-DR-3816'"
    ),

    "AssetBarcode": (
        "Barcode printed on the asset label for scanning. "
        "Example: '11273816','119263818'"
    ),

    "EquipmentRefNo": (
        "Unique reference number assigned to the equipment for identification and cross-referencing across maintenance modules. "
        "Example: '019A','020B'"
    ),

    "SerialNo": (
        "Manufacturer serial number. Used for warranty tracking. "
        "Example: '001 F 002','001 F 018'"
    ),

    "DrawingNo": (
        "Engineering drawing number associated with this asset. "
        "Example: '12432','1345'"
    ),

    # --- Classification ---
    "StatusName": (
        "Operational status of the asset. "
    ),

    "ConditionName": (
        "Physical condition of the asset. "
    ),

    "PriorityName": (
        "Criticality level of the asset. "
    ),

    "AssetTypeName": (
        "Physical classification of the asset. "
        "May be null if not classified."
    ),

    "DivisionName": (
        "Maintenance division responsible for this asset. "
        "Example: 'HVAC System','Electrical System'"
    ),

    "DisciplineName": (
        "Technical sub-category within the division. "
        "Example: 'FCU','Door'"
    ),

    # --- Equipment Details ---
    "EquipmentName": (
        "Name or description of the asset. "
        "Example: 'fan coin unit','Kia Carens'"
    ),

    "MakeName": (
        "Manufacturer or brand. "
        "Example: 'SCANNIA','Kia'"
    ),

    "ModelName": (
        "Model number or name. "
        "Example: 'CP 13','Carens 2025'"
    ),

    "Owner": (
        "Owner or responsible person/department assigned to this asset. "
        "Example: 'Facilities Team','Operations'"
    ),

    "TradeGroupName": (
        "Trade group or maintenance category assigned to this asset."
    ),

    "ServiceAreaName": (
        "Service area or maintenance zone where this asset is managed."
    ),

    "Remarks": (
        "Free-text remarks or observations about the asset. "
        "Example: 'Installed successfully','Requires inspection'"
    ),

    # --- Location ---
    "LocalityName": (
        "Geographic locality where the asset is installed. "
        "Example: 'Ajman','Bur Dubai'"
    ),

    "BuildingName": (
        "Building where the asset is installed. "
        "Example: 'Building 2 - Residential High Rise','Bhawan Tower Al Barsha'"
    ),

    "FloorName": (
        "Floor within the building. "
        "Example: 'Ground Floor','Floor 9'"
    ),

    "SpotName": (
        "Specific spot or zone within the floor. "
        "Example: 'Common Area','Appartement-90'"
    ),

    "Longitude": (
        "GPS longitude coordinate indicating the asset's physical installation location. "
        "Example: '55.2708','54.3773'"
    ),

    "Latitude": (
        "GPS latitude coordinate indicating the asset's physical installation location. "
        "Example: '25.2048','24.4539'"
    ),

    # --- Purchase / Installation ---
    "PurDate": (
        "Purchase date of the asset. Format: 'DD-MM-YYYY'. "
        "Example: '13-01-2022','24-03-2025'"
    ),

    "PurValue": (
        "Purchase value / cost of the asset. "
        "Example: '25000.00','4999.00'"
    ),

    "InstalledDate": (
        "Date the asset was installed. Format: 'DD-MM-YYYY'. "
        "Example: '15-01-2022','28-03-2025'"
    ),

    "YearOfManuf": (
        "Year the asset was manufactured. "
        "Example: '2022','2025'"
    ),

    "LifeInYear": (
        "Expected useful life of the asset in years before replacement or retirement. "
        "Example: '10','15'"
    ),

    "ScrapDate": (
        "Date the asset was scrapped or written off. Null if still in service. "
        "Example: '01-01-2035','15-06-2038'"
    ),

    "ScrapValue": (
        "Residual value of the asset at the time it was scrapped or retired. "
        "Example: '0.00','500.00'"
    ),

    # --- Flags ---
    "OnHold": (
        "Boolean — true means operations on this asset are currently on hold. "
        "Example: 'true','false'"
    ),

    "IsSnagged": (
        "Boolean — true means a snag was recorded during audit or inspection. "
        "Example: 'true','false'"
    ),

    "IsScraped": (
        "Boolean — true means this asset has been scrapped and is no longer in service. "
        "Example: 'true','false'"
    ),

    "IsEnablePPM": (
        "Boolean — true means PPM work orders can be generated for this asset. "
        "Example: 'true','false'"
    ),

    "IsEnableBDM": (
        "Boolean — true means breakdown complaints can be raised against this asset. "
        "Example: 'true','false'"
    ),

    "IsEnableBMS": (
        "Boolean — true means this asset is integrated with the Building Management System. "
        "Example: 'true','false'"
    ),

    "IsEnableDSM": (
        "Boolean — true means Demand Side Management is enabled for this asset. "
        "Example: 'true','false'"
    ),
}