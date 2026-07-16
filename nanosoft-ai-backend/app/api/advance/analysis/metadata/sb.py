"""
Analysis Metadata — sb module

Schedule Booking (Housekeeping / Cleanliness Inspections).
Records represent pre-scheduled service bookings and cleanliness
inspection tasks at specific location spots.
"""

SB_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "SBRequestNo": (
        "Unique schedule booking request number identifying this SB record. "
        "Primary reference ID. Example: 'SB-2026-001'."
    ),

    # --- Classification ---
    "SBStatus": (
        "Current lifecycle status of the schedule booking. "
        "Known values: 'Open' (booking is scheduled or in progress, not yet completed), "
        "'Closed' (booking has been completed and closed). "
        "Filter on 'Open' to find active or upcoming bookings."
    ),
    "SBStageName": (
        "Detailed workflow stage of the schedule booking. "
        "Example: 'Service Booking Raised' (booking created, awaiting technician assignment). "
        "More granular than SBStatus."
    ),
    "SBTypeName": (
        "Type of the schedule booking defining the nature of the service. "
        "Example: 'Scheduled Service' (a pre-planned, recurring service visit)."
    ),
    "PriorityName": (
        "Priority level of the booking. "
        "Known values: 'P1 Critical', 'P2 High', 'P3 Medium', 'P4 Low'. "
        "Reflects the urgency of carrying out the booked service on time."
    ),
    "ServiceTypeName": (
        "Category of service being performed under this booking. "
        "Example: 'Air Conditioning Services'. "
        "Use to filter bookings by the type of work being scheduled."
    ),
    "DivisionName": (
        "Service division responsible for delivering this booked service. "
        "Example: 'HVAC System'."
    ),
    "ContractName": (
        "Maintenance contract under which this booking is scheduled. "
        "Example: 'Facility Management Residential Area'."
    ),

    # --- Personnel ---
    "RequestedBy": (
        "Username or name of the person who created and submitted this booking. "
        "Example: 'admin'."
    ),
    "TechName": (
        "Name of the technician assigned to carry out this scheduled visit. "
        "Null if no technician has been assigned yet."
    ),

    # --- Location ---
    "LocalityName": (
        "Geographic locality or area where the booking is to be performed. "
        "Example: 'Doha'."
    ),
    "BuildingName": (
        "Building or property where the scheduled service will take place. "
        "Example: 'Building 1 - Residential High Rise'."
    ),
    "FloorName": (
        "Floor level within the building for this booking. "
        "Example: 'Floor 3'."
    ),
    "SpotName": (
        "Specific spot, apartment, room, or zone where the service will be delivered. "
        "Example: 'Appartement-30'. For cleanliness inspections this is the inspected location."
    ),

    # --- Timestamps ---
    "BookedDateTime": (
        "Date and time when the booking was registered in the system. "
        "Format: 'DD-MM-YYYY HH:MM:SS'. Represents when the request was created."
    ),
    "ScheduledDateTime": (
        "Planned date and time when the service is scheduled to be delivered. "
        "Format: 'DD-MM-YYYY HH:MM:SS'. Used to track upcoming appointments."
    ),
    "CompletedDateTime": (
        "Date and time when the booked service was actually completed. "
        "Null for open bookings that have not yet been delivered."
    ),

    # --- Notes ---
    "Remarks": (
        "Free-text remarks, notes, or special instructions related to this booking. "
        "Example: 'Annual AC service booking for apartment block'."
    ),
}
