import requests
import json
import time
import hashlib
from config import Config
from redis_client import redis_client

class LLMService:
    # Store conversation contexts
    conversation_contexts = {}
    
    @staticmethod
    def calculate_token_cost(prompt_length, response_length, processing_time):
        """Calculate token cost based on usage"""
        input_tokens = max(1, prompt_length // 4)
        output_tokens = max(1, response_length // 4)
        time_factor = max(1, int(processing_time))
        total_cost = input_tokens * 1 + output_tokens * 2 + time_factor * 5
        return int(total_cost)
    
    @staticmethod
    def get_cache_key(prompt, context_hash):
        """Generate cache key for response"""
        combined = f"{prompt}:{context_hash}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    @staticmethod
    def generate_response_sync(prompt, user_id, conversation_id):
        """Synchronous response generation (used by Celery tasks)"""
        start_time = time.time()
        
        # Check cache first
        context_hash = hashlib.md5(
            str(LLMService.conversation_contexts.get(f"{user_id}_{conversation_id}", [])).encode()
        ).hexdigest()
        
        cache_key = LLMService.get_cache_key(prompt, context_hash)
        cached = redis_client.get_cached_response(cache_key)
        
        if cached:
            return {
                'response': cached['response'],
                'tokens_used': cached['tokens_used'],
                'processing_time': 0.01,
                'from_cache': True
            }
        
        # Get conversation context
        ollama_context = LLMService.conversation_contexts.get(
            f"{user_id}_{conversation_id}", []
        )
        
        # Prepare Ollama request
        payload = {
            "model": Config.MODEL_NAME,
            "prompt": prompt,
            "stream": False
        }
        
        if ollama_context and isinstance(ollama_context, list) and len(ollama_context) > 0:
            payload["context"] = ollama_context
        
        # Make request to Ollama
        response = requests.post(
            f"{Config.OLLAMA_API_URL}/generate",
            json=payload,
            timeout=120
        )
        
        if response.status_code != 200:
            raise Exception(f"Ollama error: {response.text}")
        
        result = response.json()
        full_response = result.get('response', '')
        new_context = result.get('context', [])
        
        processing_time = time.time() - start_time
        token_cost = LLMService.calculate_token_cost(
            len(prompt), len(full_response), processing_time
        )
        
        # Save context for next message
        if new_context:
            LLMService.conversation_contexts[f"{user_id}_{conversation_id}"] = new_context
        
        # Cache the response
        cache_data = {
            'response': full_response,
            'tokens_used': token_cost
        }
        redis_client.cache_response(cache_key, cache_data)
        
        return {
            'response': full_response,
            'tokens_used': token_cost,
            'processing_time': processing_time,
            'from_cache': False
        }
    
    @staticmethod
    def generate_response_stream(prompt, user_id, conversation_id):
        """Generate streaming response from Ollama"""
        ollama_context = LLMService.conversation_contexts.get(
            f"{user_id}_{conversation_id}", []
        )
        
        payload = {
            "model": Config.MODEL_NAME,
            "prompt": prompt,
            "stream": True
        }
        
        if ollama_context and isinstance(ollama_context, list) and len(ollama_context) > 0:
            payload["context"] = ollama_context
        
        response = requests.post(
            f"{Config.OLLAMA_API_URL}/generate",
            json=payload,
            stream=True,
            timeout=120
        )
        
        return response