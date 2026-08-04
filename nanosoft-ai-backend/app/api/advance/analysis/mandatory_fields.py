"""
mandatory_fields.py

Defines the mandatory (required) fields per CMMS/FM table, used by the
Understanding Agent to validate/ground query classification against the
real schema. Field names are kept EXACTLY as provided by the source data
(including inconsistent casing like "Spotname" vs "SpotName") — do not
"correct" these, since the pipeline matches against the literal column
names in the underlying tables.
"""

MANDATORY_FIELDS = {

    # Assets: master inventory of physical equipment/assets tracked across
    # buildings and divisions.
    "Assets": [
        "AssetTagNo",
        "EquipmentName",
        "BuildingName",
        "DivisionName",
        "SpotName",
    ],

    # BDM (Breakdown Maintenance): reactive/unplanned maintenance complaints
    # raised when equipment fails, tracked with priority and status.
    "BDM": [
        "ComplaintNo",
        "WoStatus",
        "BuildingName",
        "prorityName",   
        "Spotname",      
        "DivisionName",
    ],

    # PPM (Planned Preventive Maintenance): scheduled/preventive maintenance
    # work orders tied to assets.
    "PPM": [
        "WorkOrder",
        "PPMStatus",
        "BuildingName",
        "DivisionName",
        "SpotName",
    ],

    # FA (Facility Audits): audit/rectification complaints raised during
    # facility inspections, tracked by stage.
    "FA": [
        "RMComplaintNo",
        "RMStageName",
        "BuildingName",
        "DivisionName",
        "SpotName",
    ],

    # SB (Space Booking): space/service booking requests (e.g. meeting
    # rooms, service types) tracked by stage.
    "SB": [
        "SBCreWorkOrder",
        "PPMStageName",
        "ServiceTypeName",
        "DivisionName",
        "SpotName",
        "BuildingName",
    ],
}


def get_mandatory_fields(table_name: str):
    """Return the mandatory field list for a given table name.

    Args:
        table_name: One of "Assets", "BDM", "PPM", "FA", "SB".

    Returns:
        List of mandatory field names for that table.

    Raises:
        KeyError: if table_name is not a recognized table.
    """
    table_lower = table_name.lower()
    for key, fields in MANDATORY_FIELDS.items():
        if key.lower() == table_lower:
            return fields
    raise KeyError(
        f"Unknown table '{table_name}'. "
        f"Valid tables: {list(MANDATORY_FIELDS.keys())}"
    )


def build_query_field_context(table_name: str, query_fields: list = None):
    """Build the full field set to pass to the model for a given query.

    Per query, the model must ALWAYS receive the module's mandatory fields
    (identified from the detected module/table), plus any additional
    query-specific fields extracted/inferred from the user's natural
    language query (e.g. date ranges, status values mentioned, equipment
    name mentioned, etc). Mandatory fields are non-negotiable and are
    always included even if the query text doesn't explicitly mention
    them — they ground the query in the correct schema.

    Example:
        User query: "show me open breakdown complaints in Building A"
        Detected module: "BDM"
        query_fields extracted from query: ["WoStatus", "BuildingName"]
        -> result includes BDM's mandatory fields (ComplaintNo, WoStatus,
           BuildingName, prorityName, Spotname, DivisionName) UNION the
           query_fields, deduplicated, mandatory fields always present.

    Args:
        table_name: The module/table detected for this query, one of
            "Assets", "BDM", "PPM", "FA", "SB".
        query_fields: Optional list of additional field names extracted
            from the user's query (e.g. by the Understanding Agent's NLU
            step). These are merged on top of the mandatory fields.

    Returns:
        dict with:
            "table": the resolved table name
            "mandatory_fields": the module's required fields (always sent)
            "query_fields": the deduplicated extra fields from the query
                             (excludes any already in mandatory_fields)
            "fields": final combined, de-duplicated field list to pass
                      downstream to the model/query builder

    Raises:
        KeyError: if table_name is not a recognized table.
    """
    mandatory = get_mandatory_fields(table_name)
    query_fields = query_fields or []

    # Extra query fields = anything in query_fields not already mandatory
    extra = [f for f in query_fields if f not in mandatory]

    # Final combined list, mandatory fields first, no duplicates
    combined = list(mandatory) + extra

    return {
        "table": table_name,
        "mandatory_fields": mandatory,
        "query_fields": extra,
        "fields": combined,
    }


if __name__ == "__main__":
    for table, fields in MANDATORY_FIELDS.items():
        print(f"{table}: {fields}")

    # Example: a BDM query that also mentions a priority filter in the
    # user's natural language text
    example = build_query_field_context(
        "BDM", query_fields=["prorityName", "WoStatus"]
    )
    print("\nExample per-query field context (BDM):")
    print(example)