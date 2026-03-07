import time
import requests
from datetime import timezone
from requests.exceptions import RequestException, Timeout

from .config import log, REQUEST_TIMEOUT, MAX_RETRIES, PAGE_SIZE, LOGIN_USERNAME, LOGIN_PASSWORD


# ─────────────────────────────────────────────────────────────
# LOGIN — call /login endpoint to get fresh jwt_token + user_id
# Returns ("Bearer <token>", user_id) or (None, None) on failure
# ─────────────────────────────────────────────────────────────
def fetch_login(base_url: str):
    url = f"{base_url}/askmeapi/login"

    payload = {
        "username":"SMARTFM",
        "password":"n@n0@313",
    }

    headers = {"Content-Type": "application/json"}

    log.info(f"  [/login] Calling {url} ...")

    response = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            break
        except (Timeout, RequestException) as e:
            if attempt == MAX_RETRIES:
                log.error(f"  [/login] FAILED after {MAX_RETRIES} retries: {e}")
                return None, None
            log.warning(f"  [/login] Attempt {attempt}/{MAX_RETRIES} failed: {e} — retrying in 2s ...")
            time.sleep(2)

    if response is None:
        return None, None

    if response.status_code != 200:
        log.error(f"  [/login] Unexpected status {response.status_code}: {response.text[:300]}")
        return None, None

    try:
        data = response.json()
        token   = data.get("token")
        user_id = data.get("userId")

        if not token or not user_id:
            log.error(f"  [/login] Missing token or userId in response: {data}")
            return None, None

        jwt_token = f"Bearer {token}"
        log.info(f"  [/login] ✅ Login successful — userId={user_id}")
        return jwt_token, user_id

    except Exception as e:
        log.error(f"  [/login] Failed to parse login response: {e} | Body: {response.text[:300]}")
        return None, None


# ─────────────────────────────────────────────────────────────
# FETCH SINGLE PAGE — fetch one page from assets/ppm/bdm endpoint
# ─────────────────────────────────────────────────────────────
def fetch_single_page(base_url: str, jwt_token: str, user_id: int,
                      endpoint: str, last_synced_at, page_index: int) -> list:

    url = f"{base_url}/askmeapi{endpoint}"

    if last_synced_at is not None:
        if hasattr(last_synced_at, "astimezone"):
            synced_ts = last_synced_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        else:
            synced_ts = str(last_synced_at)
    else:
        synced_ts = "" 

    headers = {
        "x-auth":       jwt_token,
        "userid":       str(user_id),
        "Content-Type": "application/json",
    }

    payload = {
        "data": {
            "PageIndex": page_index,
            "PageSize":  PAGE_SIZE,
            "DateTime":  synced_ts,
        }
    }

    log.info(f"  [{endpoint}] Fetching page {page_index} (DateTime={synced_ts}) ...")

    response = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
            )
            break
        except (Timeout, RequestException) as e:
            if attempt == MAX_RETRIES:
                log.error(f"  [{endpoint}] Page {page_index} FAILED after {MAX_RETRIES} retries: {e}")
                return []
            log.warning(f"  [{endpoint}] Attempt {attempt}/{MAX_RETRIES} failed: {e} — retrying in 2s ...")
            time.sleep(2)

    if response is None:
        return []

    if response.status_code == 400 and "No records found" in response.text:
        log.info(f"  [{endpoint}] No more records at page {page_index}. Done.")
        return []

    if response.status_code != 200:
        log.error(f"  [{endpoint}] Unexpected status {response.status_code}: {response.text[:300]}")
        return []

    try:
        resp_json = response.json()
    except Exception as e:
        log.error(f"  [{endpoint}] Invalid JSON on page {page_index}: {e} | Body: {response.text[:300]}")
        return []

    return _extract_records(resp_json)


def _extract_records(resp_json: dict) -> list:
    output = resp_json.get("Output") or resp_json.get("output")
    if isinstance(output, dict):
        records = output.get("data") or output.get("Data") or []
    else:
        raw = resp_json.get("data") or resp_json.get("Data")
        if isinstance(raw, list):
            records = raw
        elif isinstance(raw, dict):
            records = (
                raw.get("records") or raw.get("Records") or
                raw.get("data")    or raw.get("Data")    or
                raw.get("items")   or raw.get("Items")   or []
            )
        else:
            records = []

    if not isinstance(records, list):
        records = []
    return records