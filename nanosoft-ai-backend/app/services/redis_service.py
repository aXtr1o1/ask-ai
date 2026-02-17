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

from app.config import settings


class RedisService:
    """Manages Redis connection and session operations"""
    
    def __init__(self):
        """Initialize Redis client"""
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
            username=settings.REDIS_USERNAME,
            password=settings.REDIS_PASSWORD,
        )
        self._test_connection()
    
    def _test_connection(self):
        """Test Redis connection"""
        try:
            self.client.ping()
            print("✅ Redis connection successful")
        except Exception as e:
            print(f"❌ Redis connection failed: {e}")
            raise
    
    def create_session_id(self) -> str:
        """Generate a new session ID"""
        return str(uuid.uuid4())
    
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
        
        return lc_memory, redis_memory
    
    def save_session(self, user: str, session_id: str, redis_memory: List[Dict]):
        """Save session to Redis with TTL"""
        key = f"user:{user}:session:{session_id}"
        self.client.set(key, json.dumps(redis_memory))
        self.client.expire(key, settings.SESSION_TTL_SECONDS)
        print(f"💾 Session saved: {key}")
    
    def add_to_memory(
        self, 
        redis_memory: List[Dict], 
        query: str, 
        result: str
    ) -> List[Dict]:
        """Add new query-result pair to memory"""
        redis_memory.append({
            "query": query,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        })
        return redis_memory


# Global Redis service instance
redis_service = RedisService()