from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field
from typing import Optional


# ==========================================
# ✅ REQUEST MODELS
# ==========================================

class AssetRequest(BaseModel):
    """Request schema for assets endpoint"""
    user_id: str
    status: Optional[str] = None
    condition: Optional[str] = None
    priority: Optional[str] = None
    asset_tag_no: Optional[str] = None
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
    on_hold: Optional[bool] = None
    is_snagged: Optional[bool] = None
    is_scraped: Optional[bool] = None
    enable_ppm: Optional[bool] = None
    enable_bdm: Optional[bool] = None
    barcode: Optional[str] = None
    keyword: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class PPMRequest(BaseModel):
    """Request schema for PPM (work orders) endpoint"""
    user_id: str
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
    keyword: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    comp_from: Optional[str] = None
    comp_to: Optional[str] = None
    sla_min: Optional[int] = None
    sla_max: Optional[int] = None
    limit: int = Field(default=20, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class BDMRequest(BaseModel):
    """Request schema for BDM (complaints) endpoint"""
    user_id: str
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
    keyword: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    completed_from: Optional[str] = None
    completed_to: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
