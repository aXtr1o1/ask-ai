"""
Database API FastAPI Application
Provides endpoints for querying Supabase database
"""
from fastapi import FastAPI

# =====================================================
# ✅ Import Route Modules
# =====================================================
from app.api.routes import assets, complaints, workorders

# =====================================================
# ✅ FastAPI App Initialization
# =====================================================
db_api_app = FastAPI(
    title="Facility Management Database API",
    description="API for querying assets, complaints, and work orders",
    version="2.0.0"
)

# =====================================================
# ✅ Include Route Modules
# =====================================================
db_api_app.include_router(assets.router, tags=["Assets"])
db_api_app.include_router(complaints.router, tags=["Complaints"])
db_api_app.include_router(workorders.router, tags=["Work Orders"])

# =====================================================
# ✅ FastAPI Startup Event
# =====================================================
@db_api_app.on_event("startup")
def startup_event():
    """
    Initialize Supabase client safely at app startup.
    Ensures environment variables are loaded before client creation.
    """
    from app.api.database.supabase_client import get_supabase_client
    get_supabase_client()
    print("🚀 Supabase client initialized during startup")


# =====================================================
# ✅ Run Application on port 8000
# =====================================================
if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Database API on http://127.0.0.1:8000")
    uvicorn.run(
        "app.api.main:db_api_app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
