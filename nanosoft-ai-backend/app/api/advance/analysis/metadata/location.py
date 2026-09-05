"""
Analysis Metadata — location module

Location Register.
Records represent geographic localities and regional configurations
registered in the facility management system.

Field names verified against actual SP response data.
"""

LOCATION_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "LocalityCode": (
        "Unique code assigned to the locality for system reference. "
        "Example: 'LOC-01','DXB-02'"
    ),

    "LocalityName": (
        "Full geographic name of the locality. "
        "Example: 'Ajman','Bur Dubai'"
    ),

    "LocAddress1": (
        "Primary address or street details of the locality. "
        "Example: 'Sheikh Zayed Road'"
    ),

    "LocAddress2": (
        "Secondary address or landmark details of the locality. "
        "Example: 'Near Metro Station'"
    ),

    "CityCode": (
        "System code representing the city. "
        "Example: 'CTY-01'"
    ),

    "CityName": (
        "Name of the city where the locality resides. "
        "Example: 'Dubai','Abu Dhabi'"
    ),

    "LocalityGroupCode": (
        "Code representing the broader group or region this locality belongs to. "
        "Example: 'GRP-NORTH'"
    ),

    "LocalityGroupName": (
        "Name of the geographic group or region. "
        "Example: 'Northern Emirates'"
    ),

    "AdminLocalityTypeName": (
        "Administrative classification or type of the locality. "
        "Example: 'Commercial Zone','Residential Area'"
    ),

    "Remarks": (
        "Free-text remarks or observations about the locality. "
        "Example: 'Newly added region','Requires survey'"
    ),

    # --- Flags ---
    "IsActive": (
        "Boolean — true means this locality is active and available for assignments. "
        "Example: 'true','false'"
    ),

    "IsDraft": (
        "Boolean — true means the locality configuration is in draft state and pending approval. "
        "Example: 'true','false'"
    ),

    "IsPortalDisplay": (
        "Boolean — true means this locality is visible on the customer portal. "
        "Example: 'true','false'"
    ),

    "IsNonContract": (
        "Boolean — true means this locality is not bound by a standard service contract. "
        "Example: 'true','false'"
    ),

    "IsDefault": (
        "Boolean — true means this is the default locality for the system. "
        "Example: 'true','false'"
    ),

    # --- Auditing ---
    "CreatedTtm": (
        "Timestamp indicating when the locality record was created in the system. "
        "Example: '2023-01-15 10:30:00'"
    ),
}
