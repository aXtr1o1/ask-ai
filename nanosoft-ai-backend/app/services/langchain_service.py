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
                    args = dict(tool_call["args"])
                    args["user_id"] = user_id

                    # Override limit for count queries — LLM often passes limit=1 incorrectly
                    user_query = ""
                    for m in reversed(messages):
                        if isinstance(m, HumanMessage):
                            user_query = (m.content or "") if isinstance(m.content, str) else ""
                            break
                    count_patterns = ("how many", "total", "number of", "count of", "count ", "how many ")
                    if any(p in user_query.lower() for p in count_patterns) and args.get("limit") is not None:
                        logger.info("📊 Count query detected — clearing limit=%s", args.get("limit"))
                        args["limit"] = None

                    logger.info("📡 DB HIT | tool=%s | user_id=%s | limit=%s", tool_name, user_id, args.get("limit"))
                    
                    tool_result = tool_fn.invoke(args)

                    # Parse tool result — tools return JSON string, not dict
                    parsed = tool_result
                    if isinstance(tool_result, str):
                        try:
                            parsed = json.loads(tool_result)
                        except json.JSONDecodeError:
                            # Error message from tool — pass through to model
                            logger.warning("Tool %s returned non-JSON (likely error): %s", tool_name, tool_result[:100])
                            messages.append(
                                ToolMessage(content=tool_result, tool_call_id=tool_call["id"])
                            )
                            continue

                    # Extract p_list and p_count from API response shape
                    if isinstance(parsed, dict):
                        p_count = parsed.get("p_count", 0)
                        p_list = parsed.get("p_list", [])
                    else:
                        p_list = parsed if isinstance(parsed, list) else []
                        p_count = len(p_list)

                    # For count queries: SP may return total in rows (COUNT(*) OVER ()) — prefer that
                    total_for_count = p_count
                    if p_list and isinstance(p_list[0], dict):
                        for key in ("total_count", "total_count_over", "full_count", "overall_count"):
                            val = p_list[0].get(key)
                            if isinstance(val, (int, float)) and val >= 0:
                                total_for_count = int(val)
                                logger.info("📊 Using total from row field '%s' = %s", key, total_for_count)
                                break

                    logger.info(
                        "📊 Tool result | %s | p_list_length=%s | p_count=%s | total_for_count=%s",
                        tool_name, len(p_list), p_count, total_for_count
                    )

                    if p_count == 0 and total_for_count == 0:
                        return "No results found for the given query.", messages

                    # Use total_for_count for message when it differs (SP pagination with total in rows)
                    display_count = total_for_count if total_for_count > len(p_list) else p_count
                    messages.append(
                        ToolMessage(
                            content=json.dumps({
                                "message": f"{display_count} records found",
                                "records_returned": len(p_list),
                                "total_count": display_count,
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
