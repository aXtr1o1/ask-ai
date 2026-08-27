"""
Route-level aggregate guard.

normalize_tool_args() (the regex-based value-correction chain that used to live
here) is gone — it existed only to patch up payloads guessed by the old
bind_tools flow. Normal ASK-AI's payload agent now builds is_aggregate and
group_by_columns directly from real metadata, so there is nothing left to
correct after the fact.
"""
from __future__ import annotations


def validate_aggregate_request(is_aggregate: bool, group_by_columns: list | None) -> None:
    """
    Route-level guard before calling sp_*_aggregate.
    Raises ValueError with a clear message if invalid.
    """
    if not is_aggregate:
        return
    if not group_by_columns:
        raise ValueError(
            "group_by_columns is required when is_aggregate is true. "
            "Example: group_by_columns=['BuildingName']"
        )
