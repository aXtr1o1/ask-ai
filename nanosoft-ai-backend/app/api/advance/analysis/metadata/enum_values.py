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
            "Open",
            "Closed",
        ],
        "PriorityName": [
            "P1 Critical",
            "P2 High",
            "P3 Medium",
            "P4 Low",
        ],
        "ResponseTAT": [
            "ROT",   # Responded On Time — SLA met
            "NROT",  # Not Responded On Time — response SLA breached
        ],
        "ResolutionTAT": [
            "COT",   # Closed On Time — resolved within SLA
            "SNA",   # SLA Not Achieved — resolution breached SLA
        ],
        "ComplaintModeName": [
            "By Call",
            "By Mail",
            "By Mobile Portal",
            "By Web Portal",
        ],
        "ComplaintTypeName": [
            "Service Request",
            "Corrective Maintenance",
            "Emergency",
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
        "FrequencyName": [
            "MONTHLY",
            "QUARTERLY",
            "HALFYEARLY",
            "ANNUAL",
        ],
    },

    # =========================================================================
    # FA — Facility Audits & Remedial
    # =========================================================================
    "fa": {
        "PriorityName": [
            "P1 Critical",
            "P2 High",
            "P3 Medium",
            "P4 Low",
        ],
        "FrequencyName": [
            "MONTHLY",
            "QUARTERLY",
            "HALFYEARLY",
            "ANNUAL",
        ],
    },

    # =========================================================================
    # SB — Schedule Bookings
    # =========================================================================
    "sb": {
        "FrequencyName": [
            "MONTHLY",
            "QUARTERLY",
            "HALFYEARLY",
            "ANNUAL",
        ],
        "PPMStageName": [
            "Staff Yet to be Allocated",
            "Technician Assigned",
            "Execution Completed & Closed",
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
            "Good",
            "Fair",
            "Bad",
        ],
        "PriorityName": [
            "P1 Critical",
            "P2 High",
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
