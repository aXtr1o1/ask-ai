from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, validator
from typing import Optional, List

# ==========================================
# ✅ REQUEST MODELS
# ==========================================

_SMART_PUNCTUATION_TRANSLATION = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201A": "'",
    "\u201B": "'",
    "\u201C": '"',
    "\u201D": '"',
    "\u201E": '"',
    "\u201F": '"',
})


def _normalize_smart_punctuation(value):
    if isinstance(value, str):
        return value.translate(_SMART_PUNCTUATION_TRANSLATION)
    return value


class AssetRequest(BaseModel):
    """Request schema for assets endpoint"""
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    asset_tag_no: Optional[str] = None
    asset_barcode: Optional[str] = None       # NEW
    equipment_name: Optional[str] = None      # NEW
    equipment_ref_no: Optional[str] = None    # NEW
    serial_no: Optional[str] = None
    status: Optional[str] = None
    condition: Optional[str] = None
    priority: Optional[str] = None
    asset_type: Optional[str] = None
    division: Optional[str] = None
    discipline: Optional[str] = None
    locality: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    spot_name: Optional[str] = None
    owner: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    service_area: Optional[str] = None
    trade_group: Optional[str] = None
    drawing_no: Optional[str] = None          # NEW
    remarks: Optional[str] = None             # NEW
    on_hold: Optional[bool] = None
    is_snagged: Optional[bool] = None
    is_scraped: Optional[bool] = None
    enable_ppm: Optional[bool] = None
    enable_bdm: Optional[bool] = None
    enable_bms: Optional[bool] = None         # NEW
    enable_dsm: Optional[bool] = None         # NEW
    keyword: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: Optional[int] = None
    offset: int = Field(default=0, ge=0)
    is_aggregate: Optional[bool] = Field(default=False)
    group_by_columns: Optional[List[str]] = Field(default=None)
    aggregate_function: Optional[str] = Field(default=None)


class PPMRequest(BaseModel):
    """Request schema for PPM (planned preventive maintenance) endpoint"""
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    work_order: Optional[str] = None
    asset_tag_no: Optional[str] = None
    equipment_ref_no: Optional[str] = None    # NEW
    status: Optional[str] = None
    stage: Optional[str] = None
    frequency: Optional[str] = None
    division: Optional[str] = None
    discipline: Optional[str] = None
    locality: Optional[str] = None
    locality_code: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    spot_name: Optional[str] = None
    equipment: Optional[str] = None
    contract: Optional[str] = None
    tech: Optional[str] = None
    keyword: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    comp_from: Optional[str] = None
    comp_to: Optional[str] = None
    sla_min: Optional[int] = None
    sla_max: Optional[int] = None
    limit: Optional[int] = None
    offset: int = Field(default=0, ge=0)
    is_aggregate: Optional[bool] = Field(default=False)
    group_by_columns: Optional[List[str]] = Field(default=None)
    aggregate_function: Optional[str] = Field(default=None)


class BDMRequest(BaseModel):
    """Request schema for BDM (breakdown maintenance / complaints) endpoint"""
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    complaint_no: Optional[str] = None
    asset_tag_no: Optional[str] = None        # NEW
    asset_barcode: Optional[str] = None       # NEW
    client_wo_no: Optional[str] = None        # NEW
    status: Optional[str] = None
    priority: Optional[str] = None
    stage: Optional[str] = None
    complaint_type: Optional[str] = None
    complaint_header: Optional[str] = None    # NEW
    complaint_mode: Optional[str] = None
    complaint_nature: Optional[str] = None
    wo_type: Optional[str] = None
    service_type: Optional[str] = None
    division: Optional[str] = None
    discipline: Optional[str] = None
    locality: Optional[str] = None
    locality_code: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    spot_name: Optional[str] = None
    contract: Optional[str] = None
    complainer: Optional[str] = None
    register_by: Optional[str] = None         # NEW
    analysis_tech: Optional[str] = None
    execution_tech: Optional[str] = None
    keyword: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    completed_from: Optional[str] = None
    completed_to: Optional[str] = None
    limit: Optional[int] = None
    offset: int = Field(default=0, ge=0)
    is_aggregate: Optional[bool] = Field(default=False)
    group_by_columns: Optional[List[str]] = Field(default=None)
    aggregate_function: Optional[str] = Field(default=None)

    @validator("*", pre=True)
    def normalize_text_fields(cls, value):
        return _normalize_smart_punctuation(value)
    
    
class FARequest(BaseModel):
    """Request schema for FA (Facility Audit / FacilityAudit table) endpoint"""
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    complaint_no: Optional[str] = None        # maps to RMComplaintNo
    complaint_code: Optional[str] = None      # NEW — maps to RMCCMComplaintCode
    x_complaint_no: Optional[str] = None      # NEW — maps to RMXComplaintNo
    priority: Optional[str] = None
    stage: Optional[str] = None               # maps to RMStageName
    category: Optional[str] = None            # maps to RMCategoryName
    category_sub: Optional[str] = None        # maps to RMCategorySubName
    division: Optional[str] = None
    locality: Optional[str] = None
    locality_code: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    spot_name: Optional[str] = None
    contract: Optional[str] = None
    tech: Optional[str] = None                # maps to RMTechName
    frequency: Optional[str] = None
    request_desc: Optional[str] = None        # maps to RMRequestDetailsDesc
    is_withdraw: Optional[bool] = None        # maps to IsRMWithdraw
    is_rework: Optional[bool] = None          # maps to IsRMRework
    is_bms: Optional[bool] = None             # NEW — maps to IsRMBMS
    is_active: Optional[bool] = None
    is_draft: Optional[bool] = None           # NEW — maps to IsDraft
    keyword: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    comp_from: Optional[str] = None           # maps to RMBDMWOCompletedDate
    comp_to: Optional[str] = None
    limit: Optional[int] = None
    offset: int = Field(default=0, ge=0)
    is_aggregate: Optional[bool] = Field(default=False)
    group_by_columns: Optional[List[str]] = Field(default=None)
    aggregate_function: Optional[str] = Field(default=None)
 
 
class SBRequest(BaseModel):
    """Request schema for SB (Schedule Based / ScheduleBased table) endpoint"""
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    work_order: Optional[str] = None          # maps to SBCreWorkOrder
    stage: Optional[str] = None               # maps to PPMStageName
    frequency: Optional[str] = None
    service_type: Optional[str] = None        # NEW — maps to ServiceTypeName
    division: Optional[str] = None
    discipline: Optional[str] = None
    locality: Optional[str] = None
    locality_code: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    spot_name: Optional[str] = None
    contract: Optional[str] = None
    tech: Optional[str] = None                # maps to SBTechName
    is_withdraw: Optional[bool] = None        # NEW — maps to IsSBCreWithDraw
    is_reschedule: Optional[bool] = None      # NEW — maps to IsSbCreReschedule
    is_rework: Optional[bool] = None          # NEW — maps to IsSBCreRework
    is_active: Optional[bool] = None          # NEW — maps to IsActive
    is_draft: Optional[bool] = None           # NEW — maps to IsDraft
    keyword: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    comp_from: Optional[str] = None           # maps to SBCreWoCompletedDate
    comp_to: Optional[str] = None
    sla_min: Optional[float] = None           # maps to SBCreSLAHours (numeric)
    sla_max: Optional[float] = None
    limit: Optional[int] = None
    offset: int = Field(default=0, ge=0)
    is_aggregate: Optional[bool] = Field(default=False)
    group_by_columns: Optional[List[str]] = Field(default=None)
    aggregate_function: Optional[str] = Field(default=None)
