from langchain_core.tools import tool

@tool
def render_table(format_reason: str, explanation: str) -> dict:
    """Use this tool to render the answer as a highly structured, multi-column TABLE.
    CRITICAL RULE: If the execution trace returns an array of dictionaries or objects, 
    you MUST trigger render_table. This overrides all other layouts (even if the data is ranked or limited).
    Trigger this when the execution trace shows:
    - Fetching multiple database records (e.g., `list_records`)
    - Returning arrays of dictionaries or objects (e.g., {"key": "value"})
    - Multi-column comparative metrics
    """
    return {"layout": "TABLE", "response_type": "table-response", "format_reason": format_reason, "explanation": explanation}

@tool
def render_bullet_list(format_reason: str, explanation: str) -> dict:
    """Use this tool to render the answer as a BULLET_LIST of distinct points.
    Trigger this when the execution trace shows:
    - Fetching a flat array of strings or categories (e.g., `get_unique_values`)
    - Distinct, unordered 1-dimensional data points
    """
    return {"layout": "BULLET_LIST", "response_type": "bullet-response", "format_reason": format_reason, "explanation": explanation}

@tool
def render_numbered_list(format_reason: str, explanation: str) -> dict:
    """Use this tool to render the answer as a NUMBERED_LIST.
    CRITICAL RULE: DO NOT use this if the data is an array of dictionaries or objects. Use render_table instead.
    Trigger this when the execution trace shows:
    - Ranked data (e.g., top 5, highest to lowest) of FLAT strings, NOT objects.
    - Sequential workflows or steps
    """
    return {"layout": "NUMBERED_LIST", "response_type": "numbered-list-response", "format_reason": format_reason, "explanation": explanation}

@tool
def render_graph(format_reason: str, explanation: str) -> dict:
    """Use this tool to render the answer as a GRAPH chart.
    Trigger this when the execution trace explicitly shows:
    - Graphing, charting, or visualization tools being called
    """
    return {"layout": "GRAPH", "response_type": "graph-response", "format_reason": format_reason, "explanation": explanation}

@tool
def render_plain_text(format_reason: str, explanation: str) -> dict:
    """Use this tool as the DEFAULT layout for simple text or single numbers.
    Trigger this when the execution trace shows:
    - Counting a metric (e.g., `count_records`)
    - Simple calculations or standard conversation
    """
    return {"layout": "PLAIN_TEXT", "response_type": "plain-response", "format_reason": format_reason, "explanation": explanation}

FORMATTING_TOOLS = [
    render_table,
    render_bullet_list,
    render_numbered_list,
    render_graph,
    render_plain_text
]
