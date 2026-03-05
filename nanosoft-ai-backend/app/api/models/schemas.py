from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ==========================================
# ✅ REQUEST MODELS
# ==========================================

class AssetRequest(BaseModel):
    """Request schema for assets endpoint"""
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    asset_tag_no: Optional[str] = None
    status: Optional[str] = None
    condition: Optional[str] = None
    priority: Optional[str] = None
    asset_type: Optional[str] = None
    division: Optional[str] = None
    discipline: Optional[str] = None
    locality: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    owner: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    service_area: Optional[str] = None
    trade_group: Optional[str] = None
    spot_name: Optional[str] = None       
    serial_no: Optional[str] = None       
    on_hold: Optional[bool] = None
    is_snagged: Optional[bool] = None
    is_scraped: Optional[bool] = None
    enable_ppm: Optional[bool] = None
    enable_bdm: Optional[bool] = None
    keyword: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: Optional[int] = None
    offset: int = Field(default=0, ge=0)


class PPMRequest(BaseModel):
    """Request schema for PPM (planned preventive maintenance) endpoint"""
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    work_order: Optional[str] = None
    asset_tag_no: Optional[str] = None
    status: Optional[str] = None
    stage: Optional[str] = None
    frequency: Optional[str] = None
    division: Optional[str] = None
    discipline: Optional[str] = None
    locality: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    contract: Optional[str] = None
    tech: Optional[str] = None
    equipment: Optional[str] = None
    spot_name: Optional[str] = None       
    keyword: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    comp_from: Optional[str] = None
    comp_to: Optional[str] = None
    sla_min: Optional[int] = None
    sla_max: Optional[int] = None
    limit: Optional[int] = None
    offset: int = Field(default=0, ge=0)


class BDMRequest(BaseModel):
    """Request schema for BDM (breakdown maintenance / complaints) endpoint"""
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    complaint_no: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    stage: Optional[str] = None
    complaint_type: Optional[str] = None
    complaint_mode: Optional[str] = None
    complaint_nature: Optional[str] = None
    wo_type: Optional[str] = None
    service_type: Optional[str] = None
    division: Optional[str] = None
    discipline: Optional[str] = None
    locality: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    contract: Optional[str] = None
    analysis_tech: Optional[str] = None
    execution_tech: Optional[str] = None
    complainer: Optional[str] = None
    spot_name: Optional[str] = None       
    keyword: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    completed_from: Optional[str] = None
    completed_to: Optional[str] = None
    limit: Optional[int] = None
    offset: int = Field(default=0, ge=0)