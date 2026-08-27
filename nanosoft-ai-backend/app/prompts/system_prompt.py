"""
Prompts for Normal ASK-AI.

Normal ASK-AI is scope-limited to Level 1 (Information Retrieval) queries.
Two model-driven steps live here:

  get_level_check_prompt()  -> classifies a query into one of the 5 FM query
                                levels so Normal can redirect anything beyond
                                Level 1 to Advanced ASK-AI.
  get_payload_prompt()      -> given the real metadata/enum values for one
                                selected module, asks the model to produce the
                                filter values, aggregate decision, and display
                                intent for that module.

get_system_prompt() is kept for scoped_memory_service, which still opens the
model conversation with an identity/tone message.
"""
from datetime import date

from langchain_core.messages import SystemMessage


def get_system_prompt(user_name: str) -> SystemMessage:
    """Identity/tone message shown at the start of the conversation."""
    content = IDENTITY_CONTENT.format(user_name=user_name)
    return SystemMessage(content=content)


IDENTITY_CONTENT = """
Identity: Your name is ASK-AI. Use that name when it fits naturally (greetings, sign-offs, or when the user asks who you are).

Tone: Be warm, approachable, and conversational-like a helpful teammate-not stiff or robotic.

Who-you-are questions: If the user asks what you are, who you are, your name, or which company or model built you, say you are NanoAI, the in-app assistant for facility operations, assets, and maintenance. Do not call yourself "a large language model trained by Google" or similar vendor/model boilerplate unless the user explicitly asks for technical details about the underlying AI stack.

Your source is only about Asset Management, Preventive Maintenance (PPM), Breakdown Maintenance (BDM), Facility Audit (FA), Schedule Based (SB) work orders, Contracts, and Employees.
"""


# ─────────────────────────────────────────────────────────────────────────────
# CRITICAL DATE RULES — single source of truth, injected into the payload
# prompt below. Every relative-date query must resolve through these exact
# keywords; the model must never invent or hardcode a calendar date itself.
# ─────────────────────────────────────────────────────────────────────────────
CRITICAL_DATE_RULES = """
CRITICAL DATE RULES:
- Today's actual date is {today}. Use this for all relative date references.
- User says "today" -> date_from="today" and date_to="today"
- User says "yesterday" -> date_from="yesterday" and date_to="yesterday"
- User says "this week" -> date_from="this week" and date_to="today"
- User says "last week" -> date_from="last week" and date_to="last week"
- User says "this month" -> date_from="this month" and date_to="today"
- User says "last month" -> date_from="last month" and date_to="last month"
- User says "this year" -> date_from="this year" and date_to="today"
- User says "last year" -> date_from="last year" and date_to="last year"
- User says NOTHING about a date -> do NOT include date_from or date_to in filters at all.
- NEVER invent, guess, or hardcode a specific calendar date yourself. Only ever pass one of the
  exact relative keywords above, an explicit "X days/weeks/months/years ago" phrase the user typed,
  or an explicit YYYY-MM-DD date the user typed.
"""


# ─────────────────────────────────────────────────────────────────────────────
# LEVEL CHECK — Normal ASK-AI only answers Level 1 queries. Everything else
# must be redirected to Advanced ASK-AI, which has the analysis/execution
# pipeline needed to actually answer those levels.
# ─────────────────────────────────────────────────────────────────────────────
_LEVEL_DEFINITIONS = """
LEVEL 1 - Information Retrieval:
  Direct lookups, filtered lists, single counts, or a grouped breakdown on ONE topic.
  Examples: "how many PPM work orders are open", "list assets in Building 1 that are offline",
  "breakdown of BDM complaints by priority", "show me FA complaints raised this week".

LEVEL 2 - Business Analysis:
  Comparisons, correlations, or trends across multiple dimensions or time periods that require
  interpreting the data, not just counting or listing it.
  Examples: "compare PPM completion rates between Q1 and Q2", "which division has the worst SLA compliance".

LEVEL 3 - Operational Intelligence:
  Real-time operational insight - SLA breach detection, bottleneck identification, live status
  correlation across modules.
  Examples: "which work orders are about to breach SLA", "where are our maintenance bottlenecks right now".

LEVEL 4 - Prescriptive Intelligence:
  Recommendations - what action should be taken.
  Examples: "what should we do to reduce breakdown complaints", "how can we improve PPM compliance".

LEVEL 5 - Predictive Intelligence:
  Forecasting - what will happen.
  Examples: "how many complaints will we get next month", "predict which assets will fail next".
"""


def get_level_check_prompt(query_summary: str) -> str:
    """Classify a query into one of the 5 FM query levels."""
    return f"""{_LEVEL_DEFINITIONS}
Classify the query below into exactly ONE level (1-5) using the definitions above.
If the query genuinely mixes traits, pick the HIGHEST level it touches - Normal ASK-AI can
only serve pure Level 1 queries, so when in doubt about whether analysis/reasoning is required,
prefer the higher level.

Query: "{query_summary}"

Reply with ONLY strict JSON, no markdown fences, no explanation:
{{"level": <1-5>}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# PAYLOAD GENERATION — given real metadata + enum values for ONE selected
# module, decide the filter values, the aggregate/group-by decision, and
# whether the user wants a count, a list of records, or a graph.
# ─────────────────────────────────────────────────────────────────────────────
def get_payload_prompt(query_summary: str, module: str, metadata_block: str, enum_block: str) -> str:
    today = date.today().strftime("%A, %B %d, %Y")
    date_rules = CRITICAL_DATE_RULES.format(today=today)

    return f"""You are building a database query payload for the "{module}" module of a facility
management system, based on what the user asked.

USER QUERY: "{query_summary}"

FIELDS AVAILABLE IN THIS MODULE (exact DB column name -> meaning):
{metadata_block}

ALLOWED VALUES FOR ENUM FIELDS (a filter on one of these fields MUST use one of these exact values):
{enum_block}

{date_rules}

TASK: Return strict JSON, no markdown fences, no explanation, in exactly this shape:
{{
  "filters": {{"<ExactDbColumnName>": "<value>"}},
  "limit": <integer or null>,
  "is_aggregate": true or false,
  "group_by_columns": ["<ExactDbColumnName>"] or null,
  "aggregate_function": "COUNT" or "SUM" or "AVG" or null,
  "response_type": "list" or "count" or "graph"
}}

RULES:
- "filters" keys MUST be exact DB column names copied from FIELDS AVAILABLE above. Never invent a
  field name. Use "date_from" / "date_to" as literal keys (not a column from the list above) for
  any date-range filter, following the CRITICAL DATE RULES.
- Only include a filter the user actually implied. Do not guess values.
- "limit": set to an integer ONLY when the user explicitly asked for a specific number of results
  (e.g. "show 5", "top 10"). Otherwise null.
- "is_aggregate": true only when the user wants a grouped breakdown or distribution across a
  category (e.g. "how many per division", "breakdown by status", "how many X are there" where X is
  a field name). False for a plain filtered list or a single total count.
- "group_by_columns" / "aggregate_function": only set when is_aggregate is true. aggregate_function
  is "COUNT" unless the user asks for a sum or average of a numeric field.
- "response_type":
    "count" -> the user wants only a single total number, nothing else.
    "graph" -> the user explicitly asked for a chart, graph, or visual breakdown.
    "list"  -> the user wants to see the actual records or a grouped table.
"""
