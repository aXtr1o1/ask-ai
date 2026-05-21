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
    asset_tag_no: Optional[str] = Field(None, description="Unique tag number that identifies the asset. Format is always alphanumeric with dashes — NEVER a plain number. Map ONLY when user explicitly mentions a tag number in this format. Example values: L1-HVAC-CHL-3827, AJ-DV-DV-3826, T-A1-DV-DV-3825, DM-FF&AS-FE-13802. Do NOT use for pure numeric values — map those to asset_barcode instead.")
    asset_barcode: Optional[str] = Field(None, description="Barcode number printed on the asset label. Format is always a pure numeric string (digits only, no dashes or letters). Map here if the user provides ANY plain numeric ID or mentions 'Barcode' or 'Asset Barcode'. Example values: 1731251675376, 1731251675374, 1954391. Do NOT map alphanumeric values here — use asset_tag_no for those.")
    equipment_name: Optional[str] = Field(None, description="Name or description of the equipment or asset type. Map if user mentions 'Equipment Name' or 'EquipmentName'. Example values: Chiller 1, Heavy Loader, High Loader 10, Pushback Tractor, Fire Extinguisher.")
    equipment_ref_no: Optional[str] = Field(None, description="Equipment reference number. Map if user mentions 'Ref No', 'Reference Number', or 'EquipmentRefNo'.")
    serial_no: Optional[str] = Field(None, description="Filter by serial number. Map if user mentions 'Serial', 'Serial No', 'Serial Number', or 'S/N'.")
    status: Optional[str] = Field(None, description="Current operational status of the asset. Map if user mentions 'Status' or 'Status Name'. Example values: Online, Offline.")
    condition: Optional[str] = Field(None, description="Physical condition of the asset as assessed. Map if user mentions 'Condition' or 'State'. Example values: Good, Bad, Fair, Under Repair.")
    priority: Optional[str] = Field(None, description="Maintenance priority level assigned to the asset. Map if user mentions 'Priority' or 'Urgency'. Example values: P1 Critical, P2 High, P3 Medium, P4 Low.")
    asset_type: Optional[str] = Field(None, description="Category or type of the asset. Map if user mentions 'Asset Type', 'Type', or 'AssetTypeName'.")
    division: Optional[str] = Field(None, description="Division or system category the asset belongs to. Map if user mentions 'Division', 'Division Name', or 'DivisionName'. Example values: HVAC System, Duty Vehicles, Electrical System, Plumbing System, Fire Fighting and Alarm system, HVAC & PLUMBING SYSTEMS, Kitchen Handling Equipments.")
    discipline: Optional[str] = Field(None, description="Technical discipline or trade the asset belongs to. Map if user mentions 'Discipline', 'Discipline Name', or 'DisciplineName'. Example values: CHILLER, Duty Vehicles, Fire Extinguisher, Plumbing, Electrical.")
    locality: Optional[str] = Field(None, description="Physical location zone or geographic area (e.g. district, complex, community, airside zone). Do NOT map indoor rooms or common areas here — map those to 'spot_name'. Example values: Al Jurf, Terminal A1, Terminal - A2, Ajman, Doha, Airside Area.")
    building: Optional[str] = Field(None, description="Name of the building where the asset is installed. Map if user mentions 'Building' or 'Building Name'. Example values: Camp, Villa 4, Passenger Terminal Building T1 (Demo), Old Airport Terminal, VIP Terminal, Building 1 - Residential High Rise, Airfield Fire Fighting Station Building.")
    floor: Optional[str] = Field(None, description="Floor within the building where the asset is located. Map if user mentions 'Floor' or 'Floor Name'. Example values: Ground Floor, Roof Level, Roof Top, Apron Level, Parking Floor 5, Floor 1, Floor 9.")
    spot_name: Optional[str] = Field(None, description="Specific spot, room, or zone within the floor where the asset is physically placed. Map if user mentions a specific room, space, or interior area. Example values: AHU_R1201, Trash Compactor Area, Roof, Common Area Arrivals, Parking Area 5, Electrical Room, AIRFIELD SUBSTATION AF10/RS_122.")
    owner: Optional[str] = Field(None, description="Entity or department responsible for the asset. Map if user mentions 'Owner' or 'Department'.")
    make: Optional[str] = Field(None, description="Manufacturer or brand name of the asset. Map if user mentions 'Make', 'Manufacturer', or 'Brand'. Example values: SHARK, Gold Hofer, Schopf, SDI, Carrier, Trane, York.")
    model: Optional[str] = Field(None, description="Model name or number of the asset. Map if user mentions 'Model' or 'Model Name'. Example values: AST-2P, SHARK, SDI 2045, 2003.")
    service_area: Optional[str] = Field(None, description="Functional service area covered by the asset. Map if user mentions 'Service Area' or 'Zone'.")
    trade_group: Optional[str] = Field(None, description="Maintenance trade group responsible for the asset. Map if user mentions 'Trade Group' or 'Team'.")
    drawing_no: Optional[str] = Field(None, description="Drawing reference number. Map if user mentions 'Drawing No' or 'Drawing Number'.")
    remarks: Optional[str] = Field(None, description="Asset remarks/notes. Map if user mentions 'Remarks' or 'Notes'.")
    on_hold: Optional[bool] = Field(None, description="Whether the asset is currently placed on hold and not in active use. Set true to filter held/unavailable assets, false for active assets. FILTER only — do NOT use when user asks for a breakdown; use is_aggregate=True with group_by_columns=['OnHold'] instead.")
    is_snagged: Optional[bool] = Field(None, description="Whether the asset has an active snag or defect logged against it. Set true to filter snagged assets. FILTER only — for breakdown use is_aggregate=True with group_by_columns=['IsSnagged'].")
    is_scraped: Optional[bool] = Field(None, description="Whether the asset has been scrapped or permanently retired from service. Set true to filter scrapped assets. FILTER only — for breakdown use is_aggregate=True with group_by_columns=['IsScraped'].")
    enable_ppm: Optional[bool] = Field(None, description="Whether Planned Preventive Maintenance (PPM) is enabled for this asset. Set true to filter PPM-enabled assets. FILTER only — for breakdown use is_aggregate=True with group_by_columns=['IsEnablePPM'].")
    enable_bdm: Optional[bool] = Field(None, description="Whether Breakdown Maintenance (BDM) is enabled for this asset. Set true to filter BDM-enabled assets. FILTER only — for breakdown use is_aggregate=True with group_by_columns=['IsEnableBDM'].")
    enable_bms: Optional[bool] = Field(None, description="Whether Building Management System (BMS) monitoring is enabled for this asset. Set true/false for BMS enabled assets. Map if user mentions 'BMS' or 'Building Management System'.")
    enable_dsm: Optional[bool] = Field(None, description="Whether Demand Side Management (DSM) is enabled for this asset. Set true/false for DSM enabled assets. Map if user mentions 'DSM'.")
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
    work_order: Optional[str] = Field(None, description="Unique work order number for the PPM task. Map if user mentions 'Work Order' or 'WO Number'. Example values: 50010-DM-14264-2026, 50010-DM-14262-2026.")
    asset_tag_no: Optional[str] = Field(None, description="Tag number of the asset this PPM work order is raised for. Map if user mentions a specific asset tag. Example values: DM-FF&AS-FE-13802, DM-FF&AS-FE-13800, L1-HVAC-CHL-3827.")
    equipment_ref_no: Optional[str] = Field(None, description="Equipment reference number. Map if user mentions 'Ref No', 'Reference Number', or 'EquipmentRefNo'.")
    status: Optional[str] = Field(None, description="Current status of the PPM work order. Map if user mentions 'PPM Status' or 'Status Name'. Example values: Open, Closed.")
    stage: Optional[str] = Field(None, description="Current workflow stage of the PPM work order. Map if user mentions 'Stage' or 'Workflow Step'. Example values: Staff Yet to be Allocated, Technician Assigned, Work In Progress, Completed.")
    frequency: Optional[str] = Field(None, description="Maintenance frequency schedule for the PPM work order. Map if user mentions 'Frequency', 'Daily', 'Weekly', or 'Monthly'. Example values: QUARTERLY, MONTHLY, ANNUALLY, WEEKLY, BI-MONTHLY.")
    division: Optional[str] = Field(None, description="Division or system category the PPM asset belongs to. Map if user mentions 'Division', 'Division Name', or 'DivisionName'. Example values: Fire Fighting and Alarm system, HVAC System, Electrical System, Plumbing System.")
    discipline: Optional[str] = Field(None, description="Technical discipline of the asset the PPM is for. Map if user mentions 'Discipline', 'Discipline Name', or 'DisciplineName'. Example values: Fire Extinguisher, CHILLER, Plumbing, Electrical, Duty Vehicles.")
    locality: Optional[str] = Field(None, description="Physical location zone or geographic area of the PPM asset. Do NOT map indoor rooms here — map those to 'spot_name'. Example values: Doha, Terminal A1, Terminal - A2, Ajman, Al Jurf.")
    building: Optional[str] = Field(None, description="Name of the building where the PPM asset is installed. Map if user mentions 'Building' or 'PPM Building'. Example values: Building 1 - Residential High Rise, Building 2 - Residential High Rise, Passenger Terminal Building T1 (Demo).")
    floor: Optional[str] = Field(None, description="Floor within the building where the PPM asset is located. Map if user mentions 'Floor' or 'PPM Floor'. Example values: Floor 1, Floor 2, Ground Floor, Roof Level.")
    spot_name: Optional[str] = Field(None, description="Specific spot or room within the floor where the PPM work order is raised for. Map if user mentions a specific room or interior area. Example values: Electrical Room, Telephone room, AHU_R1201, Common Area.")
    equipment: Optional[str] = Field(None, description="Name of the equipment or asset the PPM work order is for. Map if user mentions specific equipment. Example values: Fire Extinguisher, Chiller 1, AHU, Pump, Generator.")
    contract: Optional[str] = Field(None, description="Name of the maintenance contract under which the PPM is raised. Map if user mentions 'Contract' or 'Agreement'. Example values: Facility Management Residential Area, Maintenance of MEP Equipments (DEMO).")
    tech: Optional[str] = Field(None, description="Name of the technician assigned to carry out this PPM work order. Map if user mentions 'Technician' or 'Assigned Staff'. Example values: Technician, John Smith.")
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
    complaint_no: Optional[str] = Field(None, description="Unique complaint number identifying the BDM work order. Map if user mentions a specific complaint number. Example values: 1261, 1260, 1255, 1252.")
    asset_tag_no: Optional[str] = Field(None, description="Tag number of the asset linked to this complaint. Map if user mentions an asset tag. Example values: L1-HVAC-CHL-3827, T-A1-DV-DV-3825.")
    asset_barcode: Optional[str] = Field(None, description="Barcode of the asset linked to this complaint. Map if user mentions 'Barcode'. Example values: 1731251675376, 1731251675374. Null if no asset is associated.")
    client_wo_no: Optional[str] = Field(None, description="Client work order number. Map if user mentions 'Client WO' or 'ClientWoNo'.")
    status: Optional[str] = Field(None, description="Current status of the BDM complaint or work order. Map if user mentions 'Status' or 'Status Name'. Example values: Open, Closed.")
    priority: Optional[str] = Field(None, description="Priority level assigned to the complaint. Map if user mentions 'Priority' or 'Urgency Level'. Example values: P1 Critical, P2 High, P3 Medium, P4 Low.")
    stage: Optional[str] = Field(None, description="Current workflow stage of the complaint. Map if user mentions 'Stage' or 'Complaint Stage'. Example values: Complaint / Service Request Raised, Staff Assigned for Analysis / Job Estimation, Staff Assigned for Work Execution, Complaint / Service Request - Closed.")
    complaint_type: Optional[str] = Field(None, description="Type of complaint raised. Map if user mentions 'Complaint Type' or 'Category'. Example values: Corrective Maintenance, Service Request.")
    complaint_header: Optional[str] = Field(None, description="Complaint header name. Map if user mentions 'Complaint Header' or 'ComplaintHeaderName'.")
    complaint_mode: Optional[str] = Field(None, description="Channel through which the complaint was submitted. Map if user mentions 'Complaint Mode' or 'Reporting Mode'. Example values: By Call, By Community Portal.")
    complaint_nature: Optional[str] = Field(None, description="Short description of the nature or subject of the complaint. Map if user mentions 'Nature', 'Failure', or 'Issue'. Example values: Water leakage in common area, light flickering, AC very noisy, Chiller vibration, fire related issues.")
    wo_type: Optional[str] = Field(None, description="Type of work order raised for the complaint. Map if user mentions 'Work Order Type' or 'WO'. Example values: General.")
    service_type: Optional[str] = Field(None, description="Type of service the complaint falls under. Map if user mentions 'Service Type' or 'Service'. Example values: Air Conditioning Services, Plumbing Services, Electrical Services, Environmental Services, IT Service Management.")
    division: Optional[str] = Field(None, description="Division or system the complaint belongs to. Map if user mentions 'Division', 'Division Name', or 'DivisionName'. Example values: Plumbing System, Electrical System, HVAC System, Fire Fighting and Alarm system, Housekeeping, Kitchen Handling Equipments.")
    discipline: Optional[str] = Field(None, description="Technical discipline linked to the complaint. Map if user mentions 'Discipline', 'Discipline Name', or 'DisciplineName'. Example values: CHILLER, Plumbing, Electrical, Fire Extinguisher.")
    locality: Optional[str] = Field(None, description="Physical location zone or geographic area where the complaint was raised. Do NOT map indoor rooms here — map those to 'spot_name'. Example values: Terminal - A2, Airside Area, Ajman, Doha, Terminal A1.")
    building: Optional[str] = Field(None, description="Name of the building where the complaint was raised. Map if user mentions 'Building'. Example values: WATER TREATMENT PLANT, Warehouse building, Building 1 - Residential High Rise, Passenger Terminal Building T1 (Demo), Runway 18/36.")
    floor: Optional[str] = Field(None, description="Floor within the building where the complaint was raised. Map if user mentions 'Floor'. Example values: Ground Floor, Floor 6, Floor 9.")
    spot_name: Optional[str] = Field(None, description="Specific spot or room within the floor where the complaint was raised. Map if user mentions a specific room or interior area. Example values: Common Area 9, Appartement-59, Warehouse building.")
    contract: Optional[str] = Field(None, description="Name of the maintenance contract under which this complaint is raised. Map if user mentions 'Contract' or 'Service Provider'. Example values: Maintenance of MEP Equipments (DEMO), Facility Management Residential Area.")
    complainer: Optional[str] = Field(None, description="Name of the person who raised or submitted the complaint. Example values: eashaktech, Mohamed, naina muhamed, gowthaman, technician.")
    register_by: Optional[str] = Field(None, description="Username of the person who registered or created the complaint in the system. Map if user mentions 'Registered By' or 'RegisterBy'. Example values: helpdesk, admin, technician, eashaktech.")
    analysis_tech: Optional[str] = Field(None, description="Name of the technician assigned for the analysis or job estimation phase. Map if user mentions 'Analysis Technician' or 'Inspector'. Example values: Technician, eashaktech, Employee18.")
    execution_tech: Optional[str] = Field(None, description="Name of the technician assigned to execute or carry out the repair work. Map if user mentions 'Execution Technician' or 'Repairer'. Example values: Technician, Employee18. Empty if not yet assigned.")
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