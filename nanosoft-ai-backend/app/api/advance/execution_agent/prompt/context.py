"""
Execution Agent — Module Relationship Context

Purpose:
    Provides a ready-to-inject prompt block that describes the exact
    relationships between the 7 FM modules.

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
The FM system has 7 modules. Understanding how they relate to each other
is essential for interpreting data correctly across multiple modules.

── MODULES OVERVIEW ──────────────────────────────────────────────────────────
  assets    : Physical Asset Register — every physical equipment in the facility.
  bdm       : Breakdown Maintenance — reactive work orders when equipment fails.
  ppm       : Planned Preventive Maintenance — scheduled routine maintenance tasks.
  fa        : Facility Audits & Remedial — audit tasks, snag inspections, walkthroughs.
  sb        : Schedule Bookings — pre-scheduled housekeeping and service bookings.
  contracts : Maintenance Contracts Register — all contracts and service agreements.
  employees : Employee / Workforce Register — all staff, technicians, supervisors.

── CROSS-MODULE RELATIONSHIPS ─────────────────────────────────────────────────

  [bdm → assets]
    Link: bdm.AssetTagNo = assets.AssetTagNo
          bdm.AssetBarcode = assets.AssetBarcode

  [ppm → assets]
    Link: ppm.AssetTagNo = assets.AssetTagNo
          ppm.EquipmentRefNo = assets.EquipmentRefNo

  [bdm → contracts]
    Link: bdm.ContractName = contracts.ContractName

  [ppm → contracts]
    Link: ppm.ContractName = contracts.ContractName

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

── LOCATION BACKBONE (shared across all 5 operational modules) ────────────────
  assets, bdm, ppm, fa, and sb all share the same location hierarchy:
    LocalityName → BuildingName → FloorName → SpotName

── ASSET CAPABILITY FLAGS (on assets module) ─────────────────────────────────
  assets.IsEnablePPM = true  → PPM work orders can be created for this asset.
  assets.IsEnableBDM = true  → BDM complaints can be raised for this asset.

── CONTRACT CAPABILITY FLAGS (on contracts module) ───────────────────────────
  contracts.IsPPM = true  → This contract covers Planned Preventive Maintenance.
  contracts.IsBDM = true  → This contract covers Breakdown Maintenance.
"""
