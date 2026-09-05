"""
Analysis Agent — Metadata Package

Exposes one public helper:

    get_metadata(modules) -> dict
        Returns a merged schema dict containing only the requested modules.
        Each module's schema is loaded from its own file in this package.

This keeps the Analysis Agent's system prompt lean — only the selected
modules' metadata is injected, not the full schema for all modules.

Individual module files:
    assets.py     →  Physical Asset Register
    bdm.py        →  Breakdown / Reactive Maintenance
    ppm.py        →  Planned Preventive Maintenance
    fa.py         →  Facility Audits & Remedial
    sb.py         →  Schedule Bookings
    contracts.py  →  Maintenance Contracts Register
    employees.py  →  Employee / Workforce Register
"""
from app.api.advance.analysis.metadata.assets     import ASSETS_SCHEMA
from app.api.advance.analysis.metadata.bdm        import BDM_SCHEMA
from app.api.advance.analysis.metadata.ppm        import PPM_SCHEMA
from app.api.advance.analysis.metadata.fa         import FA_SCHEMA
from app.api.advance.analysis.metadata.sb         import SB_SCHEMA
from app.api.advance.analysis.metadata.contracts  import CONTRACTS_SCHEMA
from app.api.advance.analysis.metadata.employees  import EMPLOYEES_SCHEMA
from app.api.advance.analysis.metadata.location   import LOCATION_SCHEMA
from app.api.advance.analysis.metadata.building   import BUILDING_SCHEMA
from app.api.advance.analysis.metadata.floor      import FLOOR_SCHEMA
from app.api.advance.analysis.metadata.spot       import SPOT_SCHEMA

# Registry — maps module name → its schema dict
_REGISTRY: dict[str, dict[str, str]] = {
    "assets":    ASSETS_SCHEMA,
    "bdm":       BDM_SCHEMA,
    "ppm":       PPM_SCHEMA,
    "fa":        FA_SCHEMA,
    "sb":        SB_SCHEMA,
    "contracts": CONTRACTS_SCHEMA,
    "employees": EMPLOYEES_SCHEMA,
    "location":  LOCATION_SCHEMA,
    "building":  BUILDING_SCHEMA,
    "floor":     FLOOR_SCHEMA,
    "spot":      SPOT_SCHEMA,
}


def get_metadata(modules: list[str]) -> dict[str, dict[str, str]]:
    """
    Return a schema dict for only the requested modules.

    Unknown module names are silently skipped (same as validation elsewhere).

    Example:
        get_metadata(["bdm", "ppm"])
        → { "bdm": {...}, "ppm": {...} }
    """
    return {mod: _REGISTRY[mod] for mod in modules if mod in _REGISTRY}


# Also expose the full registry for validation / fallback use
MODULE_SCHEMAS = _REGISTRY