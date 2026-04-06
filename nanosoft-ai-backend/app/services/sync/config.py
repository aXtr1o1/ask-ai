import logging
from app.config import settings

log = logging.getLogger("sync_engine")

ENDPOINTS = ["/getAssets", "/getPPM", "/getBDM", "/getFA", "/getSB"]
LOGIN_USERNAME = settings.LOGIN_USERNAME
LOGIN_PASSWORD = settings.LOGIN_PASSWORD
REQUEST_TIMEOUT = 120
MAX_RETRIES = 3
PAGE_SIZE = settings.SYNC_PAGE_SIZE