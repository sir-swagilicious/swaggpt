import aiohttp
import json
import time
import hashlib
import os
from redis_client import async_redis_client

OLLAMA_API_URL = os.environ.get('OLLAMA_API_URL', 'http://localhost:11434/api')
MODEL_NAME = os.environ.get('MODEL_NAME', 'llama3.1:8b')

class AsyncLLMService:
    conversation_contexts = {}
    
    @staticmethod
    def calculate_token_cost(prompt_length, response_length, processing_time):
        """Calculate token cost"""
        input_tokens = max(1, prompt_length // 4)
        output_tokens = max(1, response_length // 4)
        time_factor = max(1, int(processing_time))
        total_cost = input_tokens * 1 + output_tokens * 2 + time_factor * 5
        return int(total_cost)
    
    @staticmethod
    def get_cache_key(prompt, context_hash):
        """Generate cache key"""
        combined = f"{prompt}:{context_hash}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    @staticmethod
    async def generate_response(prompt, user_id, conversation_id):
        """Async generate response from Ollama"""
        start_time = time.time()
        
        # Check cache
        context_hash = hashlib.md5(
            str(AsyncLLMService.conversation_contexts.get(f"{user_id}_{conversation_id}", [])).encode()
        ).hexdigest()
        
        cache_key = AsyncLLMService.get_cache_key(prompt, context_hash)
        cached = await async_redis_client.get_cached_response(cache_key)
        
        if cached:
            return {
                'response': cached['response'],
                'tokens_used': cached['tokens_used'],
                'processing_time': 0.01,
                'from_cache': True
            }
        
        # Get conversation context
        ollama_context = AsyncLLMService.conversation_contexts.get(
            f"{user_id}_{conversation_id}", []
        )
        
        # Prepare payload
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False
        }
        
        if ollama_context and isinstance(ollama_context, list) and len(ollama_context) > 0:
            payload["context"] = ollama_context
        
        # Make async HTTP request to Ollama
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{OLLAMA_API_URL}/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    
                    if response.status != 200:
                        text = await response.text()
                        raise Exception(f"Ollama error: {text}")
                    
                    result = await response.json()
        except Exception as e:
            raise Exception(f"Failed to communicate with Ollama: {str(e)}")
        
        full_response = result.get('response', '')
        new_context = result.get('context', [])
        
        processing_time = time.time() - start_time
        token_cost = AsyncLLMService.calculate_token_cost(
            len(prompt), len(full_response), processing_time
        )
        
        # Save context
        if new_context:
            AsyncLLMService.conversation_contexts[f"{user_id}_{conversation_id}"] = new_context
        
        # Cache response
        cache_data = {
            'response': full_response,
            'tokens_used': token_cost
        }
        await async_redis_client.cache_response(cache_key, cache_data)
        
        return {
            'response': full_response,
            'tokens_used': token_cost,
            'processing_time': processing_time,
            'from_cache': False
        }
    
    @staticmethod
    async def generate_response_stream(prompt, user_id, conversation_id):
        """Async streaming response from Ollama"""
        ollama_context = AsyncLLMService.conversation_contexts.get(
            f"{user_id}_{conversation_id}", []
        )
        
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": True
        }
        
        if ollama_context and isinstance(ollama_context, list) and len(ollama_context) > 0:
            payload["context"] = ollama_context
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_API_URL}/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                
                # Read the response line by line
                buffer = ""
                async for data, end_of_http_chunk in response.content.iter_chunks():
                    if data:
                        buffer += data.decode('utf-8')
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            line = line.strip()
                            if line:
                                try:
                                    chunk_data = json.loads(line)
                                    yield chunk_data
                                except json.JSONDecodeError:
                                    continue