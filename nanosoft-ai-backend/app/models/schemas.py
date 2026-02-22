"""
Pydantic Schemas for LangChain Tools and API Requests
"""
from pydantic import BaseModel, Field
from typing import Optional


# ==========================================
# ✅ LANGCHAIN TOOL INPUT SCHEMAS
# ==========================================

class AssetsInput(BaseModel):
    """Schema for ASSETS tool. user_id is set by the system from the authenticated request; do not ask the user."""
    user_id: Optional[str] = Field(default=None, description="Set by system from authenticated user; never ask the user for this.")
    status: Optional[str] = Field(default=None, description="Asset status")
    asset_tag_no: Optional[str] = Field(default=None, description="Unique asset tag number")
    condition: Optional[str] = Field(default=None, description="Asset condition")
    priority: Optional[str] = Field(default=None, description="Asset priority level")
    asset_type: Optional[str] = Field(default=None, description="Asset type name")
    division: Optional[str] = Field(default=None, description="Division name")
    discipline: Optional[str] = Field(default=None, description="Discipline name")
    locality: Optional[str] = Field(default=None, description="Locality name")
    building: Optional[str] = Field(default=None, description="Building name")
    floor: Optional[str] = Field(default=None, description="Floor name")
    owner: Optional[str] = Field(default=None, description="Asset owner")
    make: Optional[str] = Field(default=None, description="Equipment make")
    model: Optional[str] = Field(default=None, description="Equipment model")
    service_area: Optional[str] = Field(default=None, description="Service area name")
    trade_group: Optional[str] = Field(default=None, description="Trade group name")
    on_hold: Optional[bool] = Field(default=None, description="Is asset on hold")
    is_snagged: Optional[bool] = Field(default=None, description="Is asset snagged")
    is_scraped: Optional[bool] = Field(default=None, description="Is asset scraped")
    enable_ppm: Optional[bool] = Field(default=None, description="PPM enabled")
    enable_bdm: Optional[bool] = Field(default=None, description="BDM enabled")
    barcode: Optional[str] = Field(default=None, description="Asset barcode")
    keyword: Optional[str] = Field(default=None, description="Free text search keyword")
    date_from: Optional[str] = Field(default=None, description="Date from YYYY-MM-DD")
    date_to: Optional[str] = Field(default=None, description="Date to YYYY-MM-DD")
    limit: Optional[int] = Field(default=None, description="Max number of results. Only set if user explicitly asks for a specific number (e.g. 'show 10'). For count/total queries (how many, total), MUST omit — do not set.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless explicitly requested.")


class PPMInput(BaseModel):
    """Schema for PPM tool (Planned Preventive Maintenance). user_id is set by the system; do not ask the user."""
    user_id: Optional[str] = Field(default=None, description="Set by system from authenticated user; never ask the user for this.")
    status: Optional[str] = Field(default=None, description="PPM status")
    stage: Optional[str] = Field(default=None, description="PPM stage name")
    frequency: Optional[str] = Field(default=None, description="Frequency (Monthly/Weekly/etc.)")
    division: Optional[str] = Field(default=None, description="Division name")
    discipline: Optional[str] = Field(default=None, description="Discipline name")
    locality: Optional[str] = Field(default=None, description="Locality name")
    building: Optional[str] = Field(default=None, description="Building name")
    floor: Optional[str] = Field(default=None, description="Floor name")
    contract: Optional[str] = Field(default=None, description="Contract name")
    tech: Optional[str] = Field(default=None, description="Technician name")
    keyword: Optional[str] = Field(default=None, description="Free text search keyword")
    date_from: Optional[str] = Field(default=None, description="Work order date from YYYY-MM-DD")
    date_to: Optional[str] = Field(default=None, description="Work order date to YYYY-MM-DD")
    comp_from: Optional[str] = Field(default=None, description="Completion date from YYYY-MM-DD")
    comp_to: Optional[str] = Field(default=None, description="Completion date to YYYY-MM-DD")
    sla_min: Optional[int] = Field(default=None, description="SLA duration minimum")
    sla_max: Optional[int] = Field(default=None, description="SLA duration maximum")
    limit: Optional[int] = Field(default=None, description="Max number of results. Only set if user explicitly asks for a specific number (e.g. 'show 10'). For count/total queries (how many, total), MUST omit — do not set.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless explicitly requested.")


class BDMInput(BaseModel):
    """Schema for BDM tool (Breakdown Maintenance / Complaints). user_id is set by the system; do not ask the user."""
    user_id: Optional[str] = Field(default=None, description="Set by system from authenticated user; never ask the user for this.")
    status: Optional[str] = Field(default=None, description="Work order status")
    priority: Optional[str] = Field(default=None, description="Priority name")
    stage: Optional[str] = Field(default=None, description="Stage name")
    complaint_type: Optional[str] = Field(default=None, description="Complaint type")
    complaint_mode: Optional[str] = Field(default=None, description="Complaint mode")
    complaint_nature: Optional[str] = Field(default=None, description="Complaint nature")
    wo_type: Optional[str] = Field(default=None, description="Work order type")
    service_type: Optional[str] = Field(default=None, description="Service type")
    division: Optional[str] = Field(default=None, description="Division name")
    discipline: Optional[str] = Field(default=None, description="Discipline name")
    locality: Optional[str] = Field(default=None, description="Locality name")
    building: Optional[str] = Field(default=None, description="Building name")
    floor: Optional[str] = Field(default=None, description="Floor name")
    contract: Optional[str] = Field(default=None, description="Contract name")
    analysis_tech: Optional[str] = Field(default=None, description="Analysis technician name")
    execution_tech: Optional[str] = Field(default=None, description="Execution technician name")
    complainer: Optional[str] = Field(default=None, description="Complainer name")
    keyword: Optional[str] = Field(default=None, description="Free text search keyword")
    date_from: Optional[str] = Field(default=None, description="Complaint date from YYYY-MM-DD")
    date_to: Optional[str] = Field(default=None, description="Complaint date to YYYY-MM-DD")
    completed_from: Optional[str] = Field(default=None, description="Completed date from YYYY-MM-DD")
    completed_to: Optional[str] = Field(default=None, description="Completed date to YYYY-MM-DD")
    limit: Optional[int] = Field(default=None, description="Max number of results. Only set if user explicitly asks for a specific number (e.g. 'show 10'). For count/total queries (how many, total), MUST omit — do not set.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless explicitly requested.")


# ==========================================
# ✅ API REQUEST SCHEMA
# ==========================================

class ChatRequest(BaseModel):
    """Request schema for chat endpoint"""
    query: str
    userId: str
    sessionId: str