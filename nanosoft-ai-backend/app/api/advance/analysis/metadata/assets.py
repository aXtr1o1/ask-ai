"""
Analysis Metadata — assets module

Physical Asset Register.
Records represent individual physical assets, equipment, devices, or
machines registered in the facility management system.
"""

ASSETS_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "AssetTagNo": (
        "Unique tag number or identifier assigned to the physical asset. "
        "Used as the primary reference ID for an asset record. "
        "Format example: 'AQ-ELE-SMDB-13837'."
    ),
    "AssetBarcode": (
        "Barcode number printed on the asset label for scanning purposes. "
        "Used during physical verification or inventory audits."
    ),
    "EquipmentName": (
        "Common name or short description of the equipment or asset type, "
        "such as 'Split AC', 'Chiller 2', 'AHU 01', 'Booster Pump', "
        "'smoke detector', 'Window AC', 'DB', 'SMDB'."
    ),
    "EquipmentRefNo": (
        "Equipment reference number or internal code used to cross-reference "
        "the asset with other modules such as PPM work orders."
    ),
    "SerialNo": (
        "Manufacturer serial number of the asset. Useful for warranty tracking, "
        "vendor support, and unique hardware identification."
    ),

    # --- Classification ---
    "StatusName": (
        "Current operational status of the asset. "
        "Known values: 'Online' (asset is active and working), "
        "'Offline' (asset is inactive, decommissioned, or out of service). "
        "Filter on this field to find all active or all decommissioned assets."
    ),
    "ConditionName": (
        "Physical condition or health of the asset as assessed during inspection. "
        "Known values: 'Good' (asset is in good working condition), "
        "'Fair' (asset is functional but showing wear), "
        "'Bad' (asset is deteriorated or in poor condition). "
        "Filter on this field to find assets needing replacement or attention."
    ),
    "PriorityName": (
        "Priority or criticality level of the asset to facility operations. "
        "Known values (in descending criticality): "
        "'P1 Critical' (mission-critical, immediate attention required), "
        "'P2 High' (high-priority, important to operations), "
        "'P3 Medium' (moderate priority, standard maintenance), "
        "'P4 Low' (low priority, minimal operational impact). "
        "Filter on this field to focus on critical or high-priority assets."
    ),
    "AssetTypeName": (
        "Classification of the asset by physical nature. "
        "Known values: 'Fixed' (permanently installed, cannot be relocated), "
        "'Movable' (portable or relocatable equipment). "
        "May be null if the asset type has not been classified."
    ),
    "DivisionName": (
        "Service division or department responsible for maintaining this asset. "
        "Examples: 'HVAC System', 'Electrical System', 'Plumbing System', "
        "'Fire Fighting and Alarm system', 'Housekeeping', 'Motorized', "
        "'Low Voltage'. Used to group assets by maintenance team."
    ),
    "DisciplineName": (
        "Technical discipline or specific sub-category of the asset within its division. "
        "Examples: 'FCU', 'SPLIT AC UNITS', 'WINDOW AC', 'ROOFTOP AAON', "
        "'SMDB', 'DB', 'BOOSTER PUMP', 'Smoke Detector', 'WAT - MTZ'. "
        "More granular than DivisionName."
    ),

    # --- Location ---
    "LocalityName": (
        "Geographic locality, city, or area where the asset is physically located. "
        "Examples: 'Dubai', 'Al Quoz', 'Bur Dubai', 'Ajman'. "
        "Used for location-based grouping and filtering."
    ),
    "BuildingName": (
        "Name of the building, tower, property, or site where the asset is installed. "
        "Examples: 'Reef Mall', 'Bhawan Tower Al Barsha', 'Labour camp-2', "
        "'Building 1 - Residential High Rise'."
    ),
    "FloorName": (
        "Floor level or floor name within the building where the asset is located. "
        "Examples: '1st Level', 'Ground Floor', 'First Floor', 'Floor 9'."
    ),
    "SpotName": (
        "Specific spot, room, zone, or exact location within the floor where the "
        "asset is installed. Examples: 'WASH ROOMS (M/F) - Near Nesto', 'DDC', "
        "'B04', 'Common Area'."
    ),

    # --- Hardware Details ---
    "MakeName": (
        "Manufacturer or brand name of the asset. "
        "Examples: 'Carrier', 'ABB', 'Super general', 'RR', 'OG'. "
        "May be 'Not Specified' if the manufacturer is unknown."
    ),
    "ModelName": (
        "Model number or model name of the asset as specified by the manufacturer. "
        "Examples: 'IED1502AO', 'SMAB', 'Window AC', 'Pump set'. "
        "May be 'N/A' if the model is not recorded."
    ),
    "Owner": (
        "Name of the owner or responsible person/department assigned to this asset."
    ),
    "ServiceArea": (
        "Service area or zone designation for this asset, used to group assets "
        "under a specific operational service boundary."
    ),
    "TradeGroup": (
        "Trade group or trade category the asset belongs to, used for "
        "maintenance planning and contractor assignment."
    ),
    "DrawingNo": (
        "Engineering drawing number or reference document number associated "
        "with this asset, used for technical reference and as-built documentation."
    ),
    "Remarks": (
        "Free-text remarks, notes, or observations about the asset entered "
        "during registration or maintenance visits."
    ),

    # --- Flags ---
    "OnHold": (
        "Boolean flag indicating whether maintenance or operations on this asset "
        "are currently on hold. True means the asset is paused or suspended."
    ),
    "IsSnagged": (
        "Boolean flag indicating whether this asset has been marked as snagged "
        "during an audit or inspection walkthrough. True means a snag was recorded."
    ),
    "IsScraped": (
        "Boolean flag indicating whether this asset has been scrapped or written off "
        "and is no longer in service. True means the asset is decommissioned."
    ),
    "EnablePPM": (
        "Boolean flag indicating whether Planned Preventive Maintenance (PPM) is "
        "enabled for this asset. True means PPM work orders can be generated."
    ),
    "EnableBDM": (
        "Boolean flag indicating whether Breakdown Maintenance (BDM) complaints "
        "can be raised against this asset. True means breakdown tickets are allowed."
    ),
    "EnableBMS": (
        "Boolean flag indicating whether this asset is integrated with the Building "
        "Management System (BMS). True means BMS monitoring is active."
    ),
    "EnableDSM": (
        "Boolean flag indicating whether Demand Side Management (DSM) is enabled "
        "for this asset, typically for energy-intensive equipment."
    ),
}
