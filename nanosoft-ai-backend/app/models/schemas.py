"""
Pydantic Schemas for API Requests (Space Booking tool inputs, chat/session requests).

The Assets/PPM/BDM/FA/SB/Contract/Employee input schemas that used to live here were
only ever consumed as LangChain `args_schema=` for the old bind_tools-based tool
selection. Normal ASK-AI now selects modules via the Understanding Agent and builds
each module's payload from Advance's own metadata/enum registries, so those schemas
are gone — see app/services/langchain_service.py.
"""
from pydantic import BaseModel, Field
from typing import Optional, List


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
    isAdvance: bool = False
    advance_result: Optional[dict] = None


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
    isAdvanceAskAI: Optional[bool] = False

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
