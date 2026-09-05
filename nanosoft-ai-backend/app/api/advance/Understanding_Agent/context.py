"""
Understanding Agent — Module Relationship Context

Purpose:
    Provides a ready-to-inject prompt block that describes the exact
    relationships between the 11 FM modules.

    The Understanding Agent uses this to understand how data from one module
    connects to data from another, enabling it to correctly select all required
    modules when a query spans across multiple domains (e.g., parent and child nodes).
"""

# =============================================================================
# MODULE_RELATIONSHIP_CONTEXT
# A plain-language description of every cross-module relationship.
# Written to be injected directly into the Understanding Agent's system prompt.
# =============================================================================

MODULE_RELATIONSHIP_CONTEXT = """\
════════════════════════════════════════════════
FM MODULE RELATIONSHIPS
════════════════════════════════════════════════
The FM system has 11 modules. Understanding how they relate to each other
is essential for selecting all required modules when a user's query spans multiple domains.
Do not map field joins; just know these conceptual connections exist.

── MODULES OVERVIEW ──────────────────────────────────────────────────────────
  (Parent Nodes)
  location  : Locality Register — regions and broad geographic zones.
  building  : Building Register — buildings within a locality.
  floor     : Floor Register — floors within a building.
  spot      : Spot Register — specific areas or parking spaces within a floor.
  
  (Child Nodes)
  assets    : Physical Asset Register — every physical equipment in the facility.
  bdm       : Breakdown Maintenance — reactive work orders when equipment fails.
  ppm       : Planned Preventive Maintenance — scheduled routine maintenance tasks.
  fa        : Facility Audits & Remedial — audit tasks, snag inspections, walkthroughs.
  sb        : Schedule Bookings — pre-scheduled housekeeping and service bookings.
  contracts : Maintenance Contracts Register — all contracts and service agreements.
  employees : Employee / Workforce Register — all staff, technicians, supervisors.

── CROSS-MODULE RELATIONSHIPS ─────────────────────────────────────────────────

  [Parent Node Hierarchy]
    location → building → floor → spot
    This chain is a true structural hierarchy (each level is directly linked
    to the one above it), not just a naming convention. If a query relates
    to a specific area but requests details down to the spot, include the
    relevant parent nodes.

  [Child Nodes → Parent Nodes]
    assets, bdm, ppm, fa, sb  →  location, building, floor, spot
    If a user asks about maintenance or assets at a specific building, floor, or location, select BOTH the operational module and the corresponding parent node modules.

  [Child Nodes → Child Nodes]
    bdm → assets      : Breakdown maintenance is raised on physical assets.
    ppm → assets      : Preventive maintenance schedules apply to physical assets.
    
    bdm → contracts   : Breakdown maintenance can be covered by specific contracts.
    ppm → contracts   : Preventive maintenance can be covered by specific contracts.
    fa  → contracts   : Audits and remedial work can fall under a contract.
    sb  → contracts   : Schedule bookings can belong to a contract.

    bdm, ppm, fa, sb → employees : Maintenance and audit tasks are assigned to and executed by employees/technicians.

── ASSET CAPABILITY FLAGS ────────────────────────────────────────────────────
  Assets have flags to indicate if they support PPM or BDM. If a query asks about an asset's capability to have work orders, include the 'assets' module.

── CONTRACT CAPABILITY FLAGS ─────────────────────────────────────────────────
  Contracts have flags for IsPPM and IsBDM. If a query asks what type of work a contract covers, include the 'contracts' module.
"""