# NANOSOFT ASK AI - Backend

The NanoSoft AI Backend is a facility management intelligence engine built with **FastAPI** and powered by **Google Gemini**. It receives natural language questions from the frontend, understands them, fetches the right data from the database, computes the answer, and returns a structured response — all in real time.

---

## What This Backend Does

- Accepts user questions in plain English (text or voice) about facility operations.
- Understands the intent behind each question and identifies which data module to query — Assets, PPM, BDM, Space Booking, Contracts, or Employees.
- Queries a **PostgreSQL** database using stored procedures to fetch real, live records — no hallucinations.
- Computes answers (counts, aggregations, comparisons) and formats the result as plain text, a table, or a chart.
- Maintains per-user session and chat history.
- Supports two separate AI pipelines: a fast **WebSocket chat** for everyday questions and an **advanced SSE pipeline** for complex analytics.

---

## Tech Stack

- **Framework:** FastAPI + Uvicorn
- **AI / LLM:** Google Gemini (`gemini-2.5-flash`, `gemini-2.5-flash-lite`)
- **Agent Orchestration:** LangGraph (multi-agent state machine)
- **Tool Binding:** LangChain
- **Database:** PostgreSQL (via stored procedures)
- **Real-time:** WebSocket (chat), Server-Sent Events / SSE (advance pipeline)

---

## Project Structure

```
nanosoft-ai-backend/
├── app/
│   ├── main.py                      # FastAPI entry point — registers all routers
│   ├── state.py                     # In-memory session store and cache state
│   ├── config/                      # Environment variable loader
│   ├── api/
│   │   ├── routes/                  # Database query functions (Assets, BDM, PPM, SB, FA, Contracts, Employees)
│   │   ├── database/                # PostgreSQL connection pool
│   │   ├── models/                  # Pydantic request/response schemas
│   │   └── advance/                 # Multi-agent Advance pipeline
│   │       ├── Understanding_Agent/ # Classifies query intent and identifies data modules
│   │       ├── analysis/            # Extracts filters and values from the query
│   │       ├── retrieval/           # Fetches records from DB with caching
│   │       ├── preprocessing/       # Cleans and normalizes fetched records
│   │       ├── execution_agent/     # Computes the final answer (counts, sums, ratios)
│   │       ├── Formatting_agent/    # Picks layout (text/table/chart) and writes explanation
│   │       ├── pipeline.py          # LangGraph pipeline wiring all agents together
│   │       └── routes/router.py     # POST /api/advance/ask-ai endpoint
│   ├── services/
│   │   ├── chat_websocket_handler.py  # Normal Ask-AI: WebSocket server + audio handling
│   │   ├── langchain_service.py       # LangChain model with 7 bound DB tools
│   │   ├── asset_analytics_service.py # External Asset History & Lifecycle API calls
│   │   ├── space_booking_service.py   # Space booking dialogue and confirmation logic
│   │   ├── audio_service.py           # Speech-to-text transcription
│   │   ├── quota_service.py           # Usage credit enforcement
│   │   ├── session_service.py         # Session retrieval and sharing logic
│   │   └── postgres_service.py        # Session and folder persistence to PostgreSQL
│   ├── tools/                         # LangChain tool definitions (ASSETS, PPM, BDM, FA, SB, CONTRACT, EMPLOYEE)
│   └── voiceAgent_endpoint.py         # Voice call endpoint
├── Cron/                              # Background data sync cron jobs
├── deploy/                            # Systemd service files for production deployment
└── tests/                             # Pytest test suites
```

---

## How the Backend Works

There are **two AI pipelines** — the right one is used based on the type of request.

### Normal Ask-AI (WebSocket)

Used for everyday conversational questions and voice queries.

- The frontend opens a persistent WebSocket connection to `/api/chat`.
- The user sends a text question or a voice message.
- If the input is voice, the backend transcribes it to text using Google Speech-to-Text, after checking the user's audio credit balance.
- The text is passed to the LangChain AI model (Gemini). The model decides:
  - If the question needs database data, it calls one of the bound tools (e.g., `ASSETS`, `BDM`, `PPM`). The tool runs a PostgreSQL stored procedure and returns real records.
  - If it's a general or conversational question, the model answers directly without a tool call.
- The response is streamed back to the client over the WebSocket in real time.
- When the session ends, the chat history is saved to PostgreSQL.

### Advance Ask-AI (SSE Stream)

Used for complex analytical queries — cross-module data, aggregations, tables, and charts.

- The frontend sends a POST request to `/api/advance/ask-ai` and receives a live SSE stream.
- The pipeline runs through six stages, with status events sent to the frontend at each step:
  1. **Understanding Agent** — reads the question and determines the intent (`db_query`, `general`, or `web_search`) and which modules are needed (e.g., BDM, PPM).
  2. **Analysis Agent** — extracts precise filter values from the question (e.g., building name, status, date range).
  3. **Retrieval Layer** — fetches records from PostgreSQL for each identified module, using in-memory and Redis caching to avoid repeated database calls.
  4. **Preprocessing Layer** — cleans and normalises the raw records.
  5. **Execution Agent** — plans and runs a calculation sequence (counts, sums, ratios, comparisons) over the fetched data.
  6. **Formatting Agent** — decides how to present the result (plain text, table, or chart) and writes a human-readable explanation.
- The final structured result is sent as the last SSE event, followed by a `[DONE]` signal.

---

## Endpoints

### 1. Normal Ask-AI — WebSocket Chat

| | |
|---|---|
| **Protocol** | WebSocket |
| **Route** | `ws://<host>/api/chat` |

**What it does:** Handles real-time conversational AI chat. Supports both text and voice input. The AI model answers questions and, when needed, fetches live data from the database.

**Input (JSON sent over WebSocket):**
```json
{
  "sessionId": "abc123",
  "userName": "john",
  "userId": 5,
  "query": "How many open BDM complaints are there?",
  "isAudio": false,
  "isSpaceBooking": false
}
```

**Returns:** Streamed AI response tokens over the WebSocket connection.

---

### 2. Advance Ask-AI — SSE Pipeline

| | |
|---|---|
| **Protocol** | HTTP POST → Server-Sent Events (SSE) |
| **Route** | `POST /api/advance/ask-ai` |

**What it does:** Handles complex analytical queries. Runs a 6-stage AI pipeline and streams live progress updates to the frontend as the answer is being computed.

**Input:**
```json
{
  "query": "Compare open vs closed BDM complaints by building this month",
  "session_id": "xyz789",
  "user_name": "john",
  "user_id": "5"
}
```

**Returns:** A stream of SSE events. The final event contains the structured result:
```json
{
  "status": "complete",
  "result": {
    "formatted_result": {
      "layout": "TABLE",
      "explanation": "Here is the breakdown of BDM complaints...",
      "final_answer": { ... }
    }
  }
}
```

---

### 3. Asset Analytics

| | |
|---|---|
| **Protocol** | HTTP POST |
| **Route** | `POST /api/asset-analytics` |

**What it does:** Fetches the full history card and lifecycle timeline for a specific asset using its barcode number. It calls the external Facility Management API concurrently for both asset history and lifecycle data.

**Input:**
```json
{ "barcode": "BC-00123", "userName": "john" }
```

**Returns:**
```json
{
  "history": { ... },
  "lifecycle": { ... }
}
```
If the barcode does not exist, it returns a clear `"error"` message.

---

### 4. Space Booking — Reservations Lookup

| | |
|---|---|
| **Protocol** | HTTP GET |
| **Route** | `GET /api/bookings/{spot_code}` |

**What it does:** Returns all active reservations for a specific room or desk spot.

**Input:** `spot_code` in the URL path.

**Returns:**
```json
{
  "status": "ok",
  "bookings": [
    { "start_time": "2026-08-17 09:00", "end_time": "2026-08-17 10:00", "booking_id": "BK-001" }
  ]
}
```

---

### 5. Session & Chat History

These REST endpoints manage the user's saved conversations and folder organisation.

| Endpoint | What it does |
|---|---|
| `POST /api/session` | Save chat history, fetch all sessions, or get one session's history |
| `POST /api/session/rename` | Rename a chat session |
| `POST /api/session/delete` | Delete a session |
| `POST /api/sessions/pin` | Pin or unpin a session |
| `POST /api/sessions/archive` | Archive or unarchive a session |
| `POST /api/sessions/share` | Make a session public or private |
| `POST /api/sessions/generate-share-code` | Generate a short code to share a session |
| `POST /api/sessions/import-by-code` | Import a shared session using a code |
| `POST /api/folder/create` | Create a folder |
| `POST /api/folder/rename` | Rename a folder |
| `POST /api/folder/delete` | Delete a folder |
| `GET /api/folders/{user_name}` | List all folders for a user |
| `GET /api/usage/{user_id}/{user_name}` | Get usage and credit stats for a user |
| `GET /api/health` | Health check — returns `{ status: "ok" }` |

---

### 6. Client Onboarding

| | |
|---|---|
| **Protocol** | HTTP POST |
| **Route** | `POST /api/client_insertion` |

**What it does:** Registers a new client organisation and performs a full initial data sync. If the client already exists, it returns their stored credentials immediately.

**Input:**
```json
{
  "userId": "5",
  "userName": "john",
  "service": "https://client-api.example.com",
  "clientName": "ClientOrg",
  "token": "jwt-token-here"
}
```

**Returns:** Client details and migration status (new or existing).

---

## Getting Started

### Prerequisites
- Python 3.10+
- PostgreSQL
- Redis (optional, for advanced caching)
- Google Gemini API Key

### Installation

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Create `app/.env`:

```env
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_AI_MODEL=gemini-2.5-flash-lite

PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=nanosoft_ask
PG_USER=postgres
PG_PASSWORD=your_password

MAX_HISTORY=2
```

### Run the Server

```bash
uvicorn app.main:chatbot_app --reload --port 8001
```

API documentation is available at **http://localhost:8000/docs**
