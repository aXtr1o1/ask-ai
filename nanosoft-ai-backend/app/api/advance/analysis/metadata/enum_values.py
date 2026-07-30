"""
FM Enum Values — Single Source of Truth

All categorical (Enum) field values across all modules.
When the analysis agent sets a filter_value, or the execution agent
filters on a field, the value MUST come from this registry.

Update this file when the database enum values change.
"""

MODULE_ENUMS: dict[str, dict[str, list[str]]] = {

    # =========================================================================
    # BDM — Breakdown / Reactive Maintenance
    # =========================================================================
    "bdm": {
        "WoStatus": [
            "Cancelled",
            "Closed",
            "Open",
        ],
        "PriorityName": [
            "Critical",
            "High",
            "Low",
            "Medium",
            "P1 Critical",
            "P2 High",
            "P3 Medium",
            "P4 Low",
        ],
        "ResponseTAT": [
            "NROT",
            "ROT",
            "SNA",
        ],
        "ResolutionTAT": [
            "COT",
            "NCOT",
        ],
        "WoTypeName": [
            "Asset",
            "BMS",
            "Encode Nature",
            "FA",
            "FA (Facility Audits)",
            "General",
            "PM (Preventive Maintenance)",
        ],
        "ComplaintModeName": [
            "BMS",
            "By Call",
            "By Community Portal",
            "By Mail",
            "By Mobile Portal",
            "By Web Portal",
            "Casual Maintenances",
            "FA",
        ],
        "ComplaintTypeName": [
            "Corrective Maintenance",
            "Incident",
            "Proactive",
            "Reactive Maintenance",
            "Service Request",
        ],
    },

    # =========================================================================
    # PPM — Planned Preventive Maintenance
    # =========================================================================
    "ppm": {
        "PPMStatus": [
            "Open",
            "Closed",
        ],
        "PPMStageName": [
            "Defected Asset",
            "Execution Completed",
            "Execution Completed & Closed",
            "Execution Completed & in Approval Process",
            "Open",
            "Preliminary Confirmed & Open",
            "Staff Assigned",
            "Staff Yet to be Allocated",
            "Standby",
            "Technician Assigned",
            "Work in Progress",
        ],
        "FrequencyName": [
            "10000 KMS",
            "ANNUAL",
            "DAILY",
            "HALFYEARLY",
            "MONTHLY",
            "QUARTERLY",
            "WEEKLY",
        ],

        
    },

    # =========================================================================
    # FA — Facility Audits & Remedial
    # =========================================================================
    "fa": {
        
        "FrequencyName": [
            "ANNUAL",
            "DAILY",
            "HALFYEARLY",
            "MONTHLY",
            "QUARTERLY",
            "WEEKLY",
        ],
        "RMStageName": [
            "Facility Audit - Closed",
            "Facility Audit Request Raised",
            "Staf Assigned for Work Execution",
        ],
        "PriorityName": [
            "Critical",
            "High",
            "Low",
            "Medium",
            "P1 Critical",
            "P2 High",
            "P2-High",
            "P3 Medium",
            "P4 Low",
        ],
        "RMCategoryName": [
            "APRON DAILY INSPECTION",
            "Building Exterior Maintenance Checklist",
            "Facility Condition Assessment Template",
            "Pest Control Checks",
        ],
    },

    # =========================================================================
    # SB — Schedule Bookings
    # =========================================================================
    "sb": {
        "FrequencyName": [
            "ANNUAL",
            "DAILY",
            "HALFYEARLY",
            "MONTHLY",
            "QUARTERLY",
            "WEEKLY",
        ],
        "PPMStageName": [
            "Defected Asset",
            "Execution Completed",
            "Execution Completed & Closed",
            "Execution Completed & in Approval Process",
            "Open",
            "Preliminary Confirmed & Open",
            "Staff Assigned",
            "Staff Yet to be Allocated",
            "Standby",
            "Technician Assigned",
            "Work in Progress",
                ],
    },

    # =========================================================================
    # Assets — Physical Asset Register
    # =========================================================================
        "assets": {
            "StatusName": [
                "Online",
                "Offline",
            ],
            "ConditionName": [
                "Bad",
                "CDT",
                "Good",
                "Immobilized",
                "Operational",
                "ULD",
            ],
            "ServiceAreaName": [
                "N/A",
                "SAC012",
                "SCA013",
            ],
            "TradeGroupName": [
                "OWNED",
                "Owned",
                "RENTED",
            ],
            "PriorityName": [
                "Critical",
                "High",
                "Low",
                "Medium",
                "P1 Critical",
                "P2 High",
                "P2-High",
                "P3 Medium",
                "P4 Low",
            ],
        

        "AssetTypeName": [
            "Fixed",
            "Movable",
        ],
    },
}


def get_enums(modules: list[str]) -> dict[str, dict[str, list[str]]]:
    """Return enum values for the requested modules only."""
    return {mod: MODULE_ENUMS[mod] for mod in modules if mod in MODULE_ENUMS}


def get_enum_block(modules: list[str]) -> str:
    """Return a clean, readable string of enum values for prompt injection."""
    selected = get_enums(modules)
    if not selected:
        return "(no enum constraints for selected modules)"

    lines = []
    for mod, fields in selected.items():
        lines.append(f"[{mod.upper()}]")
        for field, values in fields.items():
            vals = ", ".join(f'"{v}"' for v in values)
            lines.append(f"  {field}: {vals}")
        lines.append("")
    return "\n".join(lines).strip()
