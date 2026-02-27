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
uvicorn main:app --reload
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

* Performance: Features a live typing cursor and markdown formatting for an intuitive user experience.
* For detailed setup steps and architecture, check the specific folders.

# Backend
* The NanoSoft AI Backend is a facility management engine built with FastAPI and LangChain.
* It bridges the gap between raw operational data and intelligent user interaction by isolating database transactions from AI decision-making.
  
### Dual-Core Architecture
The system operates through two specialized services:

* Core API (Port 8000): Manages high-integrity PostgreSQL workflows for Assets, Complaints, and Work Orders, ensuring SLA compliance through structured stored procedures.

* AI Chat Engine (Port 8001): Integrates Google Gemini with LangChain to provide a data-driven assistant. It uses the ReAct pattern to dynamically trigger backend tools, preventing hallucinations by fetching real-time database records.

### Modular Structure
* model.py & tools.py: The "Agentic" layer where LangChain orchestrates natural language processing and tool execution.

* schemas.py & system_prompt.py: Ensures type-safe Pydantic validation and aligns AI behavior with operational rules.

* main.py: The robust RESTful foundation handling the primary facility management.
* For detailed setup steps and architecture, check the specific folders.

### Performance & Scalability
By decoupling the AI reasoning from the core asset management, the system ensures that high-computational LLM tasks do not interfere with critical database transactions. 
This professional setup allows for independent scaling, reliable testing via pytest, and seamless frontend integration.
# System Workflow
The platform operates through a high-speed, four-stage pipeline designed for data integrity and minimal latency:

* Ingress: The Frontend captures user intent via text or optimized Audio blobs, transmitting them to the backend central brain.

* Reasoning: The LangChain Agent (powered by Gemini) parses the query using a ReAct loop to determine if database access is required.

* Extraction: To eliminate hallucinations, the agent invokes specialized SQL Tools to fetch live records for assets, complaints, or work orders directly from PostgreSQL.
# Summary
* NanoSoft Ask AI is a professional facility management platform bridging complex data with intuitive interaction. 
* It integrates a Next.js 14 frontend with a LangChain-powered Backend to automate SLA-driven workflows. 
* By replacing hallucinations with factual PostgreSQL insights via audio and text, it delivers accurate, real-time operational intelligence.
