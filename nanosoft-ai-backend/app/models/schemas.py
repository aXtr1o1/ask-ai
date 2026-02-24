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
    user_id: Optional[str] = Field(None, description="Internal system-set ID; strictly mandatory for all queries. Never request this from the user.")
    status: Optional[str] = Field(None, description="Maps if user mentions 'Status' or 'Status Name'. Strictly mandatory fallback for offline/online states.")
    asset_tag_no: Optional[str] = Field(None, description="Unique identification number for equipment. Use strictly for tag-based searches. Do not guess value.")
    condition: Optional[str] = Field(None, description="Physical state of asset. Map here only if user explicitly mentions 'Condition' or 'State'.")
    priority: Optional[str] = Field(None, description="Criticality level of equipment. Map here only if user explicitly mentions 'Priority' or 'Urgency'.")
    asset_type: Optional[str] = Field(None, description="Category of equipment. Maps if user mentions 'Asset Type', 'Type', or 'Asset Type Name'.")
    division: Optional[str] = Field(None, description="Organizational unit. Maps if user mentions 'Division', 'Division Name', or 'DivisionName'. Strictly follow.")
    discipline: Optional[str] = Field(None, description="Technical specialty. Maps if user mentions 'Discipline', 'Discipline Name', or 'DisciplineName'. Strictly follow.")
    locality: Optional[str] = Field(None, description="Geographic area or site. Map here only if user explicitly mentions 'Locality' or 'Location'.")
    building: Optional[str] = Field(None, description="Specific structure name. Map here only if user explicitly mentions 'Building' or 'Building Name'.")
    floor: Optional[str] = Field(None, description="Level within building. Map here only if user explicitly mentions 'Floor' or 'Floor Name'.")
    owner: Optional[str] = Field(None, description="Entity responsible for asset. Map here only if user explicitly mentions 'Owner' or 'Department'.")
    make: Optional[str] = Field(None, description="Equipment manufacturer name. Map here only if user explicitly mentions 'Make', 'Manufacturer', or 'Brand'.")
    model: Optional[str] = Field(None, description="Specific model designation. Map here only if user explicitly mentions 'Model' or 'Model Name'.")
    service_area: Optional[str] = Field(None, description="Functional area served. Map here only if user explicitly mentions 'Service Area' or 'Zone'.")
    trade_group: Optional[str] = Field(None, description="Maintenance team group. Map here only if user explicitly mentions 'Trade Group' or 'Team'.")
    on_hold: Optional[bool] = Field(None, description="Boolean flag for frozen assets. Set true only if user explicitly mentions 'On Hold'.")
    is_snagged: Optional[bool] = Field(None, description="Boolean flag for defects. Set true only if user explicitly mentions 'Snagged' or 'Defects'.")
    is_scraped: Optional[bool] = Field(None, description="Boolean flag for decommissioned assets. Set true if user mentions 'Scraped' or 'Disposed'.")
    enable_ppm: Optional[bool] = Field(None, description="Filter for scheduled maintenance assets. Set true if user mentions 'PPM Enabled' or 'Planned'.")
    enable_bdm: Optional[bool] = Field(None, description="Filter for breakdown-ready assets. Set true if user mentions 'BDM Enabled' or 'Reactive'.")
    barcode: Optional[str] = Field(None, description="Physical scan code. Map here only if user explicitly mentions 'Barcode' or 'Scan ID'.")
    keyword: Optional[str] = Field(None, description="Mandatory fallback for any terms not explicitly labeled as a field. Use for general searches.")
    date_from: Optional[str] = Field(None, description="Installation start range. Use YYYY-MM-DD. Map only if user mentions 'From Date' or 'Installed'.")
    date_to: Optional[str] = Field(None, description="Installation end range. Use YYYY-MM-DD. Map only if user mentions 'To Date' or 'Installed'.")
    limit: Optional[int] = Field(default=None, description="Max number of results. Only set if user explicitly asks for a specific number (e.g. 'show 10'). For count/total queries (how many, total), MUST omit — do not set.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless explicitly requested.")


class PPMInput(BaseModel):
    """Schema for PPM tool. Covers planned preventive maintenance schedules."""
    user_id: Optional[str] = Field(None, description="Internal system-set ID; strictly mandatory for all queries. Never request this from the user.")
    status: Optional[str] = Field(None, description="Maps if user mentions 'PPM Status' or 'Status Name'. Mandatory for filtering schedule states.")
    stage: Optional[str] = Field(None, description="Maintenance workflow step. Map here only if user explicitly mentions 'Stage' or 'Workflow Step'.")
    frequency: Optional[str] = Field(None, description="Interval of maintenance. Map here only if user mentions 'Frequency', 'Daily', 'Weekly', or 'Monthly'.")
    division: Optional[str] = Field(None, description="Organizational unit. Maps if user mentions 'Division', 'Division Name', or 'DivisionName'. Strictly follow.")
    discipline: Optional[str] = Field(None, description="Technical specialty. Maps if user mentions 'Discipline', 'Discipline Name', or 'DisciplineName'. Strictly follow.")
    locality: Optional[str] = Field(None, description="Geographic area. Map here only if user explicitly mentions 'Locality' or 'PPM Location'.")
    building: Optional[str] = Field(None, description="Structure name. Map here only if user explicitly mentions 'Building' or 'PPM Building'.")
    floor: Optional[str] = Field(None, description="Level designation. Map here only if user explicitly mentions 'Floor' or 'PPM Floor'.")
    contract: Optional[str] = Field(None, description="Service agreement name. Map here only if user explicitly mentions 'Contract' or 'Agreement'.")
    tech: Optional[str] = Field(None, description="Maintenance worker name. Map here only if user explicitly mentions 'Technician' or 'Assigned Staff'.")
    keyword: Optional[str] = Field(None, description="Mandatory fallback for any terms not explicitly labeled as a field. Use for general searches.")
    date_from: Optional[str] = Field(None, description="Planned start range. Use YYYY-MM-DD. Map if user mentions 'Start Date' or 'Planned'.")
    date_to: Optional[str] = Field(None, description="Planned end range. Use YYYY-MM-DD. Map if user mentions 'End Date' or 'Planned'.")
    comp_from: Optional[str] = Field(None, description="Completion start range. Use YYYY-MM-DD. Map if user mentions 'Completed From' or 'Finished'.")
    comp_to: Optional[str] = Field(None, description="Completion end range. Use YYYY-MM-DD. Map if user mentions 'Completed To' or 'Finished'.")
    sla_min: Optional[int] = Field(None, description="Minimum resolution minutes. Map here only if user explicitly mentions 'SLA Min' or 'Duration'.")
    sla_max: Optional[int] = Field(None, description="Maximum resolution minutes. Map here only if user explicitly mentions 'SLA Max' or 'Duration'.")
    limit: Optional[int] = Field(default=None, description="Max number of results. Only set if user explicitly asks for a specific number (e.g. 'show 10'). For count/total queries (how many, total), MUST omit — do not set.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless explicitly requested.")


class BDMInput(BaseModel):
    """Schema for BDM tool. Covers breakdown complaints and reactive work orders."""
    user_id: Optional[str] = Field(None, description="Internal system-set ID; strictly mandatory for all queries. Never request this from the user.")
    status: Optional[str] = Field(None, description="Maps if user mentions 'Status' or 'Status Name'. Mandatory for filtering complaint lifecycle states.")
    priority: Optional[str] = Field(None, description="Complaint urgency level. Map here only if user explicitly mentions 'Priority' or 'Urgency Level'.")
    stage: Optional[str] = Field(None, description="Complaint workflow step. Map here only if user explicitly mentions 'Stage' or 'Complaint Stage'.")
    complaint_type: Optional[str] = Field(None, description="Category of failure. Map here only if user explicitly mentions 'Complaint Type' or 'Category'.")
    complaint_mode: Optional[str] = Field(None, description="Source of registration. Map here only if user mentions 'Complaint Mode' or 'Reporting Mode'.")
    complaint_nature: Optional[str] = Field(None, description="Failure description. Map here only if user explicitly mentions 'Nature', 'Failure', or 'Issue'.")
    wo_type: Optional[str] = Field(None, description="Work order classification. Map here only if user explicitly mentions 'Work Order Type' or 'WO'.")
    service_type: Optional[str] = Field(None, description="Maintenance service category. Map here only if user explicitly mentions 'Service Type' or 'Service'.")
    division: Optional[str] = Field(None, description="Organizational unit. Maps if user mentions 'Division', 'Division Name', or 'DivisionName'. Strictly follow.")
    discipline: Optional[str] = Field(None, description="Technical specialty. Maps if user mentions 'Discipline', 'Discipline Name', or 'DisciplineName'. Strictly follow.")
    locality: Optional[str] = Field(None, description="Geographic area. Map here only if user explicitly mentions 'Locality' or 'Complaint Location'.")
    building: Optional[str] = Field(None, description="Structure name. Map here only if user explicitly mentions 'Building' or 'Complaint Building'.")
    floor: Optional[str] = Field(None, description="Level designation. Map here only if user explicitly mentions 'Floor' or 'Complaint Floor'.")
    contract: Optional[str] = Field(None, description="Service agreement name. Map here only if user explicitly mentions 'Contract' or 'Service Provider'.")
    analysis_tech: Optional[str] = Field(None, description="Assigned analyst name. Map here only if user explicitly mentions 'Analysis Technician' or 'Inspector'.")
    execution_tech: Optional[str] = Field(None, description="Repair technician name. Map here only if user explicitly mentions 'Execution Technician' or 'Repairer'.")
    complainer: Optional[str] = Field(None, description="Reporting person's name. Map here only if user explicitly mentions 'Complainer' or 'Raised By'.")
    keyword: Optional[str] = Field(None, description="Mandatory fallback for any terms not explicitly labeled as a field. Use for general searches.")
    date_from: Optional[str] = Field(None, description="Reported start range. Use YYYY-MM-DD. Map if user mentions 'Date From' or 'Raised'.")
    date_to: Optional[str] = Field(None, description="Reported end range. Use YYYY-MM-DD. Map if user mentions 'Date To' or 'Raised'.")
    completed_from: Optional[str] = Field(None, description="Resolution start range. Use YYYY-MM-DD. Map if user mentions 'Resolved From' or 'Closed'.")
    completed_to: Optional[str] = Field(None, description="Resolution end range. Use YYYY-MM-DD. Map if user mentions 'Resolved To' or 'Closed'.")
    limit: Optional[int] = Field(default=None, description="Max number of results. Only set if user explicitly asks for a specific number (e.g. 'show 10'). For count/total queries (how many, total), MUST omit — do not set.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless explicitly requested.")

class ChatRequest(BaseModel):
    """Request schema for chat endpoint"""
    query: str
    userId: str
    sessionId: str