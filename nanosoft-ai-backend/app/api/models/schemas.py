"""
Pydantic Schemas for Database API Endpoints
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


# ==========================================
# ✅ REQUEST MODELS
# ==========================================

class AssetRequest(BaseModel):
    """Request schema for assets endpoint"""
    division: Optional[str] = None
    discipline: Optional[str] = None
    location: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    status: Optional[str] = None
    condition: Optional[str] = None
    priority: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    output_type: str = 'LIST'
    limit: int = Field(default=20, gt=0)


class ComplaintRequest(BaseModel):
    """Request schema for complaints endpoint"""
    status: Optional[str] = None
    priority: Optional[str] = None
    nature: Optional[str] = None
    building: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    check_sla_for_id: Optional[str] = None
    output_type: str = 'LIST'
    limit: int = 20


class WorkOrderRequest(BaseModel):
    """Request schema for work orders endpoint"""
    status: Optional[str] = None
    frequency: Optional[str] = None
    tech_name: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    output_type: str = 'LIST'
    limit: int = 20