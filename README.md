## AskAI

Simple AI assistant project with a Next.js frontend (`nanosoft-ai-frontend`) and a FastAPI backend (`nanosoft-ai-backend`).

### Tech stack

- **Frontend**: Next.js, React, Tailwind CSS  
- **Backend**: FastAPI, Uvicorn  
- **CI/CD**: GitHub Actions (tests frontend, deploys backend)

### Prerequisites

- **Node.js** 18+ and **npm**
- **Python** 3.10+ and **pip**

### Getting started

Clone the repo, then from the project root (`ask-ai/ask-ai`):

```bash
cd nanosoft-ai-frontend
npm install
npm run dev
```

Frontend will be available on `http://localhost:3000`.

In a separate terminal, start the backend:

```bash
cd nanosoft-ai-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:chatbot_app --reload --port 8001
```

### Useful scripts

From `nanosoft-ai-frontend`:

- **`npm run dev`**: Start the Next.js dev server
- **`npm run build`**: Build for production
- **`npm start`**: Run the production build
- **`npm test`**: Run frontend tests
- **`npm run lint`**: Run ESLint

# NanoSoft Ask AI
The system serves as an Intelligent Interface for Service Level Agreements workflows. It features an Agentic Reasoning Engine that autonomously queries PostgreSQL databases for assets and work orders using Google Gemini. With Audio sampling and real-time streaming, the platform ensures low-latency, Replacing AI hallucinations with factual operational insights through a secure gateway integrating text and Audio input
# Frontend
* This is a high-performance chat interface built with Next.js 14 and TypeScript, engineered for seamless AI interaction. 
* The frontend serves as a dynamic controller, utilizing the MediaRecorder API for optimized Audio capture and a ReadableStream architecture for real-time AI response.

### Core Highlights
* Architecture: Modular App Router structure with a unified logic hub in page.tsx.

* UI/UX: Responsive, dark-themed design powered by Tailwind CSS and Lucide React.

* Workflow: Seamlessly handles multi-inputs (text/Audio), transmitting data to the FastAPI backend via secure POST requests.
* Data visualization: Parses graph output and renders bar, line, pie, and horizontal charts.

* Data tables: Automatically extracts and displays structured table data in a tile-friendly view.

* UI controls: Includes theme toggle support, account/manage account panels, and an upgrade plan component.

* Performance: Features a live typing cursor and markdown formatting for an intuitive user experience.
* For detailed setup steps and architecture, check the specific folders.

# Backend
* The NanoSoft AI Backend is a facility management engine built with FastAPI and LangChain.
* It bridges the gap between raw operational data and intelligent user interaction by isolating database transactions from AI decision-making.
  
### Core Architecture
The system operates through One specialized services:

* AI Chat Engine (Port 8001): Integrates Google Gemini with LangChain to provide a data-driven assistant. It uses the ReAct pattern to dynamically trigger backend tools, preventing hallucinations by fetching real-time database records.

### Modular Structure
* `nanosoft-ai-backend/app/services/langchain_service.py` and `nanosoft-ai-backend/app/tools/`: The agentic layer where LangChain orchestrates natural language understanding, tool execution, and real-time database actions.

* `nanosoft-ai-backend/app/models/schemas.py` and `nanosoft-ai-backend/app/prompts/system_prompt.py`: Type-safe Pydantic validation and system prompt guidance that align the AI assistant with operational rules.

* `nanosoft-ai-backend/app/main.py`: The FastAPI entrypoint and routing layer that handles REST session APIs, WebSocket chat, and backend orchestration.
* For detailed setup steps and architecture, review the backend folder structure.

### Performance & Scalability
By running a single FastAPI service that separates REST session management from WebSocket-based AI chat, the project keeps AI reasoning and data workflows aligned without adding extra service complexity.
This architecture supports independent scaling at the frontend/backend boundary, reliable pytest coverage, and a smooth real-time chat experience.

# System Workflow
* Ingress: The frontend captures user intent via text or optimized audio blobs and submits it to the backend over a persistent WebSocket.

* Reasoning: The LangChain agent (powered by Gemini) parses the query, decides if tool execution is needed, and builds the next action.

* Extraction: To eliminate hallucinations, the agent invokes specialized SQL tools and backend database services to fetch live records for assets, complaints, or work orders from PostgreSQL.

* Response: The backend streams the assistant reply back over the WebSocket while persisting session history via REST endpoints.
# Summary
* NanoSoft Ask AI is a professional facility management platform bridging complex data with intuitive interaction.
* It integrates a Next.js 16 frontend with a LangChain-powered backend to automate SLA-driven workflows.
* By combining WebSocket-powered AI chat with factual PostgreSQL access, it delivers accurate, real-time operational intelligence via text and audio.
