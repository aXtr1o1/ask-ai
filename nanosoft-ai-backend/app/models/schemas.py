"""
Pydantic Schemas for LangChain Tools and API Requests
"""
from pydantic import BaseModel, Field
from typing import Optional, List


# ==========================================
# ✅ LANGCHAIN TOOL INPUT SCHEMAS
# ==========================================

class AssetsInput(BaseModel):
    """Schema for ASSETS tool. Covers physical equipment and master records."""
    user_id: Optional[str] = Field(None, description="Internal system-set ID; strictly mandatory for all queries. Never request this from the user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name; strictly mandatory for all queries. Never request this from the user.")
    asset_tag_no: Optional[str] = Field(None, description="Unique identification number for equipment. Use for tag-based searches. Do not guess value.")
    asset_barcode: Optional[str] = Field(None, description="Asset barcode. Map if user mentions 'Barcode' or 'Asset Barcode'.")
    equipment_name: Optional[str] = Field(None, description="Equipment description name. Map if user mentions 'Equipment Name' or 'EquipmentName'.")
    equipment_ref_no: Optional[str] = Field(None, description="Equipment reference number. Map if user mentions 'Ref No', 'Reference Number', or 'EquipmentRefNo'.")
    serial_no: Optional[str] = Field(None, description="Filter by serial number. Map if user mentions 'Serial', 'Serial No', 'Serial Number', or 'S/N'.")
    status: Optional[str] = Field(None, description="Maps if user mentions 'Status' or 'Status Name'. Mandatory fallback for offline/online states.")
    condition: Optional[str] = Field(None, description="Physical state of asset. Map here if user mentions 'Condition' or 'State'.")
    priority: Optional[str] = Field(None, description="Criticality level of equipment. Map here if user mentions 'Priority' or 'Urgency'.")
    asset_type: Optional[str] = Field(None, description="Category of equipment. Maps if user mentions 'Asset Type', 'Type', or 'AssetTypeName'.")
    division: Optional[str] = Field(None, description="Organizational unit. Maps if user mentions 'Division', 'Division Name', or 'DivisionName'.")
    discipline: Optional[str] = Field(None, description="Technical specialty. Maps if user mentions 'Discipline', 'Discipline Name', or 'DisciplineName'.")
    locality: Optional[str] = Field(None, description="Geographic area or site (e.g. district, complex, community). Do NOT map indoor rooms or common areas here; map them to 'spot_name'.")
    building: Optional[str] = Field(None, description="Specific structure name. Map here if user mentions 'Building' or 'Building Name'.")
    floor: Optional[str] = Field(None, description="Level within building. Map here if user mentions 'Floor' or 'Floor Name'.")
    spot_name: Optional[str] = Field(None, description="Filter by specific room, space, or interior common area (e.g., 'Common Area', 'Lobby', 'Hallway', 'Pantry', 'Corridor'). Map general interior locations here instead of 'locality'.")
    owner: Optional[str] = Field(None, description="Entity responsible for asset. Map here if user mentions 'Owner' or 'Department'.")
    make: Optional[str] = Field(None, description="Equipment manufacturer name. Map here if user mentions 'Make', 'Manufacturer', or 'Brand'.")
    model: Optional[str] = Field(None, description="Specific model designation. Map here if user mentions 'Model' or 'Model Name'.")
    service_area: Optional[str] = Field(None, description="Functional area served. Map here if user mentions 'Service Area' or 'Zone'.")
    trade_group: Optional[str] = Field(None, description="Maintenance team group. Map here if user mentions 'Trade Group' or 'Team'.")
    drawing_no: Optional[str] = Field(None, description="Drawing reference number. Map if user mentions 'Drawing No' or 'Drawing Number'.")
    remarks: Optional[str] = Field(None, description="Asset remarks/notes. Map if user mentions 'Remarks' or 'Notes'.")
    on_hold: Optional[bool] = Field(None, description="FILTER only: set true/false when user wants assets with a specific OnHold value. Do NOT use when user asks 'how many OnHolds' — use is_aggregate=True with group_by_columns=['OnHold'] instead.")
    is_snagged: Optional[bool] = Field(None, description="FILTER only: set true/false for a specific IsSnagged value. For 'how many snagged' breakdown use is_aggregate=True with group_by_columns=['IsSnagged'].")
    is_scraped: Optional[bool] = Field(None, description="FILTER only: set true/false for a specific IsScraped value. For 'how many scraped' breakdown use is_aggregate=True with group_by_columns=['IsScraped'].")
    enable_ppm: Optional[bool] = Field(None, description="FILTER only: set true/false for a specific IsEnablePPM value. For breakdown use is_aggregate=True with group_by_columns=['IsEnablePPM'].")
    enable_bdm: Optional[bool] = Field(None, description="FILTER only: set true/false for a specific IsEnableBDM value. For breakdown use is_aggregate=True with group_by_columns=['IsEnableBDM'].")
    enable_bms: Optional[bool] = Field(None, description="FILTER only: set true/false for BMS enabled assets (IsEnableBMS). Map if user mentions 'BMS' or 'Building Management System'.")
    enable_dsm: Optional[bool] = Field(None, description="FILTER only: set true/false for DSM enabled assets (IsEnableDSM). Map if user mentions 'DSM'.")
    keyword: Optional[str] = Field(None, description="Mandatory fallback ONLY for specific technical terms. Do not use vague conversational words.")
    date_from: Optional[str] = Field(None, description="Start date range. Use YYYY-MM-DD.")
    date_to: Optional[str] = Field(None, description="End date range. Use YYYY-MM-DD.")
    limit: Optional[int] = Field(default=None, description="Max number of results. Only set if user asks for a specific number. For count queries MUST omit.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless requested.")
    is_aggregate: Optional[bool] = Field(default=False, description="Set True when user asks grouping/breakdown questions like 'how many per division', 'breakdown by building'. For normal filter/list queries leave as False.")
    group_by_columns: Optional[List[str]] = Field(default=None, description="List of columns to group by. Only fill when is_aggregate=True. Valid columns: DivisionName, DisciplineName, BuildingName, FloorName, LocalityName, StatusName, ConditionName, PriorityName, AssetTypeName, EquipmentName, MakeName, ModelName, SpotName, TradeGroupName, ServiceAreaName, OnHold, IsSnagged, IsScraped, IsEnablePPM, IsEnableBDM.")
    aggregate_function: Optional[str] = Field(default=None, description="Aggregation function. COUNT for how many, SUM for total, AVG for average. Only when is_aggregate=True.")
    



class PPMInput(BaseModel):
    """Schema for PPM tool. Covers planned preventive maintenance schedules."""
    user_id: Optional[str] = Field(None, description="Internal system-set ID; strictly mandatory for all queries. Never request this from the user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name; strictly mandatory for all queries. Never request this from the user.")
    work_order: Optional[str] = Field(None, description="Work order number. Map if user mentions 'Work Order' or 'WO Number'.")
    asset_tag_no: Optional[str] = Field(None, description="Asset tag number. Map if user mentions a specific asset tag.")
    equipment_ref_no: Optional[str] = Field(None, description="Equipment reference number. Map if user mentions 'Ref No', 'Reference Number', or 'EquipmentRefNo'.")
    status: Optional[str] = Field(None, description="Maps if user mentions 'PPM Status' or 'Status Name'. Mandatory for filtering schedule states.")
    stage: Optional[str] = Field(None, description="Maintenance workflow step. Map here if user mentions 'Stage' or 'Workflow Step'.")
    frequency: Optional[str] = Field(None, description="Interval of maintenance. Map here if user mentions 'Frequency', 'Daily', 'Weekly', or 'Monthly'.")
    division: Optional[str] = Field(None, description="Organizational unit. Maps if user mentions 'Division', 'Division Name', or 'DivisionName'.")
    discipline: Optional[str] = Field(None, description="Technical specialty. Maps if user mentions 'Discipline', 'Discipline Name', or 'DisciplineName'.")
    locality: Optional[str] = Field(None, description="Geographic area or site (e.g. district, complex, community). Do NOT map indoor rooms or common areas here; map them to 'spot_name'.")
    building: Optional[str] = Field(None, description="Structure name. Map here if user mentions 'Building' or 'PPM Building'.")
    floor: Optional[str] = Field(None, description="Level designation. Map here if user mentions 'Floor' or 'PPM Floor'.")
    spot_name: Optional[str] = Field(None, description="Filter by specific room, space, or interior common area. Map general interior locations here instead of 'locality'.")
    equipment: Optional[str] = Field(None, description="Equipment name. Map if user mentions specific equipment.")
    contract: Optional[str] = Field(None, description="Service agreement name. Map here if user mentions 'Contract' or 'Agreement'.")
    tech: Optional[str] = Field(None, description="Maintenance worker name. Map here if user mentions 'Technician' or 'Assigned Staff'.")
    keyword: Optional[str] = Field(None, description="Mandatory fallback ONLY for specific technical terms. Do not use vague conversational words.")
    date_from: Optional[str] = Field(None, description="Start range. Use YYYY-MM-DD.")
    date_to: Optional[str] = Field(None, description="End range. Use YYYY-MM-DD.")
    comp_from: Optional[str] = Field(None, description="Completion start range (WoCompletedDate). Use YYYY-MM-DD.")
    comp_to: Optional[str] = Field(None, description="Completion end range (WoCompletedDate). Use YYYY-MM-DD.")
    sla_min: Optional[int] = Field(None, description="Minimum SLADuration. Map if user mentions 'SLA Min'.")
    sla_max: Optional[int] = Field(None, description="Maximum SLADuration. Map if user mentions 'SLA Max'.")
    limit: Optional[int] = Field(default=None, description="Max number of results. Only set if user asks for a specific number. For count queries MUST omit.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless requested.")
    is_aggregate: Optional[bool] = Field(default=False, description="Set True only when user asks grouping or summary questions like 'how many PPM per division', 'breakdown by frequency'. For normal filter/list queries leave as False.")
    group_by_columns: Optional[List[str]] = Field(default=None, description="List of columns to group by. Only fill when is_aggregate=True. Valid columns: DivisionName, DisciplineName, BuildingName, FloorName, LocalityName, FrequencyName, PPMStatus, PPMStageName, ContractName, SpotName.")
    aggregate_function: Optional[str] = Field(default=None, description="Aggregation function. COUNT for how many, SUM for total, AVG for average. Only when is_aggregate=True.")
    



class BDMInput(BaseModel):
    """Schema for BDM tool. Covers breakdown complaints and reactive work orders."""
    user_id: Optional[str] = Field(None, description="Internal system-set ID; strictly mandatory for all queries. Never request this from the user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name; strictly mandatory for all queries. Never request this from the user.")
    complaint_no: Optional[str] = Field(None, description="Complaint number. Map if user mentions a specific complaint number.")
    asset_tag_no: Optional[str] = Field(None, description="Asset tag number linked to the complaint. Map if user mentions an asset tag.")
    asset_barcode: Optional[str] = Field(None, description="Asset barcode linked to the complaint. Map if user mentions 'Barcode'.")
    client_wo_no: Optional[str] = Field(None, description="Client work order number. Map if user mentions 'Client WO' or 'ClientWoNo'.")
    status: Optional[str] = Field(None, description="Maps if user mentions 'Status' or 'Status Name'. Mandatory for filtering complaint lifecycle states.")
    priority: Optional[str] = Field(None, description="Urgency level. Map here if user mentions 'Priority' or 'Urgency Level'.")
    stage: Optional[str] = Field(None, description="Workflow step. Map here if user mentions 'Stage' or 'Complaint Stage'.")
    complaint_type: Optional[str] = Field(None, description="Category of failure. Map here if user mentions 'Complaint Type' or 'Category'.")
    complaint_header: Optional[str] = Field(None, description="Complaint header name. Map if user mentions 'Complaint Header' or 'ComplaintHeaderName'.")
    complaint_mode: Optional[str] = Field(None, description="Source of registration. Map here if user mentions 'Complaint Mode' or 'Reporting Mode'.")
    complaint_nature: Optional[str] = Field(None, description="Failure description. Map here if user mentions 'Nature', 'Failure', or 'Issue'.")
    wo_type: Optional[str] = Field(None, description="Work order classification. Map here if user mentions 'Work Order Type' or 'WO'.")
    service_type: Optional[str] = Field(None, description="Service category. Map here if user mentions 'Service Type' or 'Service'.")
    division: Optional[str] = Field(None, description="Organizational unit. Maps if user mentions 'Division', 'Division Name', or 'DivisionName'.")
    discipline: Optional[str] = Field(None, description="Technical specialty. Maps if user mentions 'Discipline', 'Discipline Name', or 'DisciplineName'.")
    locality: Optional[str] = Field(None, description="Geographic area or site. Do NOT map indoor rooms here; map them to 'spot_name'.")
    building: Optional[str] = Field(None, description="Structure name. Map here if user mentions 'Building'.")
    floor: Optional[str] = Field(None, description="Level designation. Map here if user mentions 'Floor'.")
    spot_name: Optional[str] = Field(None, description="Filter by specific room or interior common area. Map general interior locations here instead of 'locality'.")
    contract: Optional[str] = Field(None, description="Service agreement. Map here if user mentions 'Contract' or 'Service Provider'.")
    complainer: Optional[str] = Field(None, description="Name of the person who raised the complaint.")
    register_by: Optional[str] = Field(None, description="Person who registered the complaint. Map if user mentions 'Registered By' or 'RegisterBy'.")
    analysis_tech: Optional[str] = Field(None, description="Assigned analyst. Map here if user mentions 'Analysis Technician' or 'Inspector'.")
    execution_tech: Optional[str] = Field(None, description="Repair technician. Map here if user mentions 'Execution Technician' or 'Repairer'.")
    keyword: Optional[str] = Field(None, description="Mandatory fallback ONLY for specific technical terms. Do not use vague conversational words.")
    date_from: Optional[str] = Field(None, description="Reported start range. Use YYYY-MM-DD.")
    date_to: Optional[str] = Field(None, description="Reported end range. Use YYYY-MM-DD.")
    completed_from: Optional[str] = Field(None, description="Resolution start range (BDMWOCompletedDate). Use YYYY-MM-DD.")
    completed_to: Optional[str] = Field(None, description="Resolution end range (BDMWOCompletedDate). Use YYYY-MM-DD.")
    limit: Optional[int] = Field(default=None, description="Max number of results. Only set if user asks for a specific number. For count queries MUST omit.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless requested.")
    is_aggregate: Optional[bool] = Field(default=False, description="Set True only when user asks grouping or summary questions. For normal filter/list queries leave as False.")
    group_by_columns: Optional[List[str]] = Field(default=None, description="Columns to group by. Valid: DivisionName, DisciplineName, BuildingName, FloorName, LocalityName, WoStatus, PriorityName, StageName, ComplaintTypeName, ComplaintModeName, SpotName, ContractName.")
    aggregate_function: Optional[str] = Field(default=None, description="COUNT for how many, SUM for total, AVG for average. Only when is_aggregate=True.")
    
class FAInput(BaseModel):
    """Schema for FA tool. Covers Facility Audit scheduled inspection complaints (FacilityAudit table)."""
    user_id: Optional[str] = Field(None, description="Internal system-set ID. Never request from user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name. Never request from user.")
    complaint_no: Optional[str] = Field(None, description="FA complaint number (RMComplaintNo). Map if user mentions a specific complaint number.")
    complaint_code: Optional[str] = Field(None, description="CCM complaint code (RMCCMComplaintCode). Map if user mentions 'Complaint Code'.")
    x_complaint_no: Optional[str] = Field(None, description="External complaint number (RMXComplaintNo). Map if user mentions 'X Complaint No' or 'External Complaint'.")
    priority: Optional[str] = Field(None, description="Priority level. Map if user mentions 'Priority' or 'P1', 'P2', etc.")
    stage: Optional[str] = Field(None, description="Audit workflow stage (RMStageName). Map if user mentions 'Stage'. Example: 'Facility Audit Request Raised'.")
    category: Optional[str] = Field(None, description="Audit category (RMCategoryName). Map if user mentions 'Category', 'Pest Control'.")
    category_sub: Optional[str] = Field(None, description="Audit sub-category (RMCategorySubName). Map if user mentions 'Sub Category', 'Rodent Activity'.")
    division: Optional[str] = Field(None, description="Organizational unit. Map if user mentions 'Division'.")
    locality: Optional[str] = Field(None, description="Geographic area or site. Do NOT map indoor rooms here; map them to 'spot_name'.")
    building: Optional[str] = Field(None, description="Building name. Map if user mentions 'Building'.")
    floor: Optional[str] = Field(None, description="Floor name. Map if user mentions 'Floor'.")
    spot_name: Optional[str] = Field(None, description="Filter by specific room or interior common area. Map general interior locations here instead of 'locality'.")
    contract: Optional[str] = Field(None, description="Contract name. Map if user mentions 'Contract'.")
    tech: Optional[str] = Field(None, description="Technician name (RMTechName). Map if user mentions 'Technician' or 'Tech'.")
    frequency: Optional[str] = Field(None, description="Inspection frequency. Map if user mentions 'Frequency', 'Monthly', 'Weekly'.")
    request_desc: Optional[str] = Field(None, description="Request description (RMRequestDetailsDesc). Map if user mentions 'Pest Control', 'Housekeeping'.")
    is_withdraw: Optional[bool] = Field(None, description="FILTER for IsRMWithdraw. For breakdown use is_aggregate=True with group_by_columns=['IsWithdraw'].")
    is_rework: Optional[bool] = Field(None, description="FILTER for IsRMRework. For breakdown use is_aggregate=True with group_by_columns=['IsRework'].")
    is_bms: Optional[bool] = Field(None, description="FILTER for IsRMBMS (BMS-linked FA records). Map if user mentions 'BMS' in FA context.")
    is_active: Optional[bool] = Field(None, description="FILTER for IsActive value. For breakdown use is_aggregate=True with group_by_columns=['IsActive'].")
    is_draft: Optional[bool] = Field(None, description="FILTER for IsDraft (draft FA records). Map if user mentions 'Draft' in FA context.")
    keyword: Optional[str] = Field(None, description="Fallback for specific technical terms not covered by other fields.")
    date_from: Optional[str] = Field(None, description="Start date range. Use YYYY-MM-DD.")
    date_to: Optional[str] = Field(None, description="End date range. Use YYYY-MM-DD.")
    comp_from: Optional[str] = Field(None, description="Completion start range (RMBDMWOCompletedDate). Use YYYY-MM-DD.")
    comp_to: Optional[str] = Field(None, description="Completion end range. Use YYYY-MM-DD.")
    limit: Optional[int] = Field(default=None, description="Max records. Only set if user asks for specific number.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless requested.")
    is_aggregate: Optional[bool] = Field(default=False, description="Set True for grouping queries like 'how many FA per division', 'breakdown by category'.")
    group_by_columns: Optional[List[str]] = Field(default=None, description="Columns to group by. Valid: DivisionName, BuildingName, FloorName, LocalityName, PriorityName, RMStageName, RMCategoryName, RMCategorySubName, FrequencyName, ContractName, SpotName, IsWithdraw, IsRework, IsActive.")
    aggregate_function: Optional[str] = Field(default=None, description="COUNT for how many, SUM for total, AVG for average. Only when is_aggregate=True.")
 
 
class SBInput(BaseModel):
    """Schema for SB tool. Covers Schedule-Based maintenance work orders (ScheduleBased table)."""
    user_id: Optional[str] = Field(None, description="Internal system-set ID. Never request from user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name. Never request from user.")
    work_order: Optional[str] = Field(None, description="Work order number (SBCreWorkOrder). Map if user mentions 'Work Order', 'WO Number', e.g. 'AA-1-2026'.")
    stage: Optional[str] = Field(None, description="Workflow stage (PPMStageName). Map if user mentions 'Stage', 'Staff Yet to be Allocated', etc.")
    frequency: Optional[str] = Field(None, description="Schedule frequency. Map if user mentions 'Frequency', 'Monthly', 'Weekly'.")
    service_type: Optional[str] = Field(None, description="Service type (ServiceTypeName). Map if user mentions 'Service Type', 'Environmental Services', 'Landscaping'.")
    division: Optional[str] = Field(None, description="Organizational unit. Map if user mentions 'Division' or 'DivisionName'.")
    discipline: Optional[str] = Field(None, description="Technical discipline. Map if user mentions 'Discipline', 'Landscaping', 'Environmental'.")
    locality: Optional[str] = Field(None, description="Geographic area or site. Do NOT map indoor rooms here; map them to 'spot_name'.")
    building: Optional[str] = Field(None, description="Building name. Map if user mentions 'Building'.")
    floor: Optional[str] = Field(None, description="Floor name. Map if user mentions 'Floor'.")
    spot_name: Optional[str] = Field(None, description="Filter by specific room or interior common area. Map general interior locations here instead of 'locality'.")
    contract: Optional[str] = Field(None, description="Contract name. Map if user mentions 'Contract'.")
    tech: Optional[str] = Field(None, description="Technician name (SBTechName). Map if user mentions 'Technician' or 'Tech'.")
    is_withdraw: Optional[bool] = Field(None, description="FILTER for IsSBCreWithDraw. Map if user mentions 'withdrawn SB' or 'SB withdraw'.")
    is_reschedule: Optional[bool] = Field(None, description="FILTER for IsSbCreReschedule. Map if user mentions 'rescheduled SB'.")
    is_rework: Optional[bool] = Field(None, description="FILTER for IsSBCreRework. Map if user mentions 'rework SB'.")
    is_active: Optional[bool] = Field(None, description="FILTER for IsActive. Map if user mentions 'active SB'.")
    is_draft: Optional[bool] = Field(None, description="FILTER for IsDraft. Map if user mentions 'draft SB'.")
    keyword: Optional[str] = Field(None, description="Fallback for specific technical terms not covered by other fields.")
    date_from: Optional[str] = Field(None, description="Start date range. Use YYYY-MM-DD.")
    date_to: Optional[str] = Field(None, description="End date range. Use YYYY-MM-DD.")
    comp_from: Optional[str] = Field(None, description="Completion start range (SBCreWoCompletedDate). Use YYYY-MM-DD.")
    comp_to: Optional[str] = Field(None, description="Completion end range. Use YYYY-MM-DD.")
    sla_min: Optional[float] = Field(None, description="Minimum SBCreSLAHours. Map if user mentions 'SLA Min'.")
    sla_max: Optional[float] = Field(None, description="Maximum SBCreSLAHours. Map if user mentions 'SLA Max'.")
    limit: Optional[int] = Field(default=None, description="Max records. Only set if user asks for specific number.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless requested.")
    is_aggregate: Optional[bool] = Field(default=False, description="Set True for grouping queries like 'how many SB per division', 'breakdown by frequency'.")
    group_by_columns: Optional[List[str]] = Field(default=None, description="Columns to group by. Valid: DivisionName, DisciplineName, BuildingName, FloorName, LocalityName, PPMStageName, FrequencyName, ServiceTypeName, ContractName, SpotName.")
    aggregate_function: Optional[str] = Field(default=None, description="COUNT for how many, SUM for total, AVG for average. Only when is_aggregate=True.")



class ChatRequest(BaseModel):
    """Request schema for chat endpoint"""
    query: Optional[str] = None
    userName: Optional[str] = None
    user_name: Optional[str] = None
    userId: Optional[str] = None
    user_id: Optional[str] = None
    sessionId: Optional[str] = None
    session_id: Optional[str] = None

class FrontendChatMessage(BaseModel):
    """Shape of a single chat message sent from frontend when saving history."""
    role: str
    text: str
    isAudio: bool = False


class SessionRequest(BaseModel):
    """
    Request schema for:
    - fetching all sessions (no sessionId)
    - fetching chat history for a session (sessionId present)
    - saving chat history for a session (chatHistory present)
    """
    userName: str
    sessionId: str = ""
    chatHistory: Optional[List[FrontendChatMessage]] = None
    historyOnClick: bool = False
    group_name: Optional[str] = None

class ClientInsertionRequest(BaseModel):
    """Request schema for client insertion"""
    userId: str
    userName: str
    service: str
    token: str

class ClientInsertionRequest(BaseModel):
    """Request schema for client insertion"""
    userId: str
    clientName: str
    userName: str
    service: str
    token: str