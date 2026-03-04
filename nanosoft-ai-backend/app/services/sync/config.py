import logging
from app.config import settings

log = logging.getLogger("sync_engine")

ENDPOINTS = ["/getAssets", "/getPPM", "/getBDM"]

REQUEST_TIMEOUT = 120
MAX_RETRIES = 3
PAGE_SIZE = settings.SYNC_PAGE_SIZE