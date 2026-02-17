import os
import redis
import pyodbc
import json
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()

# =====================================================
# ⚡ HOSTED REDIS CONNECTION (L2 - Speed Layer)
# =====================================================
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD"),
    db=0,
    decode_responses=True
)

# =====================================================
# 🏛️ MSSQL CONNECTION (L3 - Permanent Vault)
# =====================================================
def get_mssql_connection():
    """Returns a connection to MSSQL using Windows Authentication."""
    # Note: Double brackets {{ }} are used for the driver name in f-strings
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};" 
        f"SERVER={os.getenv('DB_SERVER', 'localhost')};"
        f"DATABASE={os.getenv('DB_NAME', 'chat_history')};"
        f"Trusted_Connection=yes;" 
    )
    try:
        conn = pyodbc.connect(conn_str)
        return conn
    except Exception as e:
        print(f"❌ MSSQL: Connection Failed - {e}")
        return None

# =====================================================
# 🔄 AUTOMATIC SYNC: REDIS -> MSSQL
# =====================================================
def sync_redis_to_mssql():
    print("\nSTARTING SYNC...")
    keys = redis_client.keys("user:*:session:*")
    
    # ADD THIS LINE TO DEBUG
    print(f"DEBUG: Found {len(keys)} keys in Redis: {keys}") 
    
    if not keys:
        print(" No active sessions found in Redis.")
        return

    # 2. Identify keys to archive
    try:
        keys = redis_client.keys("user:*:session:*")
    except Exception as e:
        print(f"Error scanning Redis keys: {e}")
        return

    if not keys:
        print("No active sessions found in Redis to archive.")
        return

    conn = get_mssql_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    count = 0

    for key in keys:
        try:
            # Extract session_id (the last part of the key)
            parts = key.split(":")
            session_id = parts[-1] 
            data_from_redis = redis_client.get(key)
            
            if data_from_redis:
                # SAFETY CHECK: Only insert if session_id doesn't exist in MSSQL
                cursor.execute("SELECT 1 FROM chat_audit_logs WHERE session_id = ?", (session_id,))
                if cursor.fetchone():
                    print(f"   ⏩ Skipping: {session_id} (Already Archived)")
                    continue

                # Prepare the INSERT statement
                sql_query = "INSERT INTO chat_audit_logs (session_id, history) VALUES (?, ?)"
                
                # MSSQL stores JSON as NVARCHAR(MAX); ensure it is a valid string
                history_json = data_from_redis if isinstance(data_from_redis, str) else json.dumps(data_from_redis)

                cursor.execute(sql_query, (session_id, history_json))
                
                # CRITICAL: pyodbc requires explicit commit
                conn.commit() 
                count += 1
                
                # Mark as archived in Redis by setting a shorter expiry (10 minutes)
                redis_client.expire(key, 600) 
                print(f"   ✅ Archived: {session_id}")
            
        except Exception as e:
            print(f"   ❌ Error processing key {key}: {e}")

    cursor.close()
    conn.close()
    print(f"\n🎉 SYNC COMPLETE: {count} new sessions pushed to MSSQL Vault.\n")

if __name__ == "__main__":
    sync_redis_to_mssql()