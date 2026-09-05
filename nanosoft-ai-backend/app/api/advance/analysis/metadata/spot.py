"""
Analysis Metadata — spot module

Spot Register.
Records represent specific spots, zones, or parking spaces within a floor.

Field names verified against actual SP response data.
"""

SPOT_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "SpotCode": (
        "Unique system code assigned to the spot. "
        "Example: 'SP-104','PK-05'"
    ),

    "SpotName": (
        "Name or description of the specific spot. "
        "Example: 'Appartement-90','Parking Bay 5','Server Room'"
    ),

    "BuildingCode": (
        "Code of the building that contains this spot. "
        "Example: 'BLD-001'"
    ),

    "BuildingName": (
        "Name of the building that contains this spot. "
        "Example: 'Bhawan Tower'"
    ),

    "FloorCode": (
        "Code of the floor that contains this spot. "
        "Example: 'FL-09'"
    ),

    "FloorName": (
        "Name of the floor that contains this spot. "
        "Example: 'Floor 9'"
    ),

    "LocalityCode": (
        "Code of the geographic locality where this spot resides. "
        "Example: 'LOC-01'"
    ),

    "LocalityName": (
        "Name of the geographic locality. "
        "Example: 'Ajman'"
    ),

    "SpotTypeName": (
        "Classification or type of the spot. "
        "Example: 'Residential Unit','Commercial Shop','Parking Space'"
    ),

    "Remarks": (
        "Free-text remarks or observations about the spot. "
        "Example: 'Reserved for VIP','Under maintenance'"
    ),

    # --- Flags ---
    "IsActive": (
        "Boolean — true means the spot is active and operational. "
        "Example: 'true','false'"
    ),

    "IsDraft": (
        "Boolean — true means the spot record is in a draft state. "
        "Example: 'true','false'"
    ),

    "IsOccupancy": (
        "Boolean — true means the spot is currently occupied or leased. "
        "Example: 'true','false'"
    ),

    "IsParking": (
        "Boolean — true means this spot is specifically designated for parking. "
        "Example: 'true','false'"
    ),

    "IsAllocated": (
        "Boolean — true means the spot has been allocated to a specific user or asset. "
        "Example: 'true','false'"
    ),

    "IsNonContract": (
        "Boolean — true means the spot is excluded from standard service contracts. "
        "Example: 'true','false'"
    ),

    # --- Auditing ---
    "CreatedTtm": (
        "Timestamp indicating when the spot record was created in the system. "
        "Example: '2023-01-16 14:30:00'"
    ),
}
