import logging
import json
import requests
import asyncio
from typing import List, Dict, Tuple
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings
from app.tools.space_booking_tool import GET_SPOTS
from app.prompts.space_booking_prompt import SPACE_BOOKING_SYSTEM_PROMPT

logger = logging.getLogger("space_booking_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)

class SpaceBookingService:
    def __init__(self):
        try:
            self.model = ChatGoogleGenerativeAI(
                model=settings.GOOGLE_AI_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.0
            ).bind_tools([GET_SPOTS])
            
            self.system_prompt = SPACE_BOOKING_SYSTEM_PROMPT
            
            logger.info("🚀 SpaceBookingService initialized with tools")
        except Exception as e:
            logger.error(f"❌ SpaceBookingService init failed: {e}", exc_info=True)
            raise

    async def handle_space_booking(self, messages: list, user_name: str) -> tuple[str, str, list]:
        try:
            logger.info(f"🚀 Handling space booking for {user_name}")
            
            # Inject user_name into system prompt so model knows it
            sys_msg = SystemMessage(content=self.system_prompt.content + f"\n\nCURRENT USER_NAME: {user_name}")
            prompt_messages = [sys_msg] + messages
            
            ai_msg = await self.model.ainvoke(prompt_messages)
            
            # If tool called
            if ai_msg.tool_calls:
                prompt_messages.append(ai_msg)
                tool_data = None
                
                for tc in ai_msg.tool_calls:
                    if tc["name"] == "GET_SPOTS":
                        args = tc["args"]
                        b_name = args.get("building_name")
                        s_id = args.get("spot_id")
                        
                        tool_result = await GET_SPOTS.ainvoke({"user_name": user_name, "building_name": b_name, "spot_id": s_id})
                        
                        try:
                            parsed_res = json.loads(tool_result)
                            tool_data = parsed_res
                        except:
                            tool_data = {"error": "Invalid JSON response"}
                            
                        # Truncate content for LLM so it doesn't exceed context window
                        if isinstance(tool_data, dict) and "p_list" in tool_data:
                            # Compress data to save tokens but pass all items for RAG
                            compressed_spots = [
                                {
                                    "SpotIDPK": spot.get("SpotIDPK"),
                                    "SpotName": spot.get("SpotName"),
                                    "BuildingName": spot.get("BuildingName"),
                                    "LocalityName": spot.get("LocalityName"),
                                    "FloorName": spot.get("FloorName")
                                }
                                for spot in tool_data.get("p_list", [])
                            ]
                            llm_content = json.dumps({
                                "TotalCount": tool_data.get("TotalCount"),
                                "spots": compressed_spots
                            })
                        else:
                            llm_content = tool_result
                            
                        prompt_messages.append(ToolMessage(
                            name=tc["name"],
                            tool_call_id=tc["id"],
                            content=llm_content
                        ))
                
                # Second invocation for final response
                ai_msg2 = await self.model.ainvoke(prompt_messages)
                content = ai_msg2.content or ""
                
                # If we fetched data, pass the full list back to display as a table
                if tool_data and "p_list" in tool_data and len(tool_data["p_list"]) > 0:
                    final_response = {
                        "type": "large_dataset",
                        "context_summary": content,
                        "records": tool_data["p_list"]
                    }
                    return json.dumps(final_response), content, messages
                else:
                    return content, content, messages

            # No tool called
            content = ai_msg.content or ""
            return content, content, messages

        except Exception as e:
            logger.error(f"❌ Error in handle_space_booking: {e}", exc_info=True)
            err_msg = "Sorry, something went wrong while processing your space booking request."
            return err_msg, err_msg, messages

space_booking_service = SpaceBookingService()
