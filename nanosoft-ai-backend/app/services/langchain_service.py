"""
LangChain Service — AI model with tool support
"""
import logging
from typing import Any

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
                model=settings.GOOGLE_AI_MODEL,
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

    async def process_query(self, messages: list, user_name: str = None, session_id: str = None) -> tuple[str, list]:
        try:
            # user_name is always from the frontend request; use it for all tool calls
            if not user_name:
                raise ValueError("user_name is required (from frontend request)")
            logger.info(f"💬 Processing query for user_name: {user_name}")
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
                    args.pop("user_id", None)
                    args["user_name"] = user_name

                    # Override limit for count queries — LLM often passes limit=1 incorrectly
                    # Also: for LIST queries, ALWAYS clear limit to get all records (so large_dataset detection works)
                    user_query = ""
                    for m in reversed(messages):
                        if isinstance(m, HumanMessage):
                            user_query = (m.content or "") if isinstance(m.content, str) else ""
                            break
                    count_patterns = ("how many", "total", "number of", "count of", "count ", "how many ")
                    list_patterns = ("list", "show me", "get ", "fetch ", "display", "all assets", "all complaints", "all bdm", "all ppm")
                    
                    is_count_query_check = any(p in user_query.lower() for p in count_patterns)
                    is_list_query_check = any(p in user_query.lower() for p in list_patterns)
                    
                    # For list queries: ALWAYS clear limit to enable large_dataset detection
                    # This ensures we get ALL records from DB, not just first 100
                    if is_list_query_check:
                        old_limit = args.get("limit")
                        args["limit"] = None
                        logger.info("📋 List query detected — %s limit=%s to enable large_dataset detection (>100 records)", 
                                  "clearing" if old_limit else "ensuring no", old_limit)
                    elif is_count_query_check and args.get("limit") is not None:
                        logger.info("📊 Count query detected — clearing limit=%s", args.get("limit"))
                        args["limit"] = None
                    
                    tool_result = tool_fn.invoke(dict(args))
                    
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
                        
                        if "p_list" in parsed:
                            p_count = parsed.get("p_count", 0)
                            p_list = parsed.get("p_list", [])
                        else:
                        
                            p_list = list(parsed.values())
                            p_count = len(p_list)
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
                        logger.info("📊 No records found for tool %s", tool_name)
                        return "No results found for the given query.", messages

                    # Use total_for_count for message when it differs (SP pagination with total in rows)
                    display_count = total_for_count if total_for_count > len(p_list) else p_count
                    
                    #checking model whether it is a count or list needs to return. 
                    intent_msg = self.model.invoke([
                        HumanMessage(content=f"""
                        Classify this user query into one of two intents:
                        - "count" → user wants ONLY a number/total (e.g. "how many assets exist?, how many complaints exits")
                        - "list" → user wants records/data shown (e.g. "how many can you show me?", "list assets")
                        
                        Query: "{user_query}"
                        
                        Reply with ONLY one word: count or list
                        """)
                    ])
                    is_count_query = intent_msg.content.strip().lower() == "count"
                    if is_count_query:
                        logger.info("🔢 Intent=COUNT — sending count only to model | query='%s'", user_query)
                    else:
                        logger.info("📋 Intent=LIST — sending full records to model | query='%s'", user_query)
                    
                    MAX_DISPLAY = 100
                    p_list_for_model = p_list if len(p_list) <= MAX_DISPLAY else p_list[:MAX_DISPLAY]
                    is_large_result = len(p_list) > MAX_DISPLAY

                    # ⭐ LARGE DATASET (>100): Send raw data to frontend + get context only from model
                    if is_large_result:
                        logger.info("📌 Large dataset (%d records) → Sending raw data to frontend + context from model only", len(p_list))
                        
                        messages.append(
                            ToolMessage(
                                content=json.dumps({
                                    "message": f"{display_count} records found (dataset too large for full processing)",
                                    "records_returned": len(p_list),
                                    "total_count": display_count,
                                    "is_large_result": True,
                                    "records": []  # No records to model
                                }),
                                tool_call_id=tool_call["id"]
                            )
                        )
                        
                        # Get context/summary from model only
                        messages.append(HumanMessage(content="Provide a brief context/summary of the above query result. Do NOT list individual records. Keep it concise."))
                        context_ai_msg = self.model.invoke(messages)
                        context_summary = context_ai_msg.content
                        
                        logger.info("✅ Context summary generated for large dataset")
                        logger.info("🚀 [IMPORTANT] Returning large_dataset JSON directly to frontend - NO STEP 3 PROCESSING")
                        # Return immediately with large_dataset JSON format
                        large_dataset_response = json.dumps({
                            "type": "large_dataset",
                            "total_count": display_count,
                            "records_count": len(p_list),
                            "context_summary": context_summary,
                            "records": p_list  # Raw data to frontend
                        })
                        logger.info("✅ Large dataset JSON prepared: %d records", len(p_list))
                        return large_dataset_response, messages

                    # ✅ SMALL DATASET (≤100): Process normally through model
                    logger.info("📋 Small dataset (%d records) → Processing through AI model", len(p_list))
                    messages.append(
                        ToolMessage(
                            content=json.dumps({
                                "message": f"{display_count} records found",
                                "records_returned": len(p_list),
                                "total_count": display_count,
                                "is_large_result": is_large_result,
                                "displayed_count": len(p_list_for_model),
                                "records": [] if is_count_query else p_list_for_model   #If it's a count query → records: [] (empty list, no data)  or if If it's a list/show query → records: p_list full  records what it got
                            }),
                            tool_call_id=tool_call["id"]
                        )
                    )

                # STEP 3 — Call model again to generate final answer
                messages.append(HumanMessage(content="Use the above tool results and give the final answer. give some context when generating the table"))
                final_ai_msg = self.model.invoke(messages)
                final_content = final_ai_msg.content
                 # ✅ FINAL SAFETY NET (NO EMPTY STRING EVER)
                if not final_content or str(final_content).strip() == "":
                    final_content = "No results found for the given query."
                    logger.info("final_ai_content is empty")

                logger.info("✅ Final response generated after tool execution")
                return final_content, messages

    

            else:

                # Model skipped tool — check if this is a data query that REQUIRES a tool
                # if the model skipped the tool, we need to inject a synthetic tool call and result so the model formats from live data
###
                user_query = ""
                for m in reversed(messages):
                    if isinstance(m, HumanMessage):
                        user_query = (m.content or "") if isinstance(m.content, str) else ""
                        break
                q = user_query.lower()
                data_patterns = ("how many", "list", "count", "total", "number of", "show me", "get ", "fetch ")
                needs_bdm = any(w in q for w in ("complaint", "bdm", "breakdown"))
                needs_assets = any(w in q for w in ("asset", "equipment"))
                needs_ppm = any(w in q for w in ("ppm", "preventive", "planned", "scheduled"))

                if any(p in q for p in data_patterns) and (needs_bdm or needs_assets or needs_ppm):
                    tool_name = "BDM" if needs_bdm else ("ASSETS" if needs_assets else "PPM")
                    logger.warning("⚠️ Model skipped tool for data query — forcing %s", tool_name)
                    tool_fn = self.tool_map[tool_name]
                    args = {"user_name": user_name, "limit": None}
                    logger.info("🔍 Calling forced tool directly | tool=%s | user_name=%s", tool_name, user_name)
                    tool_result = tool_fn.invoke(dict(args))
                    
                    
                    try:
                        parsed = json.loads(tool_result) if isinstance(tool_result, str) else tool_result
                    except json.JSONDecodeError:
                        parsed = {}
                        
                    #handle indexed dict from cache same as normal path
                    if isinstance(parsed, dict) and "p_list" in parsed:
                        p_list = parsed.get("p_list", [])
                        p_count = parsed.get("p_count", len(p_list))
                    elif isinstance(parsed, dict):
                        p_list = list(parsed.values())
                        p_count = len(p_list)
                    else:
                        p_list = parsed if isinstance(parsed, list) else []
                        p_count = len(p_list)
                        
                    total_for_count = p_count
                    
                    if p_list and isinstance(p_list[0], dict):
                        for key in ("total_count", "total_count_over", "full_count", "overall_count"):
                            val = p_list[0].get(key)
                            if isinstance(val, (int, float)) and val >= 0:
                                total_for_count = int(val)
                                break
                    display_count = total_for_count if total_for_count > len(p_list) else p_count
                    if p_count == 0 and total_for_count == 0:
                        return "No results found for the given query.", messages
                    

                    # Inject synthetic tool call + result so model formats from live data
                    fake_tool_id = "forced-" + tool_name.lower() + "-1"
                    synthetic_ai = AIMessage(content="", tool_calls=[{"name": tool_name, "id": fake_tool_id, "args": {"user_name": user_name}}])
                    messages.append(synthetic_ai)
                    
                    #checking model whether it is a count or list needs to return. 
                    intent_msg = self.model.invoke([
                        HumanMessage(content=f"""
                        Classify this user query into one of two intents:
                        - "count" → user wants ONLY a number/total (e.g. "how many assets exist?, how many complaints exits")
                        - "list" → user wants records/data shown (e.g. "how many can you show me?", "list assets")
                        
                        Query: "{user_query}"
                        
                        Reply with ONLY one word: count or list
                        """)
                    ])
                    is_count_query = intent_msg.content.strip().lower() == "count"
                    
                    if is_count_query:
                        logger.info("🔢 Intent=COUNT — sending count only to model | query='%s'", user_query)
                    else:
                        logger.info("📋 Intent=LIST — sending full records to model | query='%s'", user_query)
                    

                    MAX_DISPLAY = 100
                    p_list_for_model = p_list if len(p_list) <= MAX_DISPLAY else p_list[:MAX_DISPLAY]
                    is_large_result = len(p_list) > MAX_DISPLAY

                    # ⭐ LARGE DATASET (>100): Send raw data to frontend + get context only from model
                    if is_large_result:
                        logger.info("📌 Large dataset (%d records) → Sending raw data to frontend + context from model only", len(p_list))
                        
                        messages.append(
                            ToolMessage(
                                content=json.dumps({
                                    "message": f"{display_count} records found (dataset too large for full processing)",
                                    "records_returned": len(p_list),
                                    "total_count": display_count,
                                    "is_large_result": True,
                                    "records": []  # No records to model
                                }),
                                tool_call_id=fake_tool_id
                            )
                        )
                        
                        # Get context/summary from model only
                        messages.append(HumanMessage(content="Provide a brief context/summary of the above query result. Do NOT list individual records. Keep it concise."))
                        context_ai_msg = self.model.invoke(messages)
                        context_summary = context_ai_msg.content
                        
                        logger.info("✅ Context summary generated for large dataset")
                        return json.dumps({
                            "type": "large_dataset",
                            "total_count": display_count,
                            "records_count": len(p_list),
                            "context_summary": context_summary,
                            "records": p_list  # Raw data to frontend
                        }), messages

                    # ✅ SMALL DATASET (≤100): Process normally through model
                    logger.info("📋 Small dataset (%d records) → Processing through AI model [FORCED]", len(p_list))
                    messages.append(
                        ToolMessage(
                            content=json.dumps({
                                "message": f"{display_count} records found",
                                "records_returned": len(p_list),
                                "total_count": display_count,
                                "is_large_result": is_large_result,
                                "displayed_count": len(p_list_for_model),
                                "records": [] if is_count_query else p_list_for_model ##If it's a count query → records: [] (empty list, no data)  or if If it's a list/show query → records: p_list full  records what it got
                                
                            }),
                            tool_call_id=fake_tool_id
                        )
                    )
                    
                    final_ai_msg = self.model.invoke(messages)
                    content = final_ai_msg.content or "No results found for the given query."
                    logger.info("✅ Response after forced tool call")
                    return content, messages
####

                content = ai_msg.content
                if not content or str(content).strip() == "":
                    content = "No results found for the given query."
                logger.info("✅ No tool call — direct response")
                return content, messages

        except Exception as e:
            logger.error(f"❌ Query processing error: {e}", exc_info=True)
            raise

langchain_service = LangChainService()