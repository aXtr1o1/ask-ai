from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from tools import ASSETS, COMPLAINTS, WORK_ORDERS
from system_prompt import system_prompt

import os
from dotenv import load_dotenv

import asyncio


load_dotenv()
api_key = os.getenv("api_key")

# =====================================================
# ✅ FastAPI App
# =====================================================
app = FastAPI()

# =====================================================
# ✅ Allow Frontend Requests (CORS Fix)
# =====================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# ✅ Bind Tools to Gemini Model
# =====================================================
model_with_tools = ChatGoogleGenerativeAI(
    model="gemini-flash-latest",
    google_api_key=api_key
).bind_tools([ASSETS, COMPLAINTS, WORK_ORDERS])

# =====================================================
# ✅ Tool Map
# =====================================================
tool_map = {
    "ASSETS": ASSETS,
    "COMPLAINTS": COMPLAINTS,
    "WORK_ORDERS": WORK_ORDERS,
}

# =====================================================
# ✅ Chat Memory Store (Simple Global)
# =====================================================
chat_history = []


# =====================================================
# ✅ Request Schema
# =====================================================
class ChatRequest(BaseModel):
    query: str


# =====================================================
# ✅ Chat Endpoint
# =====================================================
def extract_chunk_text(chunk):
    content = chunk.content

    # Case 1: Empty chunk
    if not content:
        return ""

    # Case 2: Gemini list format
    if isinstance(content, list):

        # Sometimes list is empty
        if len(content) == 0:
            return ""

        return content[0].get("text", "")

    # Case 3: Normal string
    if isinstance(content, str):
        return content

    return str(content)

@app.post("/chat")

async def chat_endpoint(request: ChatRequest):

    user_query = request.query

    # 1. Build Messages with Memory
    messages = [system_prompt]

    for item in chat_history[-10:]:
        messages.append(HumanMessage(content=item["user"]))
        messages.append(AIMessage(content=item["assistant"]))

    messages.append(HumanMessage(content=user_query))

    # 2. Tool Detection
    ai_msg = model_with_tools.invoke(messages)

    # 3. Tool Execution
    if ai_msg.tool_calls:

        messages.append(ai_msg)

        for tool_call in ai_msg.tool_calls:

            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            tool_fn = tool_map[tool_name]
            tool_result = tool_fn.invoke(tool_args)

            messages.append(
                ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call["id"]
                )
            )

    # 4. STREAM IN TERMINAL (Correct)
    print("\n🤖 Assistant: ", end="", flush=True)

    final_response_text = ""

    async for chunk in model_with_tools.astream(messages):

        text = extract_chunk_text(chunk)

        if not text:
            continue

        print(text, end="", flush=True)
        final_response_text += text

    print("\n")

    # 5. Save History
    chat_history.append({
        "user": user_query,
        "assistant": final_response_text
    })

    # 6. Send Full Output to HTML
    return {"response": final_response_text}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("model:app", host="127.0.0.1", port=8001, reload=True)
