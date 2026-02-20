"""
LangChain Service — AI model with tool support
"""
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.config import settings
from app.tools.facility_tools import ASSETS, PPM, BDM

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
                google_api_key=settings.GOOGLE_API_KEY
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

    def extract_chunk_text(self, chunk) -> str:
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
            if not user_id:
                raise ValueError("user_id is required")

            logger.info(f"💬 Processing query for user_id: {user_id}")

            # STEP 1 — First model call
            ai_msg = self.model.invoke(messages)

            # STEP 2 — If tool call exists
            if ai_msg.tool_calls:
                logger.info(f"🛠 Tool calls: {[tc['name'] for tc in ai_msg.tool_calls]}")

                for tool_call in ai_msg.tool_calls:
                    tool_fn = self.tool_map[tool_call["name"]]

                    args = tool_call.get("args", {})
                    args["user_id"] = user_id

                    tool_result = tool_fn.invoke(args)

                    messages.append(
                        ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call["id"]
                        )
                    )

                # STEP 3 — Call model again to generate final answer
                final_ai_msg = self.model.invoke(messages)

                logger.info("✅ Final response generated after tool execution")
                return final_ai_msg.content, messages

            else:
                logger.info("✅ No tool call — direct response")
                return ai_msg.content, messages

        except Exception as e:
            logger.error(f"❌ Query processing error: {e}", exc_info=True)
            raise

langchain_service = LangChainService()