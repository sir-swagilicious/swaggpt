import redis
import json
from config import Config

class RedisClient:
    def __init__(self):
        self.client = redis.Redis.from_url(
            Config.REDIS_URL,
            decode_responses=True
        )
    
    def set_session(self, user_id, session_data, ttl=604800):
        """Store session data with 7-day TTL"""
        key = f"session:{user_id}"
        self.client.setex(key, ttl, json.dumps(session_data))
    
    def get_session(self, user_id):
        """Retrieve session data"""
        key = f"session:{user_id}"
        data = self.client.get(key)
        return json.loads(data) if data else None
    
    def delete_session(self, user_id):
        """Delete session data"""
        key = f"session:{user_id}"
        self.client.delete(key)
    
    def cache_response(self, key, data, ttl=3600):
        """Cache LLM responses"""
        cache_key = f"cache:{key}"
        self.client.setex(cache_key, ttl, json.dumps(data))
    
    def get_cached_response(self, key):
        """Get cached LLM response"""
        cache_key = f"cache:{key}"
        data = self.client.get(cache_key)
        return json.loads(data) if data else None
    
    def store_oauth_state(self, state, ttl=600):
        """Store OAuth state for GitHub auth"""
        self.client.setex(f"oauth:{state}", ttl, "1")
    
    def validate_oauth_state(self, state):
        """Validate OAuth state"""
        return self.client.exists(f"oauth:{state}")
    
    def add_to_queue(self, queue_name, data):
        """Add task to Redis queue"""
        self.client.lpush(queue_name, json.dumps(data))
    
    def get_from_queue(self, queue_name, timeout=0):
        """Get task from Redis queue (blocking)"""
        result = self.client.brpop(queue_name, timeout=timeout)
        if result:
            return json.loads(result[1])
        return None

redis_client = RedisClient()