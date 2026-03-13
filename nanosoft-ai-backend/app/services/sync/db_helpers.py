from .config import log


def get_clients(cursor):
    
    cursor.execute("""
        SELECT client_name, base_url, user_id, user_name, jwt_token, last_synced_at
        FROM client_sync_config
        ORDER BY client_name
    """)
    return cursor.fetchall()


def update_sync_timestamp(cursor, client_name):
    cursor.execute("""
        UPDATE client_sync_config
        SET last_synced_at = now()
        WHERE client_name = %s
    """, (client_name,))