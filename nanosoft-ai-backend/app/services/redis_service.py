"""
Redis Session Management Service
Handles conversation history storage and retrieval
"""
import redis
import json
import uuid
from datetime import datetime
from typing import List, Dict, Tuple
from langchain_core.messages import HumanMessage, AIMessage
import logging

from app.config import settings

# ===========================
# LOGGER SETUP
# ===========================
logger = logging.getLogger("redis_service")
logger.setLevel(logging.INFO)

# Console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# Prevent duplicate handlers
if not logger.handlers:
    logger.addHandler(ch)


class RedisService:
    """Manages Redis connection and session operations"""
    
    def __init__(self):
        """Initialize Redis client"""
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                decode_responses=True,
                username=settings.REDIS_USERNAME,
                password=settings.REDIS_PASSWORD,
            )
            self._test_connection()
        except Exception as e:
            logger.error(f"❌ Failed to initialize Redis client: {e}", exc_info=True)
            raise
    
    def _test_connection(self):
        """Test Redis connection"""
        try:
            self.client.ping()
            logger.info("✅ Redis connection successful")
        except Exception as e:
            logger.critical(f"❌ Redis connection failed: {e}", exc_info=True)
            raise
    
    def create_session_id(self) -> str:
        """Generate a new session ID"""
        session_id = str(uuid.uuid4())
        logger.debug(f"🆔 Created new session ID: {session_id}")
        return session_id
    
    def fetch_session_history(
        self, 
        user: str, 
        session_id: str, 
        limit: int = None
    ) -> Tuple[List, List]:
        """
        Fetch session history from Redis
        
        Returns:
            Tuple of (langchain_memory, redis_memory)
        """
        if limit is None:
            limit = settings.MAX_HISTORY
            
        key = f"user:{user}:session:{session_id}"
        data = self.client.get(key)
        
        lc_memory = []
        redis_memory = []
        
        if data:
            records = json.loads(data)
            for item in records[-limit:]:
                lc_memory.append(HumanMessage(content=item["query"]))
                lc_memory.append(AIMessage(content=item["result"]))
                redis_memory.append(item)
        
        logger.info(f"📂 Fetched {len(redis_memory)} records for session: {key}")
        return lc_memory, redis_memory
    
    def save_session(self, user: str, session_id: str, redis_memory: List[Dict]):
        """Save session to Redis with TTL"""
        try:
            key = f"user:{user}:session:{session_id}"
            self.client.set(key, json.dumps(redis_memory))
            self.client.expire(key, settings.SESSION_TTL_SECONDS)
            logger.info(f"💾 Session saved: {key} (TTL={settings.SESSION_TTL_SECONDS}s)")
        except Exception as e:
            logger.error(f"❌ Failed to save session {key}: {e}", exc_info=True)
            raise
    
    def add_to_memory(
        self, 
        redis_memory: List[Dict], 
        query: str, 
        result: str
    ) -> List[Dict]:
        """Add new query-result pair to memory"""
        record = {
            "query": query,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        redis_memory.append(record)
        logger.debug(f"➕ Added new memory record: {record}")
        return redis_memory


# Global Redis service instance
redis_service = RedisService()
