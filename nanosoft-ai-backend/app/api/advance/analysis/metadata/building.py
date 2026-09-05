"""
Analysis Metadata — building module

Building Register.
Records represent physical building structures tied to a specific locality.

Field names verified against actual SP response data.
"""

BUILDING_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "BuildingCode": (
        "Unique system code assigned to the building. "
        "Example: 'BLD-001','TWR-A'"
    ),

    "BuildingName": (
        "Full name or title of the building. "
        "Example: 'Bhawan Tower','Crystal Plaza'"
    ),

    "LocalityCode": (
        "Code of the locality where this building is geographically situated. "
        "Example: 'LOC-01'"
    ),

    "LocalityName": (
        "Name of the locality where this building is geographically situated. "
        "Example: 'Ajman','Bur Dubai'"
    ),

    "AssBuildingTypeName": (
        "Classification or architectural type of the building. "
        "Example: 'High-Rise Residential','Commercial Mall'"
    ),

    "Remarks": (
        "Free-text remarks or observations about the building. "
        "Example: 'Under renovation','Maintained by third party'"
    ),

    # --- Flags ---
    "IsActive": (
        "Boolean — true means the building is active and operational in the system. "
        "Example: 'true','false'"
    ),

    "IsDraft": (
        "Boolean — true means the building record is in a draft state. "
        "Example: 'true','false'"
    ),

    "IsNonContract": (
        "Boolean — true means the building is excluded from standard service contracts. "
        "Example: 'true','false'"
    ),

    "IsDefault": (
        "Boolean — true means this is the default building for its locality. "
        "Example: 'true','false'"
    ),

    # --- Auditing ---
    "CreatedTtm": (
        "Timestamp indicating when the building record was created in the system. "
        "Example: '2023-01-15 11:45:00'"
    ),
}
