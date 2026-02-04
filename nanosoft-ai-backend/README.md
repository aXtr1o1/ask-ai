## Nanosoft AI Backend

This folder contains the backend service for the Nanosoft AI project. It is structured as a typical FastAPI-style application, with clear separation between configuration, API routing, business logic, data models, and utilities.

The root backend layout:

- **`app/`**: Main application code (FastAPI app, routes, schemas, services, utilities).
- **`files/`**: Storage area for uploaded files, exports, or other filesystem artifacts used by the backend.
- **`requirements.txt`**: Python dependencies for running the backend.
- **`README.md`**: This documentation file for the backend.

---

## `app/` – Application Package

Top-level application package for the backend.

- **Purpose**: Contains everything required to run the FastAPI app: entrypoint, API routers, configuration, core utilities, schemas, and services.
- **Typical content**: `__init__.py` (optional), FastAPI app instance, routing setup, domain logic, and helpers.

### `app/main.py`

- **Purpose**: Entry point of the backend service.
- **What should be here**:
  - Creation of the FastAPI application instance (`FastAPI()`).
  - Inclusion of API routers (for example from `app.api.v1.api`).
  - Startup and shutdown event handlers (DB connection, clients, background workers, etc.).
  - Basic middleware (CORS, logging, error handling) if not centralized elsewhere.
- **Example responsibilities**:
  - `app = FastAPI(title="Nanosoft AI Backend")`
  - `app.include_router(api_router, prefix="/api/v1")`

### `app/config.py`

- **Purpose**: Central place for configuration and environment settings.
- **What should be here**:
  - Settings class (usually using `pydantic` `BaseSettings`) for environment variables:
    - App name, environment, debug flag.
    - Database URLs.
    - External API keys (OpenAI, vector DB, etc.).
    - Security-related settings (JWT secret, token expiry).
  - Logic to load `.env` or OS environment variables.
- **How it is used**:
  - Imported by other modules (`core`, `services`, `main`) to access `settings` instead of hardcoding values.

### `app/api/` – API Layer

Holds versioned API routing logic.

- **Purpose**: Define HTTP endpoints and group them by versions and domains.
- **Structure**:
  - `api/v1/` – version 1 of the public API.
    - `api.py` – central router for v1.
    - `routes/` – submodules with domain-specific routers (e.g. `chat.py`, `auth.py`).

#### `app/api/v1/api.py`

- **Purpose**: Aggregate and expose all version 1 routes.
- **What should be here**:
  - `APIRouter` instance for v1.
  - Imports and inclusion of routers from `app.api.v1.routes`.
  - Optional common dependencies for all v1 endpoints (auth, rate limiting, etc.).
- **Typical pattern**:
  - `api_router = APIRouter()`
  - `api_router.include_router(chat_router, prefix="/chat", tags=["chat"])`

#### `app/api/v1/routes/`

- **Purpose**: Domain-specific route modules.
- **What should be here**:
  - One file per feature/domain, for example:
    - `chat.py` – endpoints for chat/completions.
    - `files.py` – endpoints for file upload/download.
    - `auth.py` – login, logout, token refresh.
  - Each file defines an `APIRouter` with endpoint functions using FastAPI decorators (`@router.get`, `@router.post`, etc.).
- **Responsibilities of route modules**:
  - Parse and validate requests using `app.schemas`.
  - Call business logic from `app.services`.
  - Return responses or raise HTTP exceptions.

### `app/core/`

- **Purpose**: Cross-cutting application concerns and core infrastructure.
- **What should be here**:
  - Security/auth utilities (JWT helpers, password hashing).
  - Database/session setup (SQLAlchemy, ORM, or other persistence).
  - Global exception handlers and logging setup.
  - Application-wide middleware definitions if not in `main.py`.
- **Typical modules**:
  - `security.py`, `db.py`, `logging.py`, `config_loader.py`.

### `app/schemas/`

- **Purpose**: Pydantic models (request/response schemas and shared DTOs).
- **What should be here**:
  - Request models (e.g., `ChatRequest`, `LoginRequest`).
  - Response models (e.g., `ChatResponse`, `UserOut`).
  - Shared models reused across multiple routes.
- **How they are used**:
  - Imported by route handlers for request body and response models.
  - Used by services to enforce type safety and clear boundaries.

### `app/services/`

- **Purpose**: Business logic and integrations, isolated from HTTP layer.
- **What should be here**:
  - Core domain services:
    - Chat/completions/orchestration logic.
    - File processing or document ingestion.
    - User management, authentication logic (if not solely in `core`).
  - Integrations with external systems:
    - AI model providers (OpenAI, Azure, etc.).
    - Vector databases / search engines.
    - Email/SMS or other third-party APIs.
- **Responsibilities**:
  - Implement actual “work” of the backend.
  - Be independent of FastAPI specifics (no `Request`, `Response` types if possible).

### `app/utils/`

- **Purpose**: Small, reusable helper functions that don’t belong to a single domain.
- **What should be here**:
  - Utility functions for:
    - String manipulation, parsing, formatting.
    - Common error handling patterns.
    - Date/time utilities, ID generation, etc.
- **Guideline**:
  - Avoid putting core business logic here; keep it in `services`.

---

## `files/` – File Storage

- **Purpose**: Local file storage used by the backend.
- **What should be here**:
  - Uploaded files (e.g., documents, datasets).
  - Temporary exports or generated artifacts.
  - Any persistent or cache-like files that the backend manages locally.
- **Notes**:
  - Consider adding `.gitignore` rules if you don’t want actual data files committed.
  - Keep large or sensitive files out of version control.

---

## `requirements.txt`

- **Purpose**: Define Python dependencies required to run the backend.
- **What should be here**:
  - FastAPI and ASGI server (e.g., `fastapi`, `uvicorn`).
  - Pydantic and other validation libraries.
  - Database/ORM libraries if used.
  - AI/ML/LLM clients (e.g., `openai`, `httpx`, vector DB clients).
  - Any additional utilities (logging, config, testing).

Example installation command:

```bash
pip install -r requirements.txt
```

---

## Running the Backend (Suggested Flow)

Once the files are implemented:

1. **Create and activate a virtual environment** (recommended).
2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the FastAPI app with Uvicorn** (assuming `app/main.py` defines `app`):

   ```bash
   uvicorn app.main:app --reload
   ```

4. **Open the interactive API docs**:
   - Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

This README describes the intended structure and purpose of each folder/file so you can gradually implement the Nanosoft AI backend in a clean, maintainable way.


