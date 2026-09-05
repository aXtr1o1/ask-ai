"""
Analysis Metadata — floor module

Floor Register.
Records represent floors or levels within a specific building.

Field names verified against actual SP response data.
"""

FLOOR_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "FloorCode": (
        "Unique system code assigned to the floor. "
        "Example: 'FL-001','B1'"
    ),

    "FloorName": (
        "Name or description of the floor level. "
        "Example: 'Ground Floor','Basement 1','Level 4'"
    ),

    "BuildingCode": (
        "Code of the building that contains this floor. "
        "Example: 'BLD-001'"
    ),

    "BuildingName": (
        "Name of the building that contains this floor. "
        "Example: 'Bhawan Tower'"
    ),

    "LocalityCode": (
        "Code of the geographic locality where this floor's building resides. "
        "Example: 'LOC-01'"
    ),

    "LocalityName": (
        "Name of the geographic locality. "
        "Example: 'Ajman'"
    ),

    "Remarks": (
        "Free-text remarks or observations about the floor. "
        "Example: 'Restricted access','Maintenance required'"
    ),

    # --- Flags ---
    "IsActive": (
        "Boolean — true means the floor is active and operational. "
        "Example: 'true','false'"
    ),

    "IsDraft": (
        "Boolean — true means the floor record is currently in a draft state. "
        "Example: 'true','false'"
    ),

    "IsNonContract": (
        "Boolean — true means the floor is excluded from standard service contracts. "
        "Example: 'true','false'"
    ),

    "IsDefault": (
        "Boolean — true means this is the default floor for its building. "
        "Example: 'true','false'"
    ),

    # --- Auditing ---
    "CreatedTtm": (
        "Timestamp indicating when the floor record was created in the system. "
        "Example: '2023-01-16 09:20:00'"
    ),
}
