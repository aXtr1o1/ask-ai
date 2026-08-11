"""
Analysis Metadata — contracts module

Maintenance Contracts Register.
Records represent maintenance contracts, service agreements,
and sub-contracts registered in the facility management system.

Field names verified against actual contract_master table data.
"""

CONTRACTS_SCHEMA: dict[str, str] = {

    # --- Identifiers ---
    "ContractIDPK": (
        "Internal primary key for the contract record. "
        "Example: '1','2','10'"
    ),

    "ContractCode": (
        "Unique alphanumeric code assigned to the contract. Primary reference ID. "
        "Example: '50001','50002','50003-1'"
    ),

    "ContractName": (
        "Full descriptive name of the contract. "
        "Example: 'Maintenance of MEP Equipments (DEMO)','BHS - Maintenance','Chiller Maintenance'"
    ),

    # --- Customer / Organisation ---
    "CustomerName": (
        "Name of the customer, client, or service provider under this contract. "
        "Example: 'In-House Team','BHS - Service Provider','Daikin'"
    ),

    "OrganisationName": (
        "Name of the organisation that owns or manages this contract. "
        "Example: 'Nanosoft POC'"
    ),

    # --- Classification ---
    "ContractTypeName": (
        "Type of maintenance contract. Enum — use allowed values only."
    ),

    "ContractCategName": (
        "Category of the contract indicating whether it is managed in-house or outsourced. Enum — use allowed values only."
    ),

    "ContractGroupName": (
        "Grouping of the contract for reporting or hierarchy. Enum — use allowed values only."
    ),

    "ContStStatus": (
        "Current operational status of the contract. Enum — use allowed values only."
    ),

    "ContStTypes": (
        "Type classification of the contract status. Enum — use allowed values only."
    ),

    "TaxName": (
        "Name of the applicable tax on this contract. Enum — use allowed values only."
    ),

    "Period": (
        "Billing period or duration (number of billing cycles). "
        "Example: '8','24','4'"
    ),

    "ConPaymentTermsName": (
        "Payment terms agreed for this contract. Enum — use allowed values only."
    ),

    # --- Financial Values ---
    "ContractValue": (
        "Total contract value including VAT. "
        "Example: '4725000.00','6667500.00','37800.00'"
    ),

    "ConValueBeforVat": (
        "Contract value before VAT is applied. "
        "Example: '4500000.00','6350000.00','36000.00'"
    ),

    "VatAmount": (
        "Amount of VAT applicable on the contract. "
        "Example: '225000.00','317500.00','1800.00'"
    ),

    "ExtendedValue": (
        "Additional value added due to a contract extension. Zero if not extended. "
        "Example: '0.00','500000.00'"
    ),

    "TotalContractValue": (
        "Combined total value of the contract including extensions. "
        "Example: '0.00','5225000.00'"
    ),

    # --- Dates ---
    "ContractDate": (
        "Date the contract document was signed or formalised. Null if not recorded. "
        "Example: '2025-09-01','2024-01-15'"
    ),

    "StartDate": (
        "Date the contract coverage period begins. "
        "Example: '2025-09-01'"
    ),

    "EndDate": (
        "Date the contract coverage period ends. "
        "Example: '2027-08-31','2026-08-31'"
    ),

    "AnnualReviewDate": (
        "Scheduled date for the annual contract review. Null if not applicable. "
        "Example: '2027-07-31','2026-07-31'"
    ),

    "ExtendedDate": (
        "New end date after a contract extension has been approved. Null if not extended. "
        "Example: '2028-08-31'"
    ),

    # --- Staffing Counts ---
    "NoofEngineer": (
        "Number of engineers allocated to this contract. "
        "Example: '0','5'"
    ),

    "NoofSupervisor": (
        "Number of supervisors allocated to this contract. "
        "Example: '0','2'"
    ),

    "NoofPrimary": (
        "Number of primary staff allocated to this contract. "
        "Example: '0','10'"
    ),

    "ShiftNoofPrimary": (
        "Number of primary staff allocated per shift. "
        "Example: '0','5'"
    ),

    "ShiftNoofSecondary": (
        "Number of secondary staff allocated per shift. "
        "Example: '0','3'"
    ),

    "NoOfBilling": (
        "Number of billing cycles completed so far. "
        "Example: '0','4'"
    ),

    "NoofInvoice": (
        "Total number of invoices generated for this contract. "
        "Example: '0','8','24'"
    ),

    # --- Flags ---
    "IsActive": (
        "Boolean — true if the contract is currently active. "
        "Example: 'true','false'"
    ),

    "IsDraft": (
        "Boolean — true if the contract is saved as a draft and not yet finalised. "
        "Example: 'true','false'"
    ),

    "IsRenewal": (
        "Boolean — true if this contract is a renewal of a previous contract. "
        "Example: 'true','false'"
    ),

    "IsExtended": (
        "Boolean — true if this contract has been extended beyond its original end date. "
        "Example: 'true','false'"
    ),

    "IsTerminate": (
        "Boolean — true if this contract has been terminated. "
        "Example: 'true','false'"
    ),

    "IsNonContract": (
        "Boolean — true if this record represents a non-contract agreement. "
        "Example: 'true','false'"
    ),

    "IsPPM": (
        "Boolean — true if Planned Preventive Maintenance is enabled under this contract. "
        "Example: 'true','false'"
    ),

    "IsBDM": (
        "Boolean — true if Breakdown Maintenance is enabled under this contract. "
        "Example: 'true','false'"
    ),

    "IsDSM": (
        "Boolean — true if Demand Side Management is enabled under this contract. "
        "Example: 'true','false'"
    ),

    "IsIncident": (
        "Boolean — true if incident management is enabled under this contract. "
        "Example: 'true','false'"
    ),

    "IsCase": (
        "Boolean — true if case management is enabled under this contract. "
        "Example: 'true','false'"
    ),
}
