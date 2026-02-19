from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────────────────────
# SHARED RESPONSE
# ─────────────────────────────────────────────────────────────────────────────

class StandardResponse(BaseModel):
    p_list: list[dict[str, Any]] = Field(default_factory=list)
    p_count: int = 0

# ─────────────────────────────────────────────────────────────────────────────
# ASSET REQUEST
# ─────────────────────────────────────────────────────────────────────────────

class AssetRequest(BaseModel):
    user_id: int
    
    # Text Filters
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

    # Boolean Flags
    on_hold: Optional[bool] = None
    is_snagged: Optional[bool] = None
    is_scraped: Optional[bool] = None
    enable_ppm: Optional[bool] = None
    enable_bdm: Optional[bool] = None

    # Search
    barcode: Optional[str] = None  # Added to match new SQL
    keyword: Optional[str] = None

    # Date Range
    date_from: Optional[str] = None
    date_to: Optional[str] = None

    # Pagination
    limit: int = Field(20, ge=1, le=1000)
    offset: int = Field(0, ge=0)

# ─────────────────────────────────────────────────────────────────────────────
# BDM REQUEST
# ─────────────────────────────────────────────────────────────────────────────

class BDMRequest(BaseModel):
    user_id: int

    # Text Filters
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

    # Search
    keyword: Optional[str] = None

    # Date Ranges
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    completed_from: Optional[str] = None
    completed_to: Optional[str] = None

    # Pagination
    limit: int = Field(20, ge=1, le=1000)
    offset: int = Field(0, ge=0)

# ─────────────────────────────────────────────────────────────────────────────
# PPM REQUEST
# ─────────────────────────────────────────────────────────────────────────────

class PPMRequest(BaseModel):
    user_id: int

    # Text Filters
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

    # Search
    keyword: Optional[str] = None

    # Date Ranges
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    comp_from: Optional[str] = None
    comp_to: Optional[str] = None

    # SLA Duration
    sla_min: Optional[int] = Field(None, ge=0)
    sla_max: Optional[int] = Field(None, ge=0)

    # Pagination
    limit: int = Field(20, ge=1, le=1000)
    offset: int = Field(0, ge=0)