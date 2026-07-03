"""
Advance Agent — Main Router
Only execution has HTTP routes.
Analysis folder contains question definitions only (no routes).
Retrieval folder contains data + filter function (no routes).
"""
from fastapi import APIRouter
from app.api.advance.execution.routes import router as execution_router

router = APIRouter(prefix="/advance", tags=["Advance Agent"])
router.include_router(execution_router, prefix="/execution", tags=["Advance - Execution"])
