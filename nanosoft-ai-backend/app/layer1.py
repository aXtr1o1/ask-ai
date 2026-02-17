import time
import uuid
import threading
import sys
import requests
from collections import deque
from typing import Any, Dict, List, Optional

# ==========================================
# 1. CORE CACHE ENGINE (L1 RAM)
# ==========================================
class DynamicVault:
    def __init__(self, max_records: int = 15, ttl: float = 120.0):
        # High-speed Deque for static memory footprint
        self.vault = deque(maxlen=max_records)
        self.ttl = ttl
        self.lock = threading.Lock()
        
        # Start background cleaner (Silent mode to avoid terminal flicker)
        threading.Thread(target=self._auto_clean, daemon=True).start()

    def ingest(self, raw_data: Any, source: str = "LIVE"):
        """Wraps data into a timed packet for the 120s window."""
        packet = {
            "id": f"{source}_{str(uuid.uuid4())[:8]}",
            "payload": raw_data,
            "stored_at": time.time(),
            "size_bytes": sys.getsizeof(raw_data)
        }
        with self.lock:
            self.vault.append(packet)
            return packet["id"]

    def _auto_clean(self):
        """Background thread: Deletes data older than 120 seconds."""
        while True:
            now = time.time()
            with self.lock:
                while self.vault and (now - self.vault[0]['stored_at']) > self.ttl:
                    self.vault.popleft()
            time.sleep(1.0) 

    def get_cached_payload(self, identifier_key: str, identifier_value: str):
        """Thread-safe lookup for existing RAM data."""
        with self.lock:
            for item in self.vault:
                payload = item['payload']
                if isinstance(payload, dict) and payload.get(identifier_key) == identifier_value:
                    return item
        return None

    def get_status(self):
        with self.lock:
            total_ram = sum(p['size_bytes'] for p in self.vault)
            return len(self.vault), total_ram

# ==========================================
# 2. UNIFIED FETCH LOGIC (L1 -> L3)
# ==========================================
def fetch_from_api(endpoint: str, payload: dict, vault: DynamicVault):
    """
    Checks L1 RAM first. If missing, calls FastAPI (L3) and refills RAM.
    """
    # Create a unique key based on endpoint and parameters
    cache_key = f"{endpoint}_{str(sorted(payload.items()))}"
    
    # Check if this exact request is already in L1 RAM
    cached_hit = vault.get_cached_payload("cache_key", cache_key)
    
    if cached_hit:
        print(f"📍 [L1 HIT] Serving from RAM: {endpoint}")
        return cached_hit['payload']['data']

    # Fallback to FastAPI Backend (L3)
    try:
        print(f"📡 [L1 MISS] Fetching from FastAPI: {endpoint}")
        url = f"http://127.0.0.1:8000{endpoint}"
        response = requests.post(url, json=payload, timeout=5)
        
        if response.status_code == 200:
            api_data = response.json()
            # REFILL L1: Store the result for the next 120 seconds
            vault.ingest({"cache_key": cache_key, "data": api_data}, source="API_SYNC")
            return api_data
            
    except Exception as e:
        print(f"❌ Connection Error: Ensure FastAPI is running on port 8000. ({e})")
    
    return None

# ==========================================
# 3. AUTOMATIC EXECUTION
# ==========================================
if __name__ == "__main__":
    # Initialize L1 Vault
    l1_vault = DynamicVault(max_records=20, ttl=120.0)
    print("🚀 LAYER 1 CACHE ACTIVE | 120s TTL Enabled")

    # Example Test: Assets Request
    asset_query = {"division": "Construction", "limit": 5}
    
    # Execution 1: Hits FastAPI
    print("\n--- Request 1 ---")
    res1 = fetch_data("/get-assets", asset_query, l1_vault)
    
    # Execution 2: Hits RAM (Instantly)
    print("\n--- Request 2 ---")
    res2 = fetch_data("/get-assets", asset_query, l1_vault)

    items, ram = l1_vault.get_status()
    print(f"\n📊 RAM Status: {items} items | {ram} bytes used.")