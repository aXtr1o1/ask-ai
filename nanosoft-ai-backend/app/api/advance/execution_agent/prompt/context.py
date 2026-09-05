"""
Execution Agent — Module Relationship Context

Purpose:
    Provides a ready-to-inject prompt block that describes the exact
    relationships between the 11 FM modules.

    The Execution Agent uses this to understand how data from one module
    connects to data from another — so it can reason across modules,
    group results correctly, and give a complete, accurate answer.

Usage:
    from app.api.advance.execution_agent.context import MODULE_RELATIONSHIP_CONTEXT
    # Inject MODULE_RELATIONSHIP_CONTEXT into the Execution Agent system prompt.
"""

# =============================================================================
# MODULE_RELATIONSHIP_CONTEXT
# A plain-language description of every cross-module relationship.
# Written to be injected directly into the Execution Agent's system prompt.
# =============================================================================

MODULE_RELATIONSHIP_CONTEXT = """\
════════════════════════════════════════════════
FM MODULE RELATIONSHIPS
════════════════════════════════════════════════
The FM system has 11 modules. Understanding how they relate to each other
is essential for interpreting data correctly across multiple modules.

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

  [location → building → floor → spot]
    Link: spot.FloorCode = floor.FloorCode
          spot.BuildingCode = floor.BuildingCode = building.BuildingCode
          spot.LocalityCode = floor.LocalityCode = building.LocalityCode = location.LocalityCode

  [assets / bdm / ppm / fa / sb → location / building / floor / spot]
    Link: Operational modules link to the hierarchy via name matching:
          (assets, bdm, ppm, fa, sb).LocalityName = location.LocalityName
          (assets, bdm, ppm, fa, sb).BuildingName = building.BuildingName
          (assets, bdm, ppm, fa, sb).FloorName = floor.FloorName
          (assets, bdm, ppm, fa, sb).SpotName = spot.SpotName

  [bdm → assets]                                    
    Link: bdm.AssetTagNo = assets.AssetTagNo
          bdm.AssetBarcode = assets.AssetBarcode
    Condition: assets.EnableBDM = true

  [ppm → assets]                                    
    Link: ppm.AssetTagNo = assets.AssetTagNo
          ppm.EquipmentRefNo = assets.EquipmentRefNo
    Condition: assets.EnablePPM = true

  [bdm → contracts]                                 
    Link: bdm.ContractName = contracts.ContractName
    Condition: contracts.IsBDM = true

  [ppm → contracts]                                 
    Link: ppm.ContractName = contracts.ContractName
    Condition: contracts.IsPPM = true

  [fa → contracts]                                  
    Link: fa.ContractName = contracts.ContractName
          fa.ContractCode = contracts.ContractCode

  [sb → contracts]                                  
    Link: sb.ContractName = contracts.ContractName
          sb.ContractCode = contracts.ContractCode

  [bdm → employees]
    Link: bdm.AnalysisTechName ≈ employees.EmployeeFullName  (analysis phase)
          bdm.ExecutionTechName ≈ employees.EmployeeFullName  (execution phase)

  [ppm → employees]
    Link: ppm.PMTechName ≈ employees.EmployeeFullName

  [fa → employees]
    Link: fa.RMTechName ≈ employees.EmployeeFullName

  [sb → employees]
    Link: sb.SBTechName ≈ employees.EmployeeFullName

── ASSET CAPABILITY FLAGS (on assets module) ─────────────────────────────────
  assets.IsEnablePPM = true  → PPM work orders can be created for this asset.
  assets.IsEnableBDM = true  → BDM complaints can be raised for this asset.

── CONTRACT CAPABILITY FLAGS (on contracts module) ───────────────────────────
  contracts.IsPPM = true  → This contract covers Planned Preventive Maintenance.
  contracts.IsBDM = true  → This contract covers Breakdown Maintenance.

── MODULE SELECTION COMPLETENESS ───────────────────────────────────────────
  A question can ask for multiple distinct attributes of the same specific
  thing at once — an identity together with a metric about it, for instance.
  Whichever module is chosen has to carry all of those attributes together in
  the same record, not just some of them — a module missing one of the needed
  fields cannot connect the pieces on its own, regardless of how relevant its
  other fields look. The field list given per module is what determines this.

── CHAINED LOOKUPS AND NARROWED SCOPE ──────────────────────────────────────
  A question can narrow its scope in stages — identifying something from one
  signal, then using that as the basis for a further lookup. The narrowing
  came from whatever specific signal produced it, not just from the broader
  thing it landed on — carrying only the broader result forward into the next
  step, while dropping the signal that produced it, answers a broader question
  than the one actually being narrowed down to.
"""
