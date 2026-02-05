# schemas.py
# ==========================================
# Tool Input Schemas for LangChain Tool Calling
# ==========================================

from pydantic import BaseModel, Field
from typing import Optional, List


# ==========================================
# ✅ ASSETS TOOL SCHEMA
# ==========================================

class AssetsInput(BaseModel):
    """
    Schema for ASSETS tool.

    Used when user asks about equipment/assets in facility.

    Example Queries:
    - List assets in Floor 2
    - Show HVAC assets near generator room
    - Assets with status = Active
    """

    division: Optional[str] = Field(default=None, description="Division name")
    discipline: Optional[str] = Field(default=None, description="Discipline name")
    location: Optional[str] = Field(default=None, description="Locality/Location name")

    make: Optional[str] = Field(default=None, description="Equipment make")
    model: Optional[str] = Field(default=None, description="Equipment model")

    status: Optional[str] = Field(default=None, description="Asset status")
    condition: Optional[str] = Field(default=None, description="Asset condition")
    priority: Optional[str] = Field(default=None, description="Asset priority level")

    floor: Optional[List[str]] = Field(
        default=None,
        description="List of floors (example: ['2','3'])"
    )

    spot: Optional[List[str]] = Field(
        default=None,
        description="List of spots/areas (example: ['generator room','garden'])"
    )

    year_from: Optional[int] = Field(default=None, description="Manufacturing year start")
    year_to: Optional[int] = Field(default=None, description="Manufacturing year end")

    output_type: str = Field(default="LIST", description="LIST or COUNT")
    limit: int = Field(default=20, description="Max number of results")


# ==========================================
# ✅ COMPLAINTS TOOL SCHEMA
# ==========================================

class ComplaintsInput(BaseModel):
    """
    Schema for COMPLAINTS tool.

    Used when user asks about breakdown complaints.

    Example Queries:
    - Show open complaints
    - Complaints in Building A
    - SLA check for Complaint ID
    """

    status: Optional[str] = Field(default=None, description="Complaint status")
    priority: Optional[str] = Field(default=None, description="Complaint priority")

    nature: Optional[str] = Field(default=None, description="Complaint nature/type")
    building: Optional[str] = Field(default=None, description="Building name")

    date_from: Optional[str] = Field(default=None, description="Start date YYYY-MM-DD")
    date_to: Optional[str] = Field(default=None, description="End date YYYY-MM-DD")

    check_sla_for_id: Optional[str] = Field(
        default=None,
        description="Work order/Complaint number for SLA check"
    )

    output_type: str = Field(default="LIST", description="LIST or COUNT")
    limit: int = Field(default=20, description="Max number of complaints returned")


# ==========================================
# ✅ WORK ORDERS TOOL SCHEMA
# ==========================================

class WorkOrdersInput(BaseModel):
    """
    Schema for WORK_ORDERS tool.

    Used when user asks about PPM / scheduled maintenance.

    Example Queries:
    - Open PPM work orders
    - Monthly work orders assigned to technician Ravi
    """

    status: Optional[str] = Field(default=None, description="Work order status")
    frequency: Optional[str] = Field(default=None, description="Frequency like Monthly/Weekly")

    tech_name: Optional[str] = Field(default=None, description="Technician name")

    date_from: Optional[str] = Field(default=None, description="Start date YYYY-MM-DD")
    date_to: Optional[str] = Field(default=None, description="End date YYYY-MM-DD")

    output_type: str = Field(default="LIST", description="LIST or COUNT")
    limit: int = Field(default=20, description="Max number of work orders returned")
