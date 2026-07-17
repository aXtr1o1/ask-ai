from langchain_core.tools import tool

@tool
def render_table(format_reason: str, header: str = "", explanation: str = "") -> dict:
    """Use this tool to render the answer as a highly structured, multi-column TABLE.
    Trigger this when the text contains:
    - Markdown tables (e.g., `| Column A | Column B |`)
    - Financial ledgers or tabular datasets
    - Multi-column comparative metrics
    """
    return {"layout": "TABLE", "response_type": "table-response", "format_reason": format_reason, "header": header, "explanation": explanation}

@tool
def render_bullet_list(format_reason: str, header: str = "", explanation: str = "") -> dict:
    """Use this tool to render the answer as a BULLET_LIST of distinct points or unranked items.
    Trigger this when the text contains:
    - Distinct, unordered data points
    - Feature lists or standalone attributes
    - Markdown bullets (`-`, `*`, `+`)
    """
    return {"layout": "BULLET_LIST", "response_type": "bullet-response", "format_reason": format_reason, "header": header, "explanation": explanation}

@tool
def render_numbered_list(format_reason: str, header: str = "", explanation: str = "") -> dict:
    """Use this tool to render the answer as a NUMBERED_LIST of sequential steps or ranked items.
    Trigger this when the text contains:
    - Chronological steps or workflows
    - Ordered instructions or standard operating procedures
    - Ranked items (e.g., top 5 highest costs)
    """
    return {"layout": "NUMBERED_LIST", "response_type": "numbered-list-response", "format_reason": format_reason, "header": header, "explanation": explanation}


@tool
def render_graph(format_reason: str, header: str = "", explanation: str = "") -> dict:
    """Use this tool to render the answer as a Mermaid GRAPH chart.
    Trigger this when the text contains Mermaid code for:
    - Flowcharts or architectural diagrams
    - Pie charts for data distribution
    - Bar charts for comparative metrics
    - Sequence or state diagrams
    """
    return {"layout": "GRAPH", "response_type": "graph-response", "format_reason": format_reason, "header": header, "explanation": explanation}

@tool
def render_plain_text(format_reason: str, rewritten_text: str = "", header: str = "", explanation: str = "") -> dict:
    """Use this tool as the DEFAULT layout for standard analytical text blocks containing paragraphs, formulas, or short metrics.
    Trigger this when the text contains:
    - Standard text blocks like 'Approach:', 'Formula:', 'Business Insight:'
    - Single numbers, short metrics, or conversational responses
    - Do NOT use numbered_list just because a paragraph contains a number.
    
    IMPORTANT: You must provide a clean, user-friendly conversational response in `rewritten_text`. Remove internal robotic headings like 'Approach' or 'Formula'.
    """
    return {"layout": "PLAIN_TEXT", "response_type": "plain-response", "format_reason": format_reason, "header": header, "explanation": explanation, "rewritten_text": rewritten_text}

FORMATTING_TOOLS = [
    render_table,
    render_bullet_list,
    render_numbered_list,
    render_graph,
    render_plain_text
]
