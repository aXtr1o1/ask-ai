"""
Pydantic Schemas for LangChain Tools and API Requests
"""
from pydantic import BaseModel, Field
from typing import Optional


# ==========================================
# ✅ LANGCHAIN TOOL INPUT SCHEMAS
# ==========================================

class AssetsInput(BaseModel):
    """Schema for ASSETS tool. Covers physical equipment and master records."""
    user_id: Optional[str] = Field(None, description="Internal system-set user identifier strictly mandatory for all database and API queries. Never request from user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name strictly mandatory for all database and API queries. Never request from user.")
    asset_tag_no: Optional[str] = Field(None, description="Unique equipment identification number for precise tag-based searches. Do not guess or estimate this value.")
    status: Optional[str] = Field(None, description="Equipment operational or administrative status state. Maps if user mentions Status or Status Name for filtering.")
    condition: Optional[str] = Field(None, description="Physical condition state of equipment asset. Maps if user mentions Condition, State, or Quality level.")
    priority: Optional[str] = Field(None, description="Equipment criticality or importance level. Maps if user mentions Priority, Urgency, or Severity level.")
    asset_type: Optional[str] = Field(None, description="Equipment category or type classification. Maps if user mentions Asset Type, Type, Category, or TypeName.")
    division: Optional[str] = Field(None, description="Organizational division or business unit. Maps if user mentions Division, Division Name, DivisionName, Department.")
    discipline: Optional[str] = Field(None, description="Technical specialty discipline domain. Maps if user mentions Discipline, Discipline Name, DisciplineName, specialty.")
    locality: Optional[str] = Field(None, description="Geographic location or site area. Maps if user mentions Locality, Location, Site, Area, or Region clearly.")
    building: Optional[str] = Field(None, description="Specific building or structure name. Maps if user mentions Building, Building Name, Structure, or Facility.")
    floor: Optional[str] = Field(None, description="Building floor or level designation. Maps if user mentions Floor, Floor Name, Level, or Story clearly.")
    owner: Optional[str] = Field(None, description="Entity responsible for asset ownership. Maps if user mentions Owner, Department, Division, or Organization.")
    make: Optional[str] = Field(None, description="Equipment manufacturer or brand name. Maps if user mentions Make, Manufacturer, Brand, or OEM name.")
    model: Optional[str] = Field(None, description="Specific equipment model designation. Maps if user mentions Model, Model Name, Model Number, or variant.")
    service_area: Optional[str] = Field(None, description="Functional area or zone served. Maps if user mentions Service Area, Zone, Service Zone, or Area.")
    trade_group: Optional[str] = Field(None, description="Maintenance team or trade group. Maps if user mentions Trade Group, Team, Crew, or Department clearly.")
    spot_name: Optional[str] = Field(None, description="Specific location spot name. Maps if user mentions Spot, Spot Name, Location, or Spot designation.")
    serial_no: Optional[str] = Field(None, description="Equipment serial number identifier. Maps if user mentions Serial, Serial No, Serial Number, or S/N.")
    on_hold: Optional[bool] = Field(None, description="Boolean flag for frozen or held assets. Set true if user mentions On Hold status or holds.")
    is_snagged: Optional[bool] = Field(None, description="Boolean flag for defective or snagged assets. Set true if user mentions Snagged or Defects.")
    is_scraped: Optional[bool] = Field(None, description="Boolean flag for decommissioned or scraped assets. Set true if user mentions Scraped or Disposed.")
    enable_ppm: Optional[bool] = Field(None, description="Boolean flag for scheduled maintenance assets. Set true if user mentions PPM Enabled or Planned.")
    enable_bdm: Optional[bool] = Field(None, description="Boolean flag for breakdown-ready assets. Set true if user mentions BDM Enabled or Reactive status.")
    keyword: Optional[str] = Field(None, description="MANDATORY for general queries when no filters specified. Use for broad searches like 'show assets', 'all equipment', 'list 10 assets'. Essential for queries without specific criteria.")
    date_from: Optional[str] = Field(None, description="Equipment installation or commissioning start date. Use YYYY-MM-DD. Map if user mentions From Date.")
    date_to: Optional[str] = Field(None, description="Equipment installation or commissioning end date. Use YYYY-MM-DD. Map if user mentions To Date.")
    limit: Optional[int] = Field(default=None, description="Max number of results. Only set if user asks for a specific number (e.g. 'show 10'). For count/total queries (how many, total), MUST omit — do not set.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless requested.")


class PPMInput(BaseModel):
    """Schema for PPM tool. Covers planned preventive maintenance schedules."""
    user_id: Optional[str] = Field(None, description="Internal system-set user identifier strictly mandatory for all database and API queries. Never request from user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name strictly mandatory for all database and API queries. Never request from user.")
    work_order: Optional[str] = Field(None, description="PPM work order number identifier. Maps if user mentions Work Order, WO Number, or work order ID.")
    asset_tag_no: Optional[str] = Field(None, description="Asset tag number identifier. Maps if user mentions specific asset tag or equipment number.")
    status: Optional[str] = Field(None, description="PPM schedule status state. Maps if user mentions PPM Status, Status Name, or schedule state.")
    stage: Optional[str] = Field(None, description="Maintenance workflow or process stage. Maps if user mentions Stage, Workflow Step, or phase.")
    frequency: Optional[str] = Field(None, description="Maintenance interval frequency. Maps if user mentions Frequency, Daily, Weekly, Monthly, or schedule.")
    division: Optional[str] = Field(None, description="Organizational division or business unit. Maps if user mentions Division, Division Name, DivisionName.")
    discipline: Optional[str] = Field(None, description="Technical specialty discipline domain. Maps if user mentions Discipline, Discipline Name, DisciplineName.")
    locality: Optional[str] = Field(None, description="Geographic location or site area. Maps if user mentions Locality, PPM Location, Site, or Region.")
    building: Optional[str] = Field(None, description="Building or structure name. Maps if user mentions Building, PPM Building, Structure, or Facility.")
    floor: Optional[str] = Field(None, description="Floor level or story designation. Maps if user mentions Floor, PPM Floor, Level, or Story.")
    contract: Optional[str] = Field(None, description="Service contract or agreement name. Maps if user mentions Contract, Agreement, or Service Provider.")
    tech: Optional[str] = Field(None, description="Maintenance technician worker name. Maps if user mentions Technician, Assigned Staff, or worker.")
    equipment: Optional[str] = Field(None, description="Equipment or machine name. Maps if user mentions specific equipment, device, or machine.")
    spot_name: Optional[str] = Field(None, description="Maintenance location spot name. Maps if user mentions Spot, Spot Name, Location Spot, or area.")
    keyword: Optional[str] = Field(None, description="MANDATORY for general queries when no filters specified. Use for broad searches like 'show PPM', 'all schedules', 'list maintenance'. Essential for queries without specific criteria.")
    date_from: Optional[str] = Field(None, description="Planned start date in YYYY-MM-DD format. Maps if user mentions Start Date, Planned, or begins.")
    date_to: Optional[str] = Field(None, description="Planned end date in YYYY-MM-DD format. Maps if user mentions End Date, Planned, or finishes.")
    comp_from: Optional[str] = Field(None, description="Completion start date in YYYY-MM-DD format. Maps if user mentions Completed From, Finished, or begins.")
    comp_to: Optional[str] = Field(None, description="Completion end date in YYYY-MM-DD format. Maps if user mentions Completed To, Finished, or ends.")
    sla_min: Optional[int] = Field(None, description="Minimum resolution or completion time in minutes. Maps if user mentions SLA Min, Duration minimum.")
    sla_max: Optional[int] = Field(None, description="Maximum resolution or completion time in minutes. Maps if user mentions SLA Max, Duration maximum.")
    limit: Optional[int] = Field(default=None, description="Max number of results. Only set if user asks for a specific number (e.g. 'show 10'). For count/total queries (how many, total), MUST omit — do not set.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless requested.")


class BDMInput(BaseModel):
    """Schema for BDM tool. Covers breakdown complaints and reactive work orders."""
    user_id: Optional[str] = Field(None, description="Internal system-set user identifier strictly mandatory for all database and API queries. Never request from user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name strictly mandatory for all database and API queries. Never request from user.")
    complaint_no: Optional[str] = Field(None, description="Complaint or breakdown number identifier. Maps if user mentions specific complaint number or ID.")
    status: Optional[str] = Field(None, description="Complaint status or lifecycle state. Maps if user mentions Status, Status Name, or complaint state.")
    priority: Optional[str] = Field(None, description="Complaint urgency or importance level. Maps if user mentions Priority, Urgency Level, or Severity.")
    stage: Optional[str] = Field(None, description="Complaint workflow or process stage. Maps if user mentions Stage, Complaint Stage, or phase.")
    complaint_type: Optional[str] = Field(None, description="Failure or issue category type. Maps if user mentions Complaint Type, Category, or type.")
    complaint_mode: Optional[str] = Field(None, description="Complaint reporting source or mode. Maps if user mentions Complaint Mode, Reporting Mode, or source.")
    complaint_nature: Optional[str] = Field(None, description="Failure or issue description. Maps if user mentions Nature, Failure, Issue, or description.")
    wo_type: Optional[str] = Field(None, description="Work order classification or type. Maps if user mentions Work Order Type, WO Type, or classification.")
    service_type: Optional[str] = Field(None, description="Service category or type. Maps if user mentions Service Type, Service, or category type.")
    division: Optional[str] = Field(None, description="Organizational division or business unit. Maps if user mentions Division, Division Name, DivisionName.")
    discipline: Optional[str] = Field(None, description="Technical specialty discipline domain. Maps if user mentions Discipline, Discipline Name, DisciplineName.")
    locality: Optional[str] = Field(None, description="Geographic location or site area. Maps if user mentions Locality, Complaint Location, Site, Region.")
    building: Optional[str] = Field(None, description="Building or structure name. Maps if user mentions Building, Complaint Building, Structure, Facility.")
    floor: Optional[str] = Field(None, description="Floor level or story designation. Maps if user mentions Floor, Complaint Floor, Level, Story.")
    contract: Optional[str] = Field(None, description="Service contract or agreement. Maps if user mentions Contract, Service Provider, or Agreement.")
    analysis_tech: Optional[str] = Field(None, description="Analysis technician or inspector name. Maps if user mentions Analysis Technician, Inspector, analyst.")
    execution_tech: Optional[str] = Field(None, description="Repair or execution technician name. Maps if user mentions Execution Technician, Repairer, technician.")
    complainer: Optional[str] = Field(None, description="Name of person who raised complaint. Maps if user mentions Complainer, Reporter, or user name.")
    spot_name: Optional[str] = Field(None, description="Complaint location spot name. Maps if user mentions Spot, Spot Name, Location Spot, area.")
    keyword: Optional[str] = Field(None, description="MANDATORY for general queries when no filters specified. Use for broad searches like 'show complaints', 'all breakdowns', 'list 10 issues'. Essential for queries without specific criteria.")
    date_from: Optional[str] = Field(None, description="Complaint reported date start in YYYY-MM-DD. Maps if user mentions Date From, Raised, or reported.")
    date_to: Optional[str] = Field(None, description="Complaint reported date end in YYYY-MM-DD. Maps if user mentions Date To, Raised, or reported.")
    completed_from: Optional[str] = Field(None, description="Resolution date start in YYYY-MM-DD format. Maps if user mentions Resolved From, Closed, completed.")
    completed_to: Optional[str] = Field(None, description="Resolution date end in YYYY-MM-DD format. Maps if user mentions Resolved To, Closed, completed.")
    limit: Optional[int] = Field(default=None, description="Max number of results. Only set if user asks for a specific number (e.g. 'show 10'). For count/total queries (how many, total), MUST omit — do not set.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless requested.")


class ChatRequest(BaseModel):
    """Request schema for chat endpoint"""
    query: str
    userName: str
    sessionId: str


class SessionRequest(BaseModel):
    """Request schema for fetching sessions or chat history"""
    userName: str
    sessionId: str = ""
