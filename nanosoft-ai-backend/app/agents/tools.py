import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from langchain.tools import tool, StructuredTool
from langchain_core.tools import BaseTool
from app.agents.retrieval_agent import retrieval_agent

# Import original tool modules
from app.tools import facility_tools, space_booking_tool

def run_async_sync(coro):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()

def wrap_tool_with_retrieval_agent(original_tool, source: str):
    """
    Wraps a LangChain tool so that its invocation goes through retrieval_agent.execute_step.
    """
    def wrapped_func(**kwargs):
        user_name = kwargs.get("user_name", "system")
        session_id = kwargs.get("session_id", "system_session")
        
        step = {
            "source": source,
            "target": original_tool.name.lower(),
            "params": kwargs
        }
        
        coro = retrieval_agent.execute_step(step, user_name, session_id)
        result = run_async_sync(coro)
        
        if isinstance(result, dict) and result.get("success"):
            data = result.get("data")
            if isinstance(data, (dict, list)):
                return json.dumps(data)
            return str(data)
        else:
            error_msg = result.get("error") if isinstance(result, dict) else str(result)
            return f"Error executing tool {original_tool.name}: {error_msg}"
            
    return StructuredTool.from_function(
        func=wrapped_func,
        name=original_tool.name,
        description=original_tool.description,
        args_schema=original_tool.args_schema
    )

# Dynamically wrap all database tools from facility_tools and export them
for attr_name in dir(facility_tools):
    attr = getattr(facility_tools, attr_name)
    if isinstance(attr, BaseTool) and attr_name.isupper():
        globals()[attr_name] = wrap_tool_with_retrieval_agent(attr, "db")

# Dynamically wrap all space booking tools from space_booking_tool and export them
for attr_name in dir(space_booking_tool):
    attr = getattr(space_booking_tool, attr_name)
    if isinstance(attr, BaseTool) and attr_name.isupper():
        globals()[attr_name] = wrap_tool_with_retrieval_agent(attr, "api")

# Define document search and web search tools
@tool
def WEB_SEARCH(query: str) -> str:
    """
    Use this tool to search the internet (web search) for general information, troubleshooting guides, specifications, manual lookups, or recent events.
    Input must be a simple query string.
    """
    coro = retrieval_agent.execute_step(
        {"source": "web_search", "target": query, "params": {}},
        "system", "system_session"
    )
    result = run_async_sync(coro)
    if isinstance(result, dict) and result.get("success"):
        data = result.get("data")
        if isinstance(data, (dict, list)):
            return json.dumps(data)
        return str(data)
    return str(result.get("error", result))

@tool
def DOC_SEARCH(query: str) -> str:
    """
    Use this tool to search local documents, manuals, checklists, policies, or guide files stored in the facility system.
    Input must be a simple keyword or search query.
    """
    coro = retrieval_agent.execute_step(
        {"source": "document", "target": query, "params": {}},
        "system", "system_session"
    )
    result = run_async_sync(coro)
    if isinstance(result, dict) and result.get("success"):
        data = result.get("data")
        if isinstance(data, (dict, list)):
            return json.dumps(data)
        return str(data)
    return str(result.get("error", result))
