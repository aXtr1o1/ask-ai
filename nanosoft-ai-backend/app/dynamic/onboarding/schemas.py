"""
dynamic/onboarding/schemas.py
──────────────────────────────
Pydantic request models for the dynamic client onboarding system.

Models defined here:
    FieldConfig            → describes one field in a service's data schema
    OnboardServiceRequest  → body for POST /api/client/onboard/service
    SyncRequest            → body for POST /api/client/sync
"""

from pydantic import BaseModel
from typing import Dict, List


# ══════════════════════════════════════════════════════════════════════════════
# FIELD CONFIG
# Describes the type and behavior of a single field in a service's data schema.
# Used inside OnboardServiceRequest.fields_config.
# ══════════════════════════════════════════════════════════════════════════════

class FieldConfig(BaseModel):
    """
    Metadata for a single field in a service's data schema.

    Fields:
        type         → data type: "string" | "integer" | "boolean" | "date" | "datetime"
        aggregatable → if True, this field can be used in GROUP BY queries
                       (e.g. DivisionName → "how many assets per division")
        is_date      → if True, tool schema gets _from/_to filter pair for this field
                       (e.g. PurDate → PurDate_from, PurDate_to)
        description  → optional human-readable description shown in tool schema
    """
    type:         str
    aggregatable: bool = False
    is_date:      bool = False
    description:  str  = ""


# ══════════════════════════════════════════════════════════════════════════════
# ONBOARD SERVICE REQUEST
# Full payload needed to register a new client + service for the first time.
# ══════════════════════════════════════════════════════════════════════════════

class OnboardServiceRequest(BaseModel):
    """
    Request body for POST /api/client/onboard/service

    What each field is used for:
        client_name      → unique identifier for the client (used as composite key everywhere)
        user_id          → client's user ID (sent in API headers when fetching data)
        base_url         → root URL of the client's API (e.g. "https://poc.smartfm.cloud/askmeapi")
        token            → JWT token for authenticating against the client's API
        service_key      → unique identifier for this service (e.g. "assets", "workorders")
                           used as the LangChain tool name
        service_name     → human-readable name shown in system prompt and quota menu
        description      → short description of what data this service holds
        endpoint         → API path to call for fetching data (e.g. "/getAssets")
        unique_field     → field that uniquely identifies each record (used for upsert dedup)
        routing_keywords → words that trigger this tool when found in user queries
        fields_config    → dict of field_name → FieldConfig describing filterable fields

    Example:
    {
        "client_name":  "poc",
        "user_id":      1,
        "base_url":     "https://poc.smartfm.cloud/askmeapi",
        "token":        "your_jwt_token",
        "service_key":  "assets",
        "service_name": "Asset Management",
        "description":  "Tracks physical equipment across the organization.",
        "endpoint":     "/getAssets",
        "unique_field": "AssetTagNo",
        "routing_keywords": ["asset", "equipment", "barcode"],
        "fields_config": {
            "EquipmentName": { "type": "string",  "aggregatable": false, "is_date": false },
            "DivisionName":  { "type": "string",  "aggregatable": true,  "is_date": false },
            "YearOfManuf":   { "type": "integer", "aggregatable": true,  "is_date": false },
            "IsScraped":     { "type": "boolean", "aggregatable": false, "is_date": false },
            "PurDate":       { "type": "date",    "aggregatable": false, "is_date": true  }
        }
    }
    """
    client_name:      str
    user_id:          int
    base_url:         str
    token:            str
    service_key:      str
    service_name:     str
    description:      str
    endpoint:         str
    unique_field:     str
    routing_keywords: List[str]
    fields_config:    Dict[str, FieldConfig]


# ══════════════════════════════════════════════════════════════════════════════
# SYNC REQUEST
# Minimal payload needed to trigger a data re-sync for an existing service.
# Credentials are read from DB — caller does not need to pass them again.
# ══════════════════════════════════════════════════════════════════════════════

class SyncRequest(BaseModel):
    """
    Request body for POST /api/client/sync

    What each field is used for:
        client_name → identifies which client to sync (used to look up credentials)
        user_id     → used as part of the composite key in client_service_data
        service_key → identifies which service's data to refresh

    Example:
    {
        "client_name": "poc",
        "user_id":     1,
        "service_key": "assets"
    }
    """
    client_name: str
    user_id:     int
    service_key: str