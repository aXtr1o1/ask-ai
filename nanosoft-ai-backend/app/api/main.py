"""
Database API FastAPI Application
"""
from fastapi import FastAPI
import logging

from app.api.routes import assets, ppm, bdm

logger = logging.getLogger("db_api_app")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)

db_api_app = FastAPI(
    title="Facility Management Database API",
    description="API for querying Assets, PPM, and BDM",
    version="3.0.0"
)

db_api_app.include_router(assets.router, tags=["Assets"])
db_api_app.include_router(ppm.router, tags=["PPM"])
db_api_app.include_router(bdm.router, tags=["BDM"])


@db_api_app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


@db_api_app.on_event("startup")
def startup_event():
    from app.api.database.supabase_client import get_supabase_client
    get_supabase_client()
    logger.info("🚀 Supabase client initialized during startup")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api.main:db_api_app", host="0.0.0.0", port=8000, reload=True)
