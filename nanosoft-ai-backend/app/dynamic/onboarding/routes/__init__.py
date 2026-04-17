"""
dynamic/onboarding/routes/__init__.py
──────────────────────────────────────
Combines all onboarding sub-routers into a single router.

This file is the single import point for main.py.
Instead of importing 3 separate routers, main.py does:

    from app.dynamic.onboarding.routes import router as dynamic_router
    chatbot_app.include_router(dynamic_router)

Sub-routers:
    onboard_routes  → POST /api/client/onboard/service
    sync_routes     → POST /api/client/sync
    registry_routes → GET  /api/client/verify + GET /api/client/registry
"""

import logging
from fastapi import APIRouter

from app.dynamic.onboarding.routes.onboard_routes  import router as onboard_router
from app.dynamic.onboarding.routes.sync_routes     import router as sync_router
from app.dynamic.onboarding.routes.registry_routes import router as registry_router

logger = logging.getLogger("dynamic.routes")

# ── Master router — all sub-routers attach here ───────────────────────────────
# prefix and tags are defined in each sub-router individually
router = APIRouter()

router.include_router(onboard_router)
router.include_router(sync_router)
router.include_router(registry_router)

logger.info("✅ Dynamic onboarding routes registered: onboard + sync + registry")