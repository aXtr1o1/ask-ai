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
            # user_id is always from the frontend request; use it for all tool calls
            if not user_id:
                raise ValueError("user_id is required (from frontend request)")
            logger.info(f"💬 Processing query for user_id: {user_id}")
            ai_msg = self.model.invoke(messages)

            if ai_msg.tool_calls:
                logger.info(f"🛠 Tool calls: {[tc['name'] for tc in ai_msg.tool_calls]}")
                messages.append(ai_msg)

                for tool_call in ai_msg.tool_calls:
                    tool_fn = self.tool_map[tool_call["name"]]
                    if tool_call.get("args") is None:
                        tool_call["args"] = {}
                    args_before = dict(tool_call["args"])

                    # Always use the request user_id (constant from frontend)
                    tool_call["args"]["user_id"] = user_id
                    args_after = dict(tool_call["args"])

                    logger.info(f"🔑 DEBUG Tool '{tool_call['name']}': args before inject={args_before!r}")
                    logger.info(f"🔑 DEBUG Tool '{tool_call['name']}': args after inject user_id={user_id!r} -> {args_after!r}")

                    tool_result = tool_fn.invoke(tool_call["args"])
                    messages.append(
                        ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call["id"]
                        )
                    )
                    logger.info(f"✅ Tool '{tool_call['name']}' executed for user_id: {user_id}")
            else:
                logger.info(f"🔑 DEBUG: No tool calls this turn (model replied without calling a tool)")

            final_response_text = ""
            async for chunk in self.model.astream(messages):
                text = self.extract_chunk_text(chunk)
                if text:
                    final_response_text += text

            logger.info("✅ Query processed successfully")
            return final_response_text, messages

        except Exception as e:
            logger.error(f"❌ Query processing error: {e}", exc_info=True)
            raise

langchain_service = LangChainService()