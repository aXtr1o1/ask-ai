"""
Analysis Agent — Mandatory Fields Registry

Purpose:
    Defines the cross-module relationship fields that MUST always be present
    in filter_fields for each module, regardless of what the LLM selects.

Why:
    The Execution Agent needs these fields to:
      - Relate records across modules (e.g. BDM → Asset, BDM → Contract)
      - Provide location context (Locality → Building → Floor → Spot)
      - Identify who did the work (technician names)
      - Identify what was worked on (asset identifiers)

    Without these fields, the retrieval layer trims them out and the
    Execution Agent receives disconnected, context-free data.

Injection Logic (in agent.py):
    After the LLM builds filter_fields:
    - If a mandatory field is ALREADY selected by the LLM  → skip (don't duplicate)
    - If a mandatory field is MISSING from LLM's selection → inject it
      with its description taken from the module's metadata schema (MODULE_SCHEMAS)

Field selection rationale per module:
    assets    → AssetTagNo (PK), location spine, division/discipline (classification)
    bdm       → ComplaintNo (PK), AssetTagNo (→ assets), ContractName (→ contracts),
                location spine, division/discipline, tech names (→ employees)
    ppm       → WorkOrder (PK), AssetTagNo (→ assets), EquipmentRefNo (→ assets),
                ContractName (→ contracts), location spine, division/discipline
    fa        → RMComplaintNo (PK), ContractName (→ contracts),
                location spine, division
    sb        → SBCreWorkOrder (PK), ContractName (→ contracts),
                location spine, division/discipline
    contracts → ContractCode (PK), ContractName (used as FK in all work modules)
    employees → EmployeeCode (PK), EmployeeFullName, DesignationName
    location  → LocalityCode (PK), LocalityName
    building  → BuildingCode (PK), BuildingName, plus parent Location codes/names
    floor     → FloorCode (PK), FloorName, plus parent Building/Location codes/names
    spot      → SpotCode (PK), SpotName, plus parent Floor/Building/Location codes/names
"""

# =============================================================================
# MANDATORY_FIELDS
# Key   : module name (must match keys in MODULE_SCHEMAS)
# Value : list of field names that MUST always appear in filter_fields
#         All field names here MUST exist in the corresponding module's schema.
# =============================================================================
MANDATORY_FIELDS: dict[str, list[str]] = {

    # Physical Asset Register
    # PK + location spine + classification (used as FK target by bdm/ppm)
    "assets": [
        "AssetTagNo",           # PK — referenced by bdm.AssetTagNo, ppm.AssetTagNo
        "EquipmentName",        # human-readable asset name
        "DivisionName",         # classification — shared across all work modules
        "DisciplineName",       # sub-classification — shared across work modules
        "LocalityName",         # location spine level 1
        "BuildingName",         # location spine level 2
        "FloorName",            # location spine level 3
        "SpotName",             # location spine level 4
    ],

    # Breakdown / Reactive Maintenance
    # PK + FK to assets + FK to contracts + location + personnel
    "bdm": [
        "ComplaintNo",          # PK — unique work order identifier
        "AssetTagNo",           # FK → assets.AssetTagNo
        "ContractName",         # FK → contracts.ContractName
        "DivisionName",         # classification
        "DisciplineName",       # sub-classification
        "LocalityName",         # location spine level 1
        "BuildingName",         # location spine level 2
        "FloorName",            # location spine level 3
        "SpotName",             # location spine level 4
        "AnalysisTechName",     # FK → employees (who analysed)
        "ExecutionTechName",    # FK → employees (who executed)
    ],

    # Planned Preventive Maintenance
    # PK + FK to assets + FK to contracts + location + personnel
    "ppm": [
        "WorkOrder",            # PK — unique PPM work order identifier
        "AssetTagNo",           # FK → assets.AssetTagNo
        "EquipmentRefNo",       # FK → assets.EquipmentRefNo (alternate asset link)
        "ContractName",         # FK → contracts.ContractName
        "EquipmentName",        # human-readable asset name
        "DivisionName",         # classification
        "DisciplineName",       # sub-classification
        "LocalityName",         # location spine level 1
        "BuildingName",         # location spine level 2
        "FloorName",            # location spine level 3
        "SpotName",             # location spine level 4
        "PMTechName",           # FK → employees (who did the PPM)
    ],

    # Facility Audits & Remedial
    # PK + FK to contracts + location + personnel
    "fa": [
        "RMComplaintNo",        # PK — unique audit/remedial identifier
        "ContractName",         # FK → contracts.ContractName
        "DivisionName",         # classification
        "LocalityName",         # location spine level 1
        "BuildingName",         # location spine level 2
        "FloorName",            # location spine level 3
        "SpotName",             # location spine level 4
        "RMTechName",           # FK → employees (who executed the audit)
    ],

    # Schedule Bookings (Housekeeping)
    # PK + FK to contracts + location + personnel
    "sb": [
        "SBCreWorkOrder",       # PK — unique schedule booking identifier
        "ContractName",         # FK → contracts.ContractName
        "DivisionName",         # classification
        "DisciplineName",       # sub-classification
        "LocalityName",         # location spine level 1
        "BuildingName",         # location spine level 2
        "FloorName",            # location spine level 3
        "SpotName",             # location spine level 4
        "SBTechName",           # FK → employees (who performed the booking)
    ],

    # Maintenance Contracts Register
    # PK + ContractName (used as FK in all work modules)
    "contracts": [
        "ContractCode",         # PK — unique contract identifier
        "ContractName",         # FK target — referenced by bdm/ppm/fa/sb
        "CustomerName",         # who the contract is with
        "ContStStatus",         # current contract status
    ],

    # Employee / Workforce Register
    # PK + name + role (referenced by bdm/ppm/fa/sb tech name fields)
    "employees": [
        "EmployeeCode",         # PK — unique employee identifier
        "EmployeeFullName",     # FK target — matched against TechName fields
        "DesignationName",      # role (Technician, Supervisor, Engineer, etc.)
        "DepartmentName",       # which department this employee belongs to
    ],

    # Locality Register (Parent Node)
    # PK + Name
    "location": [
        "LocalityCode",
        "LocalityName",
    ],

    # Building Register (Parent Node)
    # PK + Name + Parent Spine
    "building": [
        "BuildingCode",
        "BuildingName",
        "LocalityCode",
        "LocalityName",
    ],

    # Floor Register (Parent Node)
    # PK + Name + Parent Spine
    "floor": [
        "FloorCode",
        "FloorName",
        "BuildingCode",
        "BuildingName",
        "LocalityCode",
        "LocalityName",
    ],

    # Spot Register (Parent Node)
    # PK + Name + Parent Spine
    "spot": [
        "SpotCode",
        "SpotName",
        "FloorCode",
        "FloorName",
        "BuildingCode",
        "BuildingName",
        "LocalityCode",
        "LocalityName",
    ],
}
