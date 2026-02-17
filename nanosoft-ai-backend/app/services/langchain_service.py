"""
LangChain Service Module
Handles AI model initialization and message streaming
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.config import settings
from app.tools.facility_tools import ASSETS, COMPLAINTS, WORK_ORDERS


class LangChainService:
    """Manages LangChain model and tool interactions"""
    
    def __init__(self):
        """Initialize Gemini model with tools"""
        self.model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GOOGLE_API_KEY
        ).bind_tools([ASSETS, COMPLAINTS, WORK_ORDERS])
        
        self.tool_map = {
            "ASSETS": ASSETS,
            "COMPLAINTS": COMPLAINTS,
            "WORK_ORDERS": WORK_ORDERS,
        }
    
    def extract_chunk_text(self, chunk) -> str:
        """
        Safely extract text from streaming chunk
        Handles empty chunks and various content formats
        """
        content = chunk.content
        
        # Case 1: Empty chunk
        if not content:
            return ""
        
        # Case 2: Gemini list format
        if isinstance(content, list):
            if len(content) == 0:
                return ""
            return content[0].get("text", "")
        
        # Case 3: Normal string
        if isinstance(content, str):
            return content
        
        return str(content)
    
    async def process_query(self, messages: list) -> tuple[str, list]:
        """
        Process user query with tool calling support
        
        Args:
            messages: List of LangChain messages including system prompt and history
            
        Returns:
            Tuple of (final_response_text, updated_messages)
        """
        # Initial AI response (may contain tool calls)
        ai_msg = self.model.invoke(messages)
        
        # Handle tool calls if present
        if ai_msg.tool_calls:
            messages.append(ai_msg)
            
            for tool_call in ai_msg.tool_calls:
                tool_fn = self.tool_map[tool_call["name"]]
                tool_result = tool_fn.invoke(tool_call["args"])
                
                messages.append(
                    ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call["id"]
                    )
                )
        
        # Stream final response
        final_response_text = ""
        async for chunk in self.model.astream(messages):
            text = self.extract_chunk_text(chunk)
            if text:
                final_response_text += text
        
        return final_response_text, messages


# Global LangChain service instance
langchain_service = LangChainService()