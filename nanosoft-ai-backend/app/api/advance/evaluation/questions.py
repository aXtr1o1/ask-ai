"""
Evaluation Questions

Toggle `enabled` to True/False to include or skip a question.
You can test with 5, 3, or 1 question by flipping the flags.
"""

QUESTIONS: list[dict] = [
    {
        "id": 1,
        "enabled": True,
        "question": (
            "Are there any standby remarks logged for open tickets that explain "
            "delays in execution?"
        ),
    },
    {
        "id": 2,
        "enabled": True,
        "question": (
            "What is the average ResponseTAT for P1 Critical emergency tickets?"
        ),
    },
    {
        "id": 3,
        "enabled": True,
        "question": (
            "Identify locations where breakdown repairs were raised during a "
            "scheduled housekeeping visit."
        ),
    },
    {
        "id": 4,
        "enabled": True,
        "question": (
            "How many assets currently listed as 'Online' in the asset master have "
            "experienced a cascading failure timeline, starting as a minor anomaly "
            "in facility audits and escalating into a 'P2 High' corrective ticket?"
        ),
    },
    {
        "id": 5,
        "enabled": True,
        "question": (
            "Identify facilities where facility audit remedial actions overlap with "
            "scheduled environmental service bookings."
        ),
    },
]
