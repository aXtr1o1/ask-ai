"""
Pydantic Schemas for LangChain Tools and API Requests
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
import re
from app.models.column_validation import AllColumns
# ==========================================
# ✅ LANGCHAIN TOOL INPUT SCHEMAS
# ==========================================

class AssetsInput(BaseModel):
    """
    Schema for ASSETS tool. Covers physical equipment and master records.
    CRITICAL RULE FOR ALL FIELDS: NEVER auto-correct, modify, or truncate the user's text to match 'Example values'. Always extract the EXACT wording and spacing typed by the user.
    """
    user_id: Optional[str] = Field(None, description="Internal system-set ID; strictly mandatory for all queries. Never request this from the user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name; strictly mandatory for all queries. Never request this from the user.")
    asset_tag_no: Optional[str] = Field(None, description="Unique tag number that identifies the asset. Format is always alphanumeric with dashes — NEVER a plain number. Map ONLY when user explicitly mentions a tag number in this format. Example values: L1-HVAC-CHL-3827, AJ-DV-DV-3826, T-A1-DV-DV-3825, DM-FF&AS-FE-13802. Do NOT use for pure numeric values — map those to asset_barcode instead.")
    asset_barcode: Optional[str] = Field(None, description="Barcode number printed on the asset label. Format is always a pure numeric string (digits only, no dashes or letters). Map here if the user provides ANY plain numeric ID or mentions 'Barcode' or 'Asset Barcode'. Example values: 1731251675376, 1731251675374, 1954391. Do NOT map alphanumeric values here — use asset_tag_no for those.")
    equipment_name: Optional[str] = Field(None, description="Name or description of the equipment or asset type. Map if user mentions 'Equipment Name' or 'EquipmentName'. Example values: Chiller 1, Heavy Loader, High Loader 10, Pushback Tractor, Fire Extinguisher.")
    equipment_ref_no: Optional[str] = Field(None, description="Equipment reference number. Map if user mentions 'Ref No', 'Reference Number', or 'EquipmentRefNo'. Example values: REF-1234, EQP-001.")
    serial_no: Optional[str] = Field(None, description="Filter by serial number. Map if user mentions 'Serial', 'Serial No', 'Serial Number', or 'S/N'.")
    status: Optional[str] = Field(None, description="Current operational status of the asset. Map if user mentions 'Status' or 'Status Name'. Example values: Online, Offline.")
    condition: Optional[str] = Field(None, description="Physical condition of the asset as assessed. Map if user mentions 'Condition' or 'State'. Example values: Good, Bad, Fair, Under Repair.")
    priority: Optional[str] = Field(None, description="Maintenance priority level assigned to the asset. Map if user mentions 'Priority' or 'Urgency'. Example values: Critical, High, Medium, Low.")
    asset_type: Optional[str] = Field(None, description="Category or type of the asset. Map if user mentions 'Asset Type', 'Type', or 'AssetTypeName'.")
    division: Optional[str] = Field(None, description="Division or system category the asset belongs to. Map if user mentions 'Division', 'Division Name', or 'DivisionName'. Example values: HVAC System, Duty Vehicles, Electrical System, Plumbing System, Fire Fighting and Alarm system, HVAC & PLUMBING SYSTEMS.")
    discipline: Optional[str] = Field(None, description="Technical discipline or trade the asset belongs to. Map if user mentions 'Discipline', 'Discipline Name', or 'DisciplineName'. Example values: CHILLER, Duty Vehicles, Fire Extinguisher, Plumbing, Electrical.")
    locality: Optional[str] = Field(None, description="Physical location zone or geographic area (e.g. district, complex, community, airside zone). Do NOT map indoor rooms or common areas here — map those to 'spot_name'. Example values: Al Jurf, Terminal A1, Terminal - A2, Ajman, Doha, Airside Area.")
    locality_code: Optional[str] = Field(None, description="Filter by a SPECIFIC locality code (e.g., RUW, AUH). Do NOT use this field if the user asks for a breakdown or grouping (e.g., 'by locality code'). If they ask to group, leave this empty and use group_by_columns=['LocalityCode'] instead.")
    building: Optional[str] = Field(None, description="Name of the building where the asset is installed. Map if user mentions 'Building' or 'Building Name'. Example values: Camp, Villa 4, Passenger Terminal Building T1 (Demo), Old Airport Terminal, VIP Terminal, Building 1 - Residential High Rise, Airfield Fire Fighting Station Building.")
    floor: Optional[str] = Field(None, description="Floor within the building where the asset is located. Map if user mentions 'Floor' or 'Floor Name'. CRITICAL: NEVER translate ordinal words to numbers. If the user types 'first floor' or 'second floor', you MUST pass 'first floor' or 'second floor' exactly as typed. Do NOT translate it to 'Floor 1' or 'Floor 2'. Example values: Ground Floor, Roof Level, Roof Top, Apron Level, Parking Floor 5.")
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
    keyword: Optional[str] = Field(None, description="General text search when the term does not map cleanly to another field.")
    date_from: Optional[str] = Field(None, description="Start date range. Use YYYY-MM-DD.")
    date_to: Optional[str] = Field(None, description="End date range. Use YYYY-MM-DD.")
    limit: Optional[int] = Field(default=None, description="Max number of results. CRITICAL: You MUST set this to an integer if the user asks for a specific number (e.g., 'list 5 assets' or 'give me five' -> set limit=5). For count queries MUST omit.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless requested.")
    is_aggregate: Optional[bool] = Field(default=False, description="Set True when the user explicitly asks for a breakdown OR asks 'how many [Category/Field]' (e.g., 'how many LocalityName', 'how many loaclityName', 'how many Status'). Leave False for simple total counts or filtering by a specific value (e.g. 'how many in HVAC').")
    group_by_columns: Optional[List[AllColumns]] = Field(default=None, description="List of columns to group by. Only fill when is_aggregate=True. CRITICAL: If the user asks to group by a specific field like Frequency or Category, pass exactly that column name (e.g. FrequencyName) even if it's not strictly listed here, so the tool can validate it. Valid columns: DivisionName, DisciplineName, BuildingName, FloorName, LocalityName, LocalityCode, StatusName, ConditionName, PriorityName, AssetTypeName, EquipmentName, MakeName, ModelName, SpotName, TradeGroupName, ServiceAreaName, OnHold, IsSnagged, IsScraped, IsEnablePPM, IsEnableBDM.")
    aggregate_function: Optional[str] = Field(default=None, description="The mathematical function to apply when grouping data. Use COUNT, SUM, or AVG for grouped distributions. Do not use this field for a simple total count.")
    



class PPMInput(BaseModel):
    """
    Schema for PPM tool. Covers planned preventive maintenance schedules.
    CRITICAL RULE FOR ALL FIELDS: NEVER auto-correct, modify, or truncate the user's text to match 'Example values'. Always extract the EXACT wording and spacing typed by the user.
    """
    user_id: Optional[str] = Field(None, description="Internal system-set ID; strictly mandatory for all queries. Never request this from the user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name; strictly mandatory for all queries. Never request this from the user.")
    work_order: Optional[str] = Field(None, description="Unique work order number for the PPM task. Map if user mentions 'Work Order' or 'WO Number'. Example values: 50010-DM-14264-2026, 50010-DM-14262-2026.")
    asset_tag_no: Optional[str] = Field(None, description="Tag number of the asset this PPM work order is raised for. Map if user mentions a specific asset tag. Example values: DM-FF&AS-FE-13802, DM-FF&AS-FE-13800, L1-HVAC-CHL-3827.")
    equipment_ref_no: Optional[str] = Field(None, description="Equipment reference number. Map if user mentions 'Ref No', 'Reference Number', or 'EquipmentRefNo'. Example values: REF-1234, EQP-001.")
    status: Optional[str] = Field(None, description="Current status of the PPM work order. Map if user mentions 'PPM Status' or 'Status Name'. Example values: Open, Closed.")
    stage: Optional[str] = Field(None, description="Current workflow stage of the PPM work order. Map if user mentions 'Stage' or 'Workflow Step'. Example values: Staff Yet to be Allocated, Technician Assigned, Work In Progress, Completed.")
    frequency: Optional[str] = Field(None, description="Maintenance frequency schedule for the PPM work order. Map if user mentions 'Frequency', 'Daily', 'Weekly', or 'Monthly'. Example values: QUARTERLY, MONTHLY, ANNUALLY, WEEKLY, BI-MONTHLY.")
    division: Optional[str] = Field(None, description="Division or system category the PPM asset belongs to. Map if user mentions 'Division'. Example values: Fire Fighting and Alarm system, HVAC System, BHS - Maintenance. CRITICAL: Do NOT include the word 'PPM' inside this field (e.g., use 'BHS - Maintenance' NOT 'BHS - Maintenance PPM').")
    discipline: Optional[str] = Field(None, description="Technical discipline of the asset the PPM is for. Map if user mentions 'Discipline', 'Discipline Name', or 'DisciplineName'. Example values: Fire Extinguisher, CHILLER, Plumbing, Electrical, Duty Vehicles.")
    locality: Optional[str] = Field(None, description="Physical location zone or geographic area of the PPM asset. Do NOT map indoor rooms here — map those to 'spot_name'. Example values: Doha, Terminal A1, Terminal - A2, Ajman, Al Jurf.")
    locality_code: Optional[str] = Field(None, description="Filter by a SPECIFIC locality code (e.g., RUW, AUH). Do NOT use this field if the user asks for a breakdown or grouping (e.g., 'by locality code'). If they ask to group, leave this empty and use group_by_columns=['LocalityCode'] instead.")
    building: Optional[str] = Field(None, description="Name of the building where the PPM asset is installed. Map if user mentions 'Building' or 'PPM Building'. Example values: Building 1 - Residential High Rise, Building 2 - Residential High Rise, Passenger Terminal Building T1 (Demo).")
    floor: Optional[str] = Field(None, description="Floor within the building where the PPM asset is located. Map if user mentions 'Floor' or 'PPM Floor'. CRITICAL: NEVER translate ordinal words to numbers. If the user types 'first floor' or 'second floor', you MUST pass 'first floor' or 'second floor' exactly as typed. Do NOT translate it to 'Floor 1' or 'Floor 2'. Example values: Ground Floor, Roof Level.")
    spot_name: Optional[str] = Field(None, description="Specific spot or room. CRITICAL: Extract EXACT spacing as typed by user (e.g. if user types 'Appartement-1801', do NOT add spaces like 'Appartement - 1801'). Example values: Electrical Room, AHU_R1201.")
    equipment: Optional[str] = Field(None, description="Name of the equipment or asset the PPM work order is for. Map if user mentions specific equipment. Example values: Fire Extinguisher, Chiller 1, AHU, Pump, Generator.")
    contract: Optional[str] = Field(None, description="Name of the maintenance contract under which the PPM is raised. Map if user mentions 'Contract' or 'Agreement'. Example values: Facility Management Residential Area.")
    tech: Optional[str] = Field(None, description="Name of the technician assigned to carry out this PPM work order. Map if user mentions 'Technician' or 'Assigned Staff'. Example values: Technician, John Smith.")
    keyword: Optional[str] = Field(None, description="General text search. CRITICAL: NEVER include the words 'PPM', 'BDM', 'work order' or 'complaint' in the keyword itself. CRITICAL: Extract exact spacing as provided by the user (e.g. if user types 'BHS - Maintenance', keep the spaces!).")
    date_from: Optional[str] = Field(None, description="Start range. Use YYYY-MM-DD.")
    date_to: Optional[str] = Field(None, description="End range. Use YYYY-MM-DD.")
    comp_from: Optional[str] = Field(None, description="Completion start range (WoCompletedDate). Use YYYY-MM-DD.")
    comp_to: Optional[str] = Field(None, description="Completion end range (WoCompletedDate). Use YYYY-MM-DD.")
    sla_min: Optional[int] = Field(None, description="Minimum SLADuration. Map if user mentions 'SLA Min'.")
    sla_max: Optional[int] = Field(None, description="Maximum SLADuration. Map if user mentions 'SLA Max'.")
    limit: Optional[int] = Field(default=None, description="Max number of results. CRITICAL: You MUST set this to an integer if the user asks for a specific number (e.g., 'list 5' -> set limit=5). For count queries MUST omit.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless requested.")
    is_aggregate: Optional[bool] = Field(default=False, description="Set True when the user explicitly asks for a breakdown OR asks 'how many [Category/Field]' (e.g., 'how many Status'). Leave False for simple total counts or filtering by a specific value.")
    group_by_columns: Optional[List[AllColumns]] = Field(default=None, description="List of columns to group by. Only fill when is_aggregate=True. CRITICAL: If the user asks to group by a specific field like Category or Complainer, pass exactly that column name even if it's not strictly listed here, so the tool can validate it. Valid columns: DivisionName, DisciplineName, BuildingName, FloorName, LocalityName, LocalityCode, FrequencyName, PPMStatus, PPMStageName, ContractName, SpotName.")
    aggregate_function: Optional[str] = Field(default=None, description="The mathematical function to apply when grouping data. Use COUNT, SUM, or AVG for grouped distributions. Do not use this field for a simple total count.")
    



class BDMInput(BaseModel):
    """
    Schema for BDM tool. Covers breakdown complaints and reactive work orders.
    CRITICAL RULE FOR ALL FIELDS: NEVER auto-correct, modify, or truncate the user's text to match 'Example values'. Always extract the EXACT wording and spacing typed by the user.
    """
    user_id: Optional[str] = Field(None, description="Internal system-set ID; strictly mandatory for all queries. Never request this from the user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name; strictly mandatory for all queries. Never request this from the user.")
    complaint_no: Optional[str] = Field(None, description="Unique complaint number identifying the BDM work order. Map if user mentions a specific complaint number. Example values: 1261, 1260, 1255, 1252.")
    asset_tag_no: Optional[str] = Field(None, description="Tag number of the asset linked to this complaint. Map if user mentions an asset tag. Example values: L1-HVAC-CHL-3827, T-A1-DV-DV-3825.")
    asset_barcode: Optional[str] = Field(None, description="Barcode of the asset linked to this complaint. Map if user mentions 'Barcode'. Example values: 1731251675376, 1731251675374. Null if no asset is associated.")
    client_wo_no: Optional[str] = Field(None, description="Client work order number. Map if user mentions 'Client WO' or 'ClientWoNo'.")
    status: Optional[str] = Field(None, description="Current status of the BDM complaint or work order. Map if user mentions 'Status' or 'Status Name'. Example values: Open, Closed.")
    priority: Optional[str] = Field(None, description="Priority level assigned to the complaint. Map ONLY for explicit priority/urgency (e.g. Low, low priority). NEVER map 'low count', 'lowest', or 'fewest' to this field. Example values: Critical, High, Medium, Low.")
    stage: Optional[str] = Field(None, description="Current workflow stage of the complaint. Map if user mentions 'Stage' or 'Complaint Stage'. Example values: Complaint / Service Request Raised, Staff Assigned for Analysis / Job Estimation, Staff Assigned for Work Execution, Complaint / Service Request - Closed.")
    complaint_type: Optional[str] = Field(None, description="Type of complaint raised. Allowed values: Service Request, Corrective Maintenance, Reactive Maintenance. Use the exact value the user says; never replace one allowed value with another.")
    complaint_header: Optional[str] = Field(None, description="Complaint header name. Map if user mentions 'Complaint Header' or 'ComplaintHeaderName'.")
    complaint_mode: Optional[str] = Field(None, description="Channel through which the complaint was submitted. Map if user mentions 'Complaint Mode' or 'Reporting Mode'. Example values: By Call, By Community Portal.")
    complaint_nature: Optional[str] = Field(None, description="Short description of the nature or subject of the complaint. Map if user mentions 'Nature', 'Failure', or 'Issue'. Example values: Water leakage in common area, light flickering, AC very noisy, Chiller vibration, fire related issues.")
    wo_type: Optional[str] = Field(None, description="Type of work order raised for the complaint. Map if user mentions 'Work Order Type' or 'WO'. Example values: General.")
    service_type: Optional[str] = Field(
        None,
        description=(
            "Service category (ServiceTypeName). USE when the user names a category ending in "
            "'Services' (e.g. 'Electrical Services', 'Plumbing Services') or says 'service type'. "
            "Do NOT map '... System' or bare 'division' here. "
            "Example values: Air Conditioning Services, Plumbing Services, Electrical Services, "
            "Environmental Services, IT Service Management."
        ),
    )
    division: Optional[str] = Field(
        None,
        description=(
            "Division/system category (DivisionName). Map ONLY when the user explicitly uses the word 'Division' or explicitly names a building system like 'Fire System' or 'Cooling System'. "
            "NEVER map entire sentences or conversational phrases like 'in the system'. "
            "If the user says '... Services', use service_type instead — NOT this field. "
            "Example values: Plumbing System, Electrical System, HVAC System, "
            "Fire Fighting and Alarm system. "
            "Bare 'Housekeeping' without 'Services' may be division — 'Housekeeping Services' "
            "is always service_type, never division."
        ),
    )
    discipline: Optional[str] = Field(
        None,
        description=(
            "Technical discipline (DisciplineName). USE only when the user says 'discipline' or "
            "a short trade name (e.g. 'Electrical', 'Plumbing', 'CHILLER') — NOT 'Electrical "
            "Services' or 'Electrical System'. "
            "Example values: CHILLER, Plumbing, Electrical, Fire Extinguisher."
        ),
    )
    locality: Optional[str] = Field(None, description="Physical location zone or geographic area where the complaint was raised. Do NOT map indoor rooms here — map those to 'spot_name'. Example values: Terminal - A2, Airside Area, Ajman, Doha, Terminal A1.")
    locality_code: Optional[str] = Field(None, description="Filter by a SPECIFIC locality code (e.g., RUW, AUH). Do NOT use this field if the user asks for a breakdown or grouping (e.g., 'by locality code'). If they ask to group, leave this empty and use group_by_columns=['LocalityCode'] instead.")
    building: Optional[str] = Field(None, description="Name of the building where the complaint was raised. Map if user mentions 'Building'. Example values: WATER TREATMENT PLANT, Warehouse building, Building 1 - Residential High Rise, Passenger Terminal Building T1 (Demo), Runway 18/36.")
    floor: Optional[str] = Field(None, description="Floor within the building where the complaint was raised. Map if user mentions 'Floor'. CRITICAL: NEVER translate ordinal words to numbers. If the user types 'first floor' or 'second floor', you MUST pass 'first floor' or 'second floor' exactly as typed. Do NOT translate it to 'Floor 1' or 'Floor 2'. Example values: Ground Floor.")
    spot_name: Optional[str] = Field(None, description="Specific spot or room within the floor where the complaint was raised. Map if user mentions a specific room or interior area. Example values: Common Area 9, Appartement-59, Warehouse building.")
    contract: Optional[str] = Field(None, description="Name of the maintenance contract under which this complaint is raised. Map if user mentions 'Contract' or 'Service Provider'. Example values: Facility Management Residential Area.")
    complainer: Optional[str] = Field(None, description="Name of the person who raised or submitted the complaint. Example values: eashaktech, Mohamed, naina muhamed, gowthaman, technician.")
    register_by: Optional[str] = Field(None, description="Username of the person who registered or created the complaint in the system. Map if user mentions 'Registered By' or 'RegisterBy'. Example values: helpdesk, admin, technician, eashaktech.")
    analysis_tech: Optional[str] = Field(None, description="Name of the technician assigned for the analysis or job estimation phase. Map if user mentions 'Analysis Technician' or 'Inspector'. Example values: Technician, eashaktech, Employee18.")
    execution_tech: Optional[str] = Field(None, description="Name of the technician assigned to execute or carry out the repair work. Map if user mentions 'Execution Technician' or 'Repairer'. Example values: Technician, Employee18. Empty if not yet assigned.")
    keyword: Optional[str] = Field(None, description="General text search when the term does not map cleanly to another field.")
    date_from: Optional[str] = Field(None, description="Reported start range. Use YYYY-MM-DD.")
    date_to: Optional[str] = Field(None, description="Reported end range. Use YYYY-MM-DD.")
    completed_from: Optional[str] = Field(None, description="Resolution start range (BDMWOCompletedDate). Use YYYY-MM-DD.")
    completed_to: Optional[str] = Field(None, description="Resolution end range (BDMWOCompletedDate). Use YYYY-MM-DD.")
    limit: Optional[int] = Field(default=None, description="Max number of results. CRITICAL: You MUST set this to an integer if the user asks for a specific number (e.g., 'list 5' -> set limit=5). For count queries MUST omit.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless requested.")
    is_aggregate: Optional[bool] = Field(default=False, description="Set True when the user explicitly asks for a breakdown OR asks 'how many [Category/Field]' (e.g., 'how many Status'). Leave False for simple total counts or filtering by a specific value.")
    group_by_columns: Optional[List[AllColumns]] = Field(
        default=None,
        description=(
            "Columns to group by when is_aggregate=True. Compare two '... Services' types "
            "(e.g. Electrical Services vs Housekeeping Services) → ['ServiceTypeName'] only. "
            "CRITICAL: If the user asks to group by a specific field like FrequencyName or RMCategoryName, "
            "pass exactly that column name even if it's not strictly listed here, so the tool can validate it. "
            "Valid: DivisionName, DisciplineName, BuildingName, FloorName, LocalityName, LocalityCode, "
            "WoStatus, PriorityName, StageName, ComplaintTypeName, ComplaintHeaderName, ComplaintModeName, "
            "ServiceTypeName, SpotName, ContractName."
        ),
    )
    aggregate_function: Optional[str] = Field(default=None, description="The mathematical function to apply when grouping data. Use COUNT, SUM, or AVG for grouped distributions. Do not use this field for a simple total count.")
    
class FAInput(BaseModel):
    """
    Schema for FA tool. Covers Facility Audit scheduled inspection complaints (FacilityAudit table).
    CRITICAL RULE FOR ALL FIELDS: NEVER auto-correct, modify, or truncate the user's text to match 'Example values'. Always extract the EXACT wording and spacing typed by the user.
    """
    user_id: Optional[str] = Field(None, description="Internal system-set ID. Never request from user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name. Never request from user.")
    complaint_no: Optional[str] = Field(None, description="Unique numeric complaint number that identifies this FA record. Map if user mentions a specific complaint number. Example values: 55, 56, 57, 58, 59, 60, 61, 62, 63.")
    complaint_code: Optional[str] = Field(None, description="Internal CCM complaint code assigned by the system. Map if user explicitly mentions 'Complaint Code' or 'CCM Code'.")
    x_complaint_no: Optional[str] = Field(None, description="External cross-reference complaint number. Map if user mentions 'X Complaint No' or 'External Complaint Number'.")
    priority: Optional[str] = Field(None, description="Maintenance priority level assigned to the FA complaint. Map ONLY for explicit priority wording. NEVER map 'low count' or 'lowest' to this field. Example values: Critical, High, Medium, Low.")
    stage: Optional[str] = Field(
        None,
        description=(
            "Workflow stage (RMStageName). FA has NO separate status/WoStatus field. "
            "Map user 'Open' or 'Closed' HERE (e.g. stage='Closed' matches 'Facility Audit - Closed'). "
            "Do NOT use category or keyword for Open/Closed. "
            "Example values: Facility Audit Request Raised, Facility Audit - Closed, "
            "Staf Assigned for Work Execution."
        ),
    )
    category: Optional[str] = Field(
        None,
        description=(
            "Audit inspection category (RMCategoryName) — e.g. Pest Control Checks. Map ONLY "
            "for 'audit category', 'inspection category', or a named audit type. Do NOT map "
            "'BuildingName Category', 'building categories', or 'categories of buildings' — "
            "those mean group_by_columns=['BuildingName'], not this field."
        ),
    )
    category_sub: Optional[str] = Field(None, description="Specific sub-category under the audit category providing more detail on the inspection type. Map if user mentions 'Sub Category' or specific check name. Example values: RODENT ACTIVITY.")
    division: Optional[str] = Field(None, description="Organizational division or department responsible for this FA complaint. Map if user mentions 'Division' or 'DivisionName'. Example values: Housekeeping.")
    locality: Optional[str] = Field(None, description="Geographic zone, district, or outdoor site area where the FA complaint is located. Do NOT use for indoor rooms or floors — map those to spot_name or floor. Example values: Doha, Ajman, Terminal A1.")
    locality_code: Optional[str] = Field(None, description="Filter by a SPECIFIC locality code (e.g., RUW, AUH). Do NOT use this field if the user asks for a breakdown or grouping (e.g., 'by locality code'). If they ask to group, leave this empty and use group_by_columns=['LocalityCode'] instead.")
    building: Optional[str] = Field(None, description="Name of the building where the FA inspection complaint was raised. Map if user mentions 'Building' or 'Building Name'. Example values: Building 1 - Residential High Rise, Building 2 - Residential High Rise.")
    floor: Optional[str] = Field(None, description="Specific floor level within the building where the FA complaint is located. Map if user mentions 'Floor' or 'Floor Name'. CRITICAL: NEVER translate ordinal words to numbers. If the user types 'first floor' or 'second floor', you MUST pass 'first floor' or 'second floor' exactly as typed. Do NOT translate it to 'Floor 1' or 'Floor 2'. Example values: Ground Floor.")
    spot_name: Optional[str] = Field(None, description="Specific indoor room, spot, or interior area within the floor where the FA complaint is raised. Map if user mentions a room or interior location. Example values: Garbage Room, Electrical Room, Common Area.")
    contract: Optional[str] = Field(None, description="Name of the maintenance or service contract under which this FA complaint is raised. Map if user mentions 'Contract' or 'Agreement'. Example values: Facility Management Residential Area.")
    tech: Optional[str] = Field(None, description="Name of the technician assigned to carry out the FA inspection work. Map if user mentions 'Technician' or 'Tech Name'. Example values: Technician.")
    frequency: Optional[str] = Field(None, description="Inspection recurrence schedule for this FA complaint. Map if user mentions 'Frequency', 'Monthly', 'Weekly', etc. Example values: MONTHLY, QUARTERLY, ANNUALLY, WEEKLY.")
    request_desc: Optional[str] = Field(None, description="Free-text description of the inspection request or task to be performed. Map if user mentions the nature of work like 'Pest Control', 'Housekeeping'. Example values: Pest Control.")
    is_withdraw: Optional[bool] = Field(None, description="Whether the FA complaint has been withdrawn. Set true to filter withdrawn complaints. FILTER only — for breakdown use is_aggregate=True with group_by_columns=['IsRMWithdraw'].")
    is_rework: Optional[bool] = Field(None, description="Whether the FA complaint requires rework. Set true to filter rework complaints. FILTER only — for breakdown use is_aggregate=True with group_by_columns=['IsRMRework'].")
    is_bms: Optional[bool] = Field(None, description="Whether this FA complaint is linked to the Building Management System (BMS). Map if user mentions 'BMS' in FA context.")
    is_active: Optional[bool] = Field(None, description="Whether the FA record is currently active. FILTER only — for breakdown use is_aggregate=True with group_by_columns=['IsActive'].")
    is_draft: Optional[bool] = Field(None, description="Whether the FA complaint is in draft state and not yet submitted. Map if user mentions 'Draft' in FA context.")
    keyword: Optional[str] = Field(None, description="General text search when the term does not map cleanly to another field.")
    date_from: Optional[str] = Field(None, description="Start date for filtering FA complaints by complaint date. Use YYYY-MM-DD format.")
    date_to: Optional[str] = Field(None, description="End date for filtering FA complaints by complaint date. Use YYYY-MM-DD format.")
    comp_from: Optional[str] = Field(None, description="Completion start date range (RMBDMWOCompletedDate). Use YYYY-MM-DD.")
    comp_to: Optional[str] = Field(None, description="Completion end date range. Use YYYY-MM-DD.")
    limit: Optional[int] = Field(default=None, description="Max records to return. CRITICAL: You MUST set this to an integer if the user asks for a specific number (e.g., 'list 5' -> set limit=5). Omit for count queries.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless requested.")
    is_aggregate: Optional[bool] = Field(default=False, description="Set True when the user explicitly asks for a breakdown OR asks 'how many [Category/Field]' (e.g., 'how many Status'). Leave False for simple total counts or filtering by a specific value.")
    group_by_columns: Optional[List[AllColumns]] = Field(
        default=None,
        description=(
            "Columns to group by when is_aggregate=True. 'BuildingName Category' or "
            "'building categories' → ['BuildingName'] only. RMCategoryName only for explicit "
            "audit/inspection category. "
            "CRITICAL: If the user asks to group by a specific field like WoStatus or ServiceTypeName, "
            "pass exactly that column name even if it's not strictly listed here, so the tool can validate it. "
            "Valid: DivisionName, BuildingName, FloorName, "
            "LocalityName, LocalityCode, PriorityName, RMStageName, RMCategoryName, RMCategorySubName, "
            "FrequencyName, ContractName, SpotName, IsRMWithdraw, IsRMRework, IsActive."
        ),
    )
    aggregate_function: Optional[str] = Field(default=None, description="The mathematical function to apply when grouping data. Use COUNT, SUM, or AVG for grouped distributions. Do not use this field for a simple total count.")
 
 
class SBInput(BaseModel):
    """
    Schema for SB tool. Covers Schedule-Based maintenance work orders (ScheduleBased table).
    CRITICAL RULE FOR ALL FIELDS: NEVER auto-correct, modify, or truncate the user's text to match 'Example values'. Always extract the EXACT wording and spacing typed by the user.
    """
    user_id: Optional[str] = Field(None, description="Internal system-set ID. Never request from user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name. Never request from user.")
    work_order: Optional[str] = Field(None, description="Unique work order number identifying this SB record. Map if user mentions 'Work Order' or 'WO Number'. Example values: AA-1-2026, AA-2-2026.")
    stage: Optional[str] = Field(None, description="Current workflow stage showing the progress status of this SB work order. Map if user mentions 'Stage'. Example values: Staff Yet to be Allocated, Technician Assigned, Work In Progress, Completed.")
    frequency: Optional[str] = Field(None, description="Recurrence schedule that determines how often this SB work order is generated. Map if user mentions 'Frequency', 'Monthly', 'Weekly', etc. Example values: MONTHLY, QUARTERLY, ANNUALLY, WEEKLY.")
    service_type: Optional[str] = Field(None, description="Type of service this SB work order belongs to, grouping it under a broad service category. Map if user mentions 'Service Type'. Example values: Environmental Services.")
    division: Optional[str] = Field(None, description="Organizational division or department responsible for this SB work order. Map if user mentions 'Division' or 'DivisionName'. Example values: Envrionmental Services.")
    discipline: Optional[str] = Field(None, description="Technical trade or discipline classification of this SB work order. Map if user mentions 'Discipline'. Example values: Landscaping.")
    locality: Optional[str] = Field(None, description="Geographic zone, district, or outdoor site area where the SB work order is to be performed. Do NOT use for indoor rooms — map those to spot_name. Example values: Ajman, Doha, Terminal A1.")
    locality_code: Optional[str] = Field(None, description="Filter by a SPECIFIC locality code (e.g., RUW, AUH). Do NOT use this field if the user asks for a breakdown or grouping (e.g., 'by locality code'). If they ask to group, leave this empty and use group_by_columns=['LocalityCode'] instead.")
    building: Optional[str] = Field(None, description="Name of the building or outdoor facility where this SB work order is assigned. Map if user mentions 'Building' or 'Building Name'. Example values: Al Safia Park, Building 1 - Residential High Rise.")
    floor: Optional[str] = Field(None, description="Specific floor level within the building for this SB work order. Map if user mentions 'Floor'. CRITICAL: NEVER translate ordinal words to numbers. If the user types 'first floor' or 'second floor', you MUST pass 'first floor' or 'second floor' exactly as typed. Do NOT translate it to 'Floor 1' or 'Floor 2'. Example values: Ground Floor.")
    spot_name: Optional[str] = Field(None, description="Specific indoor room or interior area within the floor for this SB work order. Map if user mentions a specific room or interior location. Example values: Garbage Room, Electrical Room.")
    contract: Optional[str] = Field(None, description="Name of the service or maintenance contract under which this SB work order is raised. Map if user mentions 'Contract' or 'Agreement'. Example values: Environmental Services - Annual Contract, Facility Management Residential Area.")
    tech: Optional[str] = Field(None, description="Name of the technician assigned to carry out this SB work order. Map if user mentions 'Technician' or 'Tech Name'. Example values: Technician.")
    is_withdraw: Optional[bool] = Field(None, description="Whether this SB work order has been withdrawn. Set true to filter withdrawn records. Map if user mentions 'withdrawn SB'.")
    is_reschedule: Optional[bool] = Field(None, description="Whether this SB work order has been rescheduled. Set true to filter rescheduled records. Map if user mentions 'rescheduled SB'.")
    is_rework: Optional[bool] = Field(None, description="Whether this SB work order requires rework. Set true to filter rework records. Map if user mentions 'rework SB'.")
    is_active: Optional[bool] = Field(None, description="Whether this SB record is currently active. Set true/false to filter active or inactive records.")
    is_draft: Optional[bool] = Field(None, description="Whether this SB record is in draft state. Map if user mentions 'draft SB'.")
    keyword: Optional[str] = Field(None, description="General text search when the term does not map cleanly to another field.")
    date_from: Optional[str] = Field(None, description="Start date for filtering SB work orders by scheduled date. Use YYYY-MM-DD format.")
    date_to: Optional[str] = Field(None, description="End date for filtering SB work orders by scheduled date. Use YYYY-MM-DD format.")
    comp_from: Optional[str] = Field(None, description="Completion start date range (SBCreWoCompletedDate). Use YYYY-MM-DD.")
    comp_to: Optional[str] = Field(None, description="Completion end date range. Use YYYY-MM-DD.")
    sla_min: Optional[float] = Field(None, description="Minimum SLA hours allowed for this SB work order. Map if user mentions 'SLA Min' or minimum SLA.")
    sla_max: Optional[float] = Field(None, description="Maximum SLA hours allowed for this SB work order. Map if user mentions 'SLA Max' or maximum SLA.")
    limit: Optional[int] = Field(default=None, description="Max records to return. CRITICAL: You MUST set this to an integer if the user asks for a specific number (e.g., 'list 5' -> set limit=5). Omit for count queries.")
    offset: Optional[int] = Field(default=None, description="Pagination offset. Omit unless requested.")
    is_aggregate: Optional[bool] = Field(default=False, description="Set True when the user explicitly asks for a breakdown OR asks 'how many [Category/Field]' (e.g., 'how many Status'). Leave False for simple total counts or filtering by a specific value.")
    group_by_columns: Optional[List[AllColumns]] = Field(default=None, description="Columns to group by when is_aggregate=True. CRITICAL: If the user asks to group by a specific field, pass exactly that column name even if it's not strictly listed here. Valid values: DivisionName, DisciplineName, BuildingName, FloorName, LocalityName, LocalityCode, PPMStageName, FrequencyName, ServiceTypeName, ContractName, SpotName.")
    aggregate_function: Optional[str] = Field(default=None, description="The mathematical function to apply when grouping data. Use COUNT, SUM, or AVG for grouped distributions. Do not use this field for a simple total count.")

class ContractInput(BaseModel):
    """
    Schema for CONTRACT tool. Covers service contracts, maintenance agreements, and client contracts.
    CRITICAL RULE FOR ALL FIELDS: NEVER auto-correct, modify, or truncate the user's text to match
    'Example values'. Always extract the EXACT wording and spacing typed by the user.
    """
    user_id: Optional[str] = Field(None, description="Internal system-set ID; strictly mandatory for all queries. Never request this from the user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name; strictly mandatory for all queries. Never request this from the user.")
    contract_id: Optional[int] = Field(None, description="The exact integer ID of the contract (ContractIDPK). Map this ONLY if the user provides a specific integer ID.")
    contract_code: Optional[str] = Field(None, description="The unique reference code for a specific contract record. Use this when the user gives a contract number or code to look up a particular contract. Example values: 50016, 50015, 50014.")
    contract_name: Optional[str] = Field(None, description="The full title or name of the contract. Use this when the user names a specific contract they want to find or asks about a contract by its title. Example values: Maintenance Group L India, Split Unit Maintenance.")
    customer_name: Optional[str] = Field(None, description="The client or company the contract is signed with. Use this when the user asks about contracts belonging to or issued to a specific company or client. Example values: Group L Services, Power Group.")
    contract_type: Optional[str] = Field(None, description="The broad classification that defines what kind of contract it is. Use this when the user asks for a specific type of contract. Example values: Annual Maintenance Contract.")
    contract_categ: Optional[str] = Field(None, description="A more specific category the contract falls under within its type. Use this when the user asks about contract categories. Example values: In-House.")
    contract_group: Optional[str] = Field(None, description="The grouping that organises related contracts together. Use this when the user asks about a particular contract group. Example values: Contract.")
    organisation: Optional[str] = Field(None, description="The organisation that manages or delivers the contract. Use this when the user asks about contracts under a specific organisation. Example values: Nanosoft POC.")
    status: Optional[str] = Field(None, description="The current lifecycle state of the contract. Use this when the user asks for live, expired, pending, or terminated contracts. Example values: Live, Expired, Pending, Terminated. NEVER use this for count aggregations — use is_aggregate=True with group_by_columns=['ContStStatus'] instead.")
    status_type: Optional[str] = Field(None, description="A sub-classification that further distinguishes the contract's status. Use this when the user specifically asks about the contract type being formal or informal. Example values: Contract, Non Contract.")
    tax_name: Optional[str] = Field(None, description="The tax or VAT rate applied to the contract's financial value. Use this when the user asks about contracts with a specific tax or VAT rate. Example values: VAT 5%.")
    period: Optional[str] = Field(None, description="The billing period or duration cycle agreed in the contract. Use this when the user asks about contracts with a specific billing frequency or period.")
    payment_terms: Optional[str] = Field(None, description="The payment schedule or terms that govern how the contract is billed. Use this when the user asks about payment cycles, billing terms, or how a contract is paid.")
    is_active: Optional[bool] = Field(None, description="Indicates whether the contract is currently active and in force. Set true when the user asks for currently active or live contracts; false for inactive ones. For a distribution count (active vs inactive), use is_aggregate=True with group_by_columns=['IsActive'] instead.")
    is_draft: Optional[bool] = Field(None, description="Indicates the contract has been created but not yet finalised or approved. Set true when the user asks about draft contracts or contracts that are still pending sign-off.")
    is_renewal: Optional[bool] = Field(None, description="Indicates this contract is a renewal of a previous agreement. Set true when the user asks about renewed or renewal contracts.")
    is_extended: Optional[bool] = Field(None, description="Indicates this contract's duration has been extended beyond its original end date. Set true when the user asks about contracts that have been given an extension.")
    is_terminate: Optional[bool] = Field(None, description="Indicates this contract was terminated before its natural end date. Set true when the user asks about terminated or cancelled contracts.")
    is_non_contract: Optional[bool] = Field(None, description="Indicates this is an informal or non-contract record rather than a formal signed agreement. Set true when the user asks about non-contract or informal agreements; false for formal contracts.")
    is_ppm: Optional[bool] = Field(None, description="Indicates the contract includes Planned Preventive Maintenance (PPM) as a covered service. Set true when the user asks which contracts cover or include PPM services. For a count breakdown, use is_aggregate=True with group_by_columns=['IsPPM'].")
    is_bdm: Optional[bool] = Field(None, description="Indicates the contract includes Breakdown Maintenance (BDM) as a covered service. Set true when the user asks which contracts cover BDM or reactive maintenance. For a count breakdown, use is_aggregate=True with group_by_columns=['IsBDM'].")
    is_dsm: Optional[bool] = Field(None, description="Indicates the contract includes Demand Side Management (DSM) services. Set true when the user asks about DSM-enabled contracts.")
    is_incident: Optional[bool] = Field(None, description="Indicates the contract covers incident management services. Set true when the user asks about contracts that include incident tracking.")
    is_case: Optional[bool] = Field(None, description="Indicates the contract covers case management services. Set true when the user asks about contracts that include case handling.")
    keyword: Optional[str] = Field(None, description="A free-text search term for anything the user mentions that doesn't match a specific contract field above. Pass the user's exact words. CRITICAL: Never include generic words like 'contract', 'show', or 'list' here — only specific meaningful search terms.")
    date_from: Optional[str] = Field(None, description="Filters contracts whose start date falls on or after this date. Use when the user asks about contracts starting from a certain date or time period. Use YYYY-MM-DD. Supports: 'today', 'this month', 'last month', 'this year', 'last year'.")
    date_to: Optional[str] = Field(None, description="Filters contracts whose end date falls on or before this date. Use when the user asks about contracts expiring by a certain date. Use YYYY-MM-DD. Supports relative keywords.")
    limit: Optional[int] = Field(default=None, description="The maximum number of contract records to return. Set this when the user asks for a specific number of results — e.g. 'show 5 contracts' means limit=5. For count-only queries, do NOT set this.")
    offset: Optional[int] = Field(default=None, description="Pagination offset — skip this many records before returning results. Only set if the user explicitly asks for a page or offset.")
    is_aggregate: Optional[bool] = Field(default=False, description="Set True when the user asks for a count breakdown grouped by a dimension — e.g. 'how many contracts per type', 'breakdown by status', 'how many ContractTypeName'. Leave False for simple total counts or when filtering for a specific value.")
    group_by_columns: Optional[List[AllColumns]] = Field(default=None, description="The database columns to group the result by when is_aggregate=True. Use the exact column name. Valid values: ContractTypeName, ContractCategName, ContractGroupName, OrganisationName, CustomerName, ContStStatus, ContStTypes, IsActive, IsDraft, IsRenewal, IsExtended, IsTerminate, IsPPM, IsBDM, IsDSM, IsIncident, IsCase, IsNonContract, Period, TaxName, ConPaymentTermsName.")
    aggregate_function: Optional[str] = Field(default=None, description="The aggregation function applied to each group. Use COUNT when the user asks how many, SUM for total values, AVG for averages. Do not set for a simple total count with no grouping.")


class EmployeeInput(BaseModel):
    """
    Schema for EMPLOYEE tool. Covers HR employee master records, staff profiles, and workforce data.
    CRITICAL RULE FOR ALL FIELDS: NEVER auto-correct, modify, or truncate the user's text to match
    'Example values'. Always extract the EXACT wording and spacing typed by the user.
    """
    user_id: Optional[str] = Field(None, description="Internal system-set ID; strictly mandatory for all queries. Never request this from the user.")
    user_name: Optional[str] = Field(None, description="Internal system-set user name; strictly mandatory for all queries. Never request this from the user.")
    employee_id: Optional[int] = Field(None, description="The exact integer ID of the employee (EmployeeIDPK). Map this ONLY if the user provides a specific integer ID.")
    employee_code: Optional[str] = Field(None, description="The unique HR code that identifies a specific employee. Use this when the user gives an employee ID or code to look up a particular person. Example values: E10001, E10002.")
    employee_name: Optional[str] = Field(None, description="The full name of the employee as recorded in the system. Use this when the user asks about a specific person by their full name. Example values: Yalcin Akbulut Akbulut, Adem Bal.")
    first_name: Optional[str] = Field(None, description="The employee's first or given name. Use this when the user provides only the first name of the person they are looking for. Example values: Adem, Yalcin Akbulut.")
    last_name: Optional[str] = Field(None, description="The employee's last name or family name. Use this when the user provides only a surname to search for. Example values: Bal, Akbulut.")
    organisation: Optional[str] = Field(None, description="The organisation the employee is part of. Use this when the user asks about employees belonging to a particular company or organisation. Example values: Nanosoft POC.")
    department: Optional[str] = Field(None, description="The department the employee works in. Use this when the user asks about employees in a specific team or department. Example values: Facility Management Operations.")
    designation: Optional[str] = Field(None, description="The job title or position the employee holds. Use this when the user asks about employees with a specific role, title, or position. Example values: Manager, Engineer.")
    classification: Optional[str] = Field(None, description="The HR classification assigned to the employee, grouping them by a staffing category. Use this when the user filters by employee classification. Example values: Self.")
    branch: Optional[str] = Field(None, description="The branch or office location the employee is assigned to. Use this when the user asks about employees based at a specific branch or office.")
    nature_of_work: Optional[str] = Field(None, description="The type of work or operational domain the employee performs. Use this when the user asks about employees by their work nature or function. Example values: FM Operations.")
    employee_type: Optional[str] = Field(None, description="The category type of the employee — whether primary, secondary, contract, etc. Use this when the user asks about a specific employee category. Example values: Primary.")
    employment_type: Optional[str] = Field(None, description="The employment basis — whether full-time, part-time, or other. Use this when the user asks about employees by their employment arrangement.")
    shift_name: Optional[str] = Field(None, description="The work shift the employee is assigned to. Use this when the user asks about employees on a specific shift or who work at certain times. Example values: Morning Shift, General Shift.")
    shift_code: Optional[str] = Field(None, description="The short code for the employee's assigned shift. Use this when the user references a shift by its code. Example values: 101, 102.")
    gender: Optional[str] = Field(None, description="The gender of the employee. Use this when the user asks specifically about male or female employees. Example values: Male, Female.")
    marital_status: Optional[str] = Field(None, description="The marital status of the employee. Use this when the user asks about employees filtered by marital status. Example values: Single, Married.")
    nationality: Optional[str] = Field(None, description="The nationality or country of citizenship of the employee. Use this when the user asks about employees of a specific nationality. Example values: Indian, Filipino, Pakistani.")
    country: Optional[str] = Field(None, description="The country of residence or origin of the employee. Use this when the user asks about employees from or residing in a specific country.")
    employee_group: Optional[str] = Field(None, description="The workforce group category the employee belongs to within the HR structure. Use this when the user asks about a specific employee grouping.")
    emp_grade: Optional[str] = Field(None, description="The salary or payroll grade level of the employee. Use this when the user asks about employees at a specific grade or pay band.")
    emp_title: Optional[str] = Field(None, description="The honorific title of the employee. Use this when the user asks about employees with a specific title prefix. Example values: Mr., Ms., Dr.")
    vehicle_no: Optional[str] = Field(None, description="The vehicle registration number assigned to or used by the employee. Use this when the user asks about an employee's assigned vehicle.")
    is_active: Optional[bool] = Field(None, description="Indicates whether the employee is currently working and active in the system. Set true when the user asks for currently active or working staff; false for resigned or inactive. For a distribution count (active vs inactive), use is_aggregate=True with group_by_columns=['IsActive'].")
    is_attendance_enable: Optional[bool] = Field(None, description="Indicates whether attendance tracking is turned on for this employee. Set true when the user asks about employees whose attendance is being tracked. For a count breakdown, use is_aggregate=True with group_by_columns=['IsAttendanceEnable'].")
    is_single_punch: Optional[bool] = Field(None, description="Indicates the employee uses single-punch (one-direction) attendance recording. Set true when the user asks about employees who use single punch mode.")
    keyword: Optional[str] = Field(None, description="A free-text search term for anything the user mentions that doesn't match a specific employee field above. Pass the user's exact words. CRITICAL: Never include generic words like 'employee', 'staff', 'show', or 'list' here — only specific meaningful search terms.")
    date_from: Optional[str] = Field(None, description="Filters employees who joined on or after this date. Use when the user asks about employees who joined from a certain date or period. Use YYYY-MM-DD. Supports: 'today', 'this month', 'last month', 'this year'.")
    date_to: Optional[str] = Field(None, description="Filters employees who joined on or before this date. Use when the user asks about employees who joined up to a certain date. Use YYYY-MM-DD. Supports relative keywords.")
    limit: Optional[int] = Field(default=None, description="The maximum number of employee records to return. Set this when the user asks for a specific number — e.g. 'show 5 employees' means limit=5. For count-only queries, do NOT set this.")
    offset: Optional[int] = Field(default=None, description="Pagination offset — skip this many records before returning results. Only set if the user explicitly asks for a page or offset.")
    is_aggregate: Optional[bool] = Field(default=False, description="Set True when the user asks for a count breakdown grouped by a dimension — e.g. 'how many employees per department', 'breakdown by nationality', 'how many DepartmentName'. Leave False for simple totals or when filtering for a specific value.")
    group_by_columns: Optional[List[AllColumns]] = Field(default=None, description="The database columns to group the result by when is_aggregate=True. Use the exact column name. Valid values: OrganisationName, DepartmentName, DesignationName, ClassificationName, Branch, NatureOfWorkName, EmployeeTypeName, EmploymentTypeName, ShiftName, EmpGenderName, NationalityName, CountryName, IsActive, IsAttendanceEnable, EmployeeGroupName, EmpGradeName, EmpTitleName.")
    aggregate_function: Optional[str] = Field(default=None, description="The aggregation function applied to each group. Use COUNT when the user asks how many, SUM for totals, AVG for averages. Do not set for a simple total count with no grouping.")


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
    isSpaceBooking: Optional[bool] = False

class ClientInsertionRequest(BaseModel):
    """Request schema for client insertion"""
    userId: str
    clientName: str
    userName: str
    service: str
    token: str

class BookSpotInput(BaseModel):
    user_name: str = Field(description="The client_name/user_name from the frontend context.")
    sub_user_name: Optional[str] = Field(default=None, description="The specific user making the booking, if any.")
    spot_code: str = Field(description="The unique Spot Code being booked (e.g., WRMF-NES).")
    spot_name: Optional[str] = Field(default="Unknown Spot", description="The name of the spot.")
    building_name: Optional[str] = Field(default="Unknown Building", description="The name of the building where the spot is located.")
    floor_name: Optional[str] = Field(default="Unknown Floor", description="The floor where the spot is located.")
    start_time: str = Field(description="Booking start datetime. Can be in YYYY-MM-DD HH:MM:00 (24-hour format) or include AM/PM (e.g., YYYY-MM-DD hh:mm AM/PM). CRITICAL: If the user has not explicitly provided a start time, or has omitted the year (e.g., they only typed month and day like 'July 10' without explicitly specifying the year, and it is not a structured calendar payload), DO NOT CALL THIS TOOL. You MUST reply conversationally and ask them to confirm the year or use the calendar. NEVER guess, assume, or auto-fill the year.")
    end_time: str = Field(description="Booking end datetime. Can be in YYYY-MM-DD HH:MM:00 (24-hour format) or include AM/PM (e.g., YYYY-MM-DD hh:mm AM/PM). CRITICAL: If the user has not explicitly provided an end time, or has omitted the year (e.g., they only typed month and day like 'July 10' without explicitly specifying the year, and it is not a structured calendar payload), DO NOT CALL THIS TOOL. You MUST reply conversationally and ask them to confirm the year or use the calendar. NEVER guess, assume, or auto-fill the year.")


class GetSpotsInput(BaseModel):
    user_name: str = Field(description="The client_name/user_name from the frontend context.")
    search_term: Optional[str] = Field(
        default="",
        description="The Spot Code, Spot Name, Building Name, Floor Name, or any search term/keyword typed by the user (e.g. 'floor 6', 'floor6', 'Building 1', 'WMR'). You MUST pass the user's search text exactly as entered."
    )

class GetBookingStatusInput(BaseModel):
    user_name: str = Field(description="The client_name/user_name from the frontend context.")
    booking_id: Optional[str] = Field(default=None, description="The 4-digit booking ID provided by the user. If omitted, returns all bookings for the user.")
