"""
LangChain Service — AI model with tool support
"""
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.config import settings
from app.tools.facility_tools import ASSETS, PPM, BDM

import json

logger = logging.getLogger("langchain_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


class LangChainService:
    def __init__(self):
        try:
            self.model = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash-lite",
                google_api_key="AIzaSyD1beb6M9n72YO2PaLZXn9IzDUW_i6q6dA"#settings.GOOGLE_API_KEY
            ).bind_tools([ASSETS, PPM, BDM])

            self.tool_map = {
                "ASSETS": ASSETS,
                "PPM": PPM,
                "BDM": BDM,
            }
            logger.info("🚀 LangChainService initialized with ASSETS, PPM, BDM tools")
        except Exception as e:
            logger.error(f"❌ LangChainService init failed: {e}", exc_info=True)
            raise

    def extract_chunk_text(self, chunk) -> str: # later purpose for the streaming purpose
        content = chunk.content
        if not content:
            return ""
        if isinstance(content, list):
            return content[0].get("text", "") if content else ""
        if isinstance(content, str):
            return content
        return str(content)

    async def process_query(self, messages: list, user_id: str = None) -> tuple[str, list]:
        try:
            # user_id is always from the frontend request; use it for all tool calls
            if not user_id:
                raise ValueError("user_id is required (from frontend request)")
            logger.info(f"💬 Processing query for user_id: {user_id}")
            ai_msg = self.model.invoke(messages)
            logger.info("🤖 First model call | tool_calls=%s", bool(ai_msg.tool_calls))
            

            if ai_msg.tool_calls:
                logger.info(f"🛠 Tool calls: {[tc['name'] for tc in ai_msg.tool_calls]}")
                
                messages.append(ai_msg) 
                
                for tool_call in ai_msg.tool_calls:
                    tool_name = tool_call["name"]
                    tool_fn = self.tool_map[tool_call["name"]]
                    if tool_call.get("args") is None:
                        tool_call["args"] = {}
                    args_before = dict(tool_call["args"])

                    args = tool_call.get("args", {})
                    args["user_id"] = user_id
                    logger.info("📡 DB HIT | tool=%s | user_id=%s", tool_name, user_id)
                    
                    tool_result = tool_fn.invoke(args)
        
                    # ✅ EMPTY RESULT HANDLING
                    if isinstance(tool_result, dict):
                        p_count = tool_result.get("p_count", 0)
                        p_list = tool_result.get("p_list", [])

                        logger.info(
                            "📊 Tool result | %s | p_list_length=%s | p_count=%s",
                            tool_name, len(p_list), p_count
                        )

                        if p_count == 0:
                            return "No results found for the given query.", messages
                    else:
                        p_list = tool_result
                        p_count = len(p_list)

                    # ✅ CLEAR MESSAGE TO MODEL
                    messages.append(
                        ToolMessage(
                            content=json.dumps({
                                "message": f"{p_count} records found",
                                "records": p_list
                            }),
                            tool_call_id=tool_call["id"]
                        )
                    )

                # STEP 3 — Call model again to generate final answer
                final_ai_msg = self.model.invoke(messages)
                final_content = final_ai_msg.content
                 # ✅ FINAL SAFETY NET (NO EMPTY STRING EVER)
                if not final_content or str(final_content).strip() == "":
                    final_content = "No results found for the given query."

                logger.info("✅ Final response generated after tool execution")
                return final_content, messages

    

            else:
                content = ai_msg.content
                if not content or str(content).strip() == "":
                    content = "No results found for the given query."
                logger.info("✅ No tool call — direct response")
                return content, messages

        except Exception as e:
            logger.error(f"❌ Query processing error: {e}", exc_info=True)
            raise

langchain_service = LangChainService()