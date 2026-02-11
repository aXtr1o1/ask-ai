# Nanosoft AI Backend 

This directory contains the backend code for the Nanosoft AI project (backend branch).

The backend handles SLA-driven logic, API processing, and AI integration, ensuring that responses are generated based on real backend data instead of assumptions.


## 📁 Folder Structure

```
ask-ai/
└── nanosoft-ai-backend/
    ├── app/
    │   ├── api/
    │   ├── __init__.py
    │   ├── config.py
    │   ├── main.py          # Core Backend API (Port 8000)
    │   ├── model.py         # AI Chat API (Port 8001)
    │   ├── schemas.py
    │   ├── system_prompt.py
    │   └── tools.py
    │
    ├── tests/
    ├── requirements.txt
    └── README.md
```

---

## 🧩 app/main.py – Core Backend API

### Purpose

Acts as the **primary backend service** responsible for database workflows and SLA tracking.

### Database & Workflow

This backend uses **PostgreSQL** and is structured around three core tables:

- **Assets**  
  Stores complete equipment details including identification, location, status, priority, and operational configuration.

- **Complaints**  
  Stores records of reported equipment issues or breakdowns raised against an asset.

- **Work Orders**  
  Stores planned or scheduled maintenance tasks generated for assets based on defined rules or schedules.


### Flow

1. User actions are validated at the API layer
2. Data is processed using **PostgreSQL stored procedures**
3. Backend exposes clean REST APIs (e.g., `/assets`, `/complaint`, `/work-orders`)
4. Frontend consumes these APIs using a base URL

**One-line summary:**  
Implements the FastAPI backend for managing assets, complaints, work orders, and SLA-compliant facility workflows.

---

## 🤖 app/model.py – AI Chat API (FastAPI + LangChain + Gemini)

### Purpose

Implements the **AI Assistant**.

### Responsibilities

- Connects frontend chat UI with Gemini LLM via LangChain
- Understands natural language queries
- Dynamically decides when to invoke backend tools
- Fetches real-time data for Assets, Complaints, and Work Orders
- Maintains chat memory during a session

**One-line summary:**  
FastAPI-based AI chat engine integrating Gemini with LangChain tools to deliver accurate, data-driven responses.

---

## 📐 app/schemas.py – Tool Input Schemas

### Purpose

Defines **Pydantic schemas** used by LangChain for tool invocation.

- Converts natural language inputs into structured data
- Ensures validation and consistency
- Prevents malformed inputs from reaching backend services

**One-line summary:**  
Defines validated Pydantic schemas that allow LangChain to safely invoke backend tools.

---

## 🧠 app/system_prompt.py – System Prompt

### Purpose

Defines the **system-level behavior** of the AI assistant.

- Controls response style
- Determines when tools should be invoked
- Aligns AI decisions with operational and SLA rules

**One-line summary:**  
Controls AI behavior and tool-usage logic based on user intent.

---

## 🔧 app/tools.py – LangChain Tools

### Purpose

Defines LangChain tools that act as a bridge between the LLM and backend APIs.

- Fetches real backend data
- Prevents hallucinations
- Enables reliable, structured responses

**One-line summary:**  
LangChain tools connecting the AI assistant to Assets, Complaints, and Work Orders APIs.

---

## 📦 files / tests

- `tests/` contains backend test cases

---

## 📜 requirements.txt

Main dependencies include:

- FastAPI, Uvicorn
- Pydantic v2
- Supabase / PostgreSQL support
- LangChain + Gemini
- Pytest

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## ▶️ Running the Backend (Backend Branch)

### Step 1: Navigate to App Folder

```bash
cd ask-ai/nanosoft-ai-backend/app
```

### Step 2: Install Dependencies

```bash
pip install -r ../requirements.txt
```

### Step 3: Run Services

#### Core Backend API (Port 8000)

```bash
uvicorn main:app --reload --port 8000
```

#### AI Chat API (Port 8001)

```bash
uvicorn model:app --reload --port 8001
```

---

## 📘 API Documentation

- Core Backend API: http://localhost:8000/docs
- AI Chat API: http://localhost:8001/docs

---

## ✅ Summary

This backend branch delivers an **SLA-compliant facility management platform** powered by FastAPI, PostgreSQL, and an AI assistant. The architecture cleanly separates business workflows from AI orchestration, ensuring scalability, reliability, and maintainability.

