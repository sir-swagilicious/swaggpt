from celery_app import celery_app
from services.llm_service import LLMService
from services.chat_service import ChatService
from models import db
import time
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name='generate_llm_response')
def generate_llm_response(self, prompt, user_id, conversation_id):
    """
    Async task to generate LLM response.
    This runs in a separate worker process, demonstrating true asynchronicity.
    """
    task_id = self.request.id
    logger.info(f"🚀 Starting async LLM task {task_id}")
    logger.info(f"   User: {user_id}, Conversation: {conversation_id}")
    logger.info(f"   Prompt: {prompt[:50]}...")
    
    try:
        # Update task state to show progress
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'Processing request',
                'progress': 10,
                'task_id': task_id
            }
        )
        
        # Simulate processing steps (so we can see async progress)
        time.sleep(0.5)
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'Sending to LLM',
                'progress': 30,
                'task_id': task_id
            }
        )
        
        # Generate response from LLM
        result = LLMService.generate_response_sync(prompt, user_id, conversation_id)
        
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'Processing response',
                'progress': 70,
                'task_id': task_id
            }
        )
        
        # Simulate post-processing
        time.sleep(0.3)
        
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'Saving to database',
                'progress': 90,
                'task_id': task_id
            }
        )
        
        # Save to database (in a real app, you'd inject the db session)
        # For now, we return the result to be saved by the controller
        
        logger.info(f"✅ Async LLM task {task_id} completed")
        
        return {
            'task_id': task_id,
            'status': 'completed',
            'response': result['response'],
            'tokens_used': result['tokens_used'],
            'processing_time': result['processing_time'],
            'from_cache': result.get('from_cache', False),
            'conversation_id': conversation_id
        }
        
    except Exception as e:
        logger.error(f"❌ Async LLM task {task_id} failed: {e}")
        self.update_state(
            state='FAILURE',
            meta={
                'status': 'Failed',
                'error': str(e),
                'task_id': task_id
            }
        )
        raise

@celery_app.task(bind=True, name='batch_generate_responses')
def batch_generate_responses(self, prompts, user_id, conversation_id):
    """
    Async task to generate multiple responses in batch.
    Demonstrates parallel processing capability.
    """
    task_id = self.request.id
    results = []
    
    for i, prompt in enumerate(prompts):
        self.update_state(
            state='PROCESSING',
            meta={
                'status': f'Processing prompt {i+1}/{len(prompts)}',
                'progress': (i / len(prompts)) * 100,
                'task_id': task_id
            }
        )
        
        result = LLMService.generate_response_sync(prompt, user_id, conversation_id)
        results.append(result)
    
    return {
        'task_id': task_id,
        'status': 'completed',
        'results': results
    }