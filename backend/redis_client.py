import redis.asyncio as aioredis
import redis as sync_redis
import json
import os

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

class AsyncRedisClient:
    def __init__(self):
        self.client = None
    
    async def connect(self):
        """Initialize async Redis connection"""
        if not self.client:
            self.client = aioredis.from_url(
                REDIS_URL,
                decode_responses=True
            )
        return self.client
    
    async def set_session(self, user_id, session_data, ttl=604800):
        """Store session data"""
        client = await self.connect()
        key = f"session:{user_id}"
        await client.setex(key, ttl, json.dumps(session_data))
    
    async def get_session(self, user_id):
        """Retrieve session data"""
        client = await self.connect()
        key = f"session:{user_id}"
        data = await client.get(key)
        return json.loads(data) if data else None
    
    async def delete_session(self, user_id):
        """Delete session data"""
        client = await self.connect()
        key = f"session:{user_id}"
        await client.delete(key)
    
    async def cache_response(self, key, data, ttl=3600):
        """Cache LLM response"""
        client = await self.connect()
        cache_key = f"cache:{key}"
        await client.setex(cache_key, ttl, json.dumps(data))
    
    async def get_cached_response(self, key):
        """Get cached LLM response"""
        client = await self.connect()
        cache_key = f"cache:{key}"
        data = await client.get(cache_key)
        return json.loads(data) if data else None
    
    async def store_oauth_state(self, state, ttl=600):
        """Store OAuth state"""
        client = await self.connect()
        await client.setex(f"oauth:{state}", ttl, "1")
    
    async def validate_oauth_state(self, state):
        """Validate OAuth state"""
        client = await self.connect()
        return await client.exists(f"oauth:{state}")

# Create async client instance
async_redis_client = AsyncRedisClient()

# Create sync client for backward compatibility
redis_client = sync_redis.Redis.from_url(REDIS_URL, decode_responses=True)