"""
Facility Management module functions — re-exported for langchain_service.
"""
from app.tools.assets_tool import ASSETS
from app.tools.ppm_tool import PPM
from app.tools.bdm_tool import BDM
from app.tools.fa_tool import FA
from app.tools.sb_tool import SB
from app.tools.contract_tool import CONTRACT
from app.tools.employee_tool import EMPLOYEE
from app.tools.location_tool import LOCATION
from app.tools.building_tool import BUILDING
from app.tools.floor_tool import FLOOR
from app.tools.spot_tool import SPOT

ASSETS_TOOL_NAME   = "ASSETS"
PPM_TOOL_NAME      = "PPM"
BDM_TOOL_NAME      = "BDM"
FA_TOOL_NAME       = "FA"
SB_TOOL_NAME       = "SB"
CONTRACT_TOOL_NAME = "CONTRACT"
EMPLOYEE_TOOL_NAME = "EMPLOYEE"
LOCATION_TOOL_NAME = "LOCATION"
BUILDING_TOOL_NAME = "BUILDING"
FLOOR_TOOL_NAME    = "FLOOR"
SPOT_TOOL_NAME     = "SPOT"

__all__ = [
    "ASSETS",   "ASSETS_TOOL_NAME",
    "PPM",      "PPM_TOOL_NAME",
    "BDM",      "BDM_TOOL_NAME",
    "FA",       "FA_TOOL_NAME",
    "SB",       "SB_TOOL_NAME",
    "CONTRACT", "CONTRACT_TOOL_NAME",
    "EMPLOYEE", "EMPLOYEE_TOOL_NAME",
    "LOCATION", "LOCATION_TOOL_NAME",
    "BUILDING", "BUILDING_TOOL_NAME",
    "FLOOR",    "FLOOR_TOOL_NAME",
    "SPOT",     "SPOT_TOOL_NAME",
]
