from flask import Blueprint, request, jsonify, Response, stream_with_context
from functools import wraps
from services.auth_service import AuthService
from models import User, Conversation, Message, TokenTransaction
from database import async_session_factory
from sqlalchemy import select
from services.async_llm_service import AsyncLLMService
import asyncio
import json
import time
import threading
from datetime import datetime

async_chat_bp = Blueprint('async_chat', __name__)

# Create a single event loop for all async operations
_loop = None
_loop_lock = threading.Lock()

def get_event_loop():
    """Get or create a persistent event loop"""
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
        return _loop

def run_async(coro):
    """Run async coroutine in the persistent event loop"""
    loop = get_event_loop()
    return loop.run_until_complete(coro)

def jwt_required(f):
    """Decorator to require JWT authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid token'}), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            payload = AuthService.verify_token(token, 'access')
            request.user_id = payload['user_id']
            request.username = payload['username']
        except ValueError as e:
            return jsonify({'error': str(e)}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

# ============ Conversation Endpoints ============

@async_chat_bp.route('/api/conversations', methods=['GET'])
@jwt_required
def get_conversations():
    """Get all conversations for current user"""
    async def _get():
        async with async_session_factory() as session:
            result = await session.execute(
                select(Conversation)
                .where(Conversation.user_id == request.user_id)
                .where(Conversation.is_active == True)
                .order_by(Conversation.updated_at.desc())
            )
            conversations = result.scalars().all()
            return jsonify({
                'conversations': [conv.to_dict() for conv in conversations]
            }), 200
    
    try:
        return run_async(_get())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@async_chat_bp.route('/api/conversations', methods=['POST'])
@jwt_required
def create_conversation():
    """Create a new conversation"""
    async def _create():
        data = request.json or {}
        title = data.get('title', 'New Conversation')
        
        async with async_session_factory() as session:
            conversation = Conversation(
                user_id=request.user_id,
                title=title
            )
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            return jsonify({'conversation': conversation.to_dict()}), 201
    
    try:
        return run_async(_create())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@async_chat_bp.route('/api/conversations/<int:conversation_id>', methods=['GET'])
@jwt_required
def get_conversation(conversation_id):
    """Get specific conversation with messages"""
    async def _get():
        async with async_session_factory() as session:
            result = await session.execute(
                select(Conversation)
                .where(Conversation.id == conversation_id)
                .where(Conversation.user_id == request.user_id)
            )
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                return jsonify({'error': 'Conversation not found'}), 404
            
            result = await session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )
            messages = result.scalars().all()
            
            return jsonify({
                'conversation': conversation.to_dict(),
                'messages': [msg.to_dict() for msg in messages]
            }), 200
    
    try:
        return run_async(_get())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@async_chat_bp.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
@jwt_required
def delete_conversation(conversation_id):
    """Soft delete a conversation"""
    async def _delete():
        async with async_session_factory() as session:
            result = await session.execute(
                select(Conversation)
                .where(Conversation.id == conversation_id)
                .where(Conversation.user_id == request.user_id)
            )
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                return jsonify({'error': 'Conversation not found'}), 404
            
            conversation.is_active = False
            await session.commit()
            return jsonify({'message': 'Conversation deleted'}), 200
    
    try:
        return run_async(_delete())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ Chat Endpoint ============

@async_chat_bp.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    """Main chat endpoint - handles all chat requests"""
    if request.method == 'OPTIONS':
        return '', 200
    
    # Authenticate
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid token'}), 401
    
    token = auth_header.split(' ')[1]
    try:
        payload = AuthService.verify_token(token, 'access')
        user_id = payload['user_id']
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    
    # Check if async mode is requested
    is_async = request.headers.get('X-Async-Mode') == 'true'
    
    try:
        if is_async:
            return run_async(_chat_async_handler(user_id))
        else:
            return run_async(_chat_handler(user_id))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

async def _chat_handler(user_id):
    """Handle chat request"""
    data = request.json
    prompt = data.get('prompt', '')
    conversation_id = data.get('conversation_id')
    
    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400
    
    start_time = time.time()
    
    # Get or create conversation and save user message
    async with async_session_factory() as session:
        conversation = None
        if conversation_id:
            result = await session.execute(
                select(Conversation)
                .where(Conversation.id == conversation_id)
                .where(Conversation.user_id == user_id)
            )
            conversation = result.scalar_one_or_none()
        
        if not conversation:
            conversation = Conversation(
                user_id=user_id,
                title=prompt[:50] + ('...' if len(prompt) > 50 else '')
            )
            session.add(conversation)
            await session.flush()
        
        user_message = Message(
            conversation_id=conversation.id,
            role='user',
            content=prompt
        )
        session.add(user_message)
        await session.commit()
        conv_id = conversation.id
    
    # Generate response from Ollama
    result = await AsyncLLMService.generate_response(prompt, user_id, conv_id)
    
    processing_time = time.time() - start_time
    
    # Save assistant message and update tokens
    async with async_session_factory() as session:
        result_user = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result_user.scalar_one_or_none()
        
        if user:
            user.tokens -= result['tokens_used']
            user.total_tokens_used = (user.total_tokens_used or 0) + result['tokens_used']
            user.total_requests = (user.total_requests or 0) + 1
            
            transaction = TokenTransaction(
                user_id=user_id,
                amount=-result['tokens_used'],
                transaction_type='usage',
                description='Chat completion',
                tokens_processed=len(result['response'].split()),
                processing_time=processing_time
            )
            session.add(transaction)
        
        assistant_message = Message(
            conversation_id=conv_id,
            role='assistant',
            content=result['response'],
            tokens_used=result['tokens_used']
        )
        session.add(assistant_message)
        
        # Update conversation timestamp
        conv_result = await session.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        conv = conv_result.scalar_one_or_none()
        if conv:
            conv.updated_at = datetime.utcnow()
            if conv.title == 'New Conversation':
                conv.title = prompt[:50] + ('...' if len(prompt) > 50 else '')
        
        await session.commit()
    
    return jsonify({
        'response': result['response'],
        'tokens_used': result['tokens_used'],
        'tokens_remaining': user.tokens if user else 0,
        'conversation_id': conv_id,
        'from_cache': result.get('from_cache', False),
        'processing_time': processing_time
    }), 200

async def _chat_async_handler(user_id):
    """Handle async chat request (with task tracking)"""
    data = request.json
    prompt = data.get('prompt', '')
    conversation_id = data.get('conversation_id')
    
    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400
    
    # Get or create conversation and save user message
    async with async_session_factory() as session:
        conversation = None
        if conversation_id:
            result = await session.execute(
                select(Conversation)
                .where(Conversation.id == conversation_id)
                .where(Conversation.user_id == user_id)
            )
            conversation = result.scalar_one_or_none()
        
        if not conversation:
            conversation = Conversation(
                user_id=user_id,
                title=prompt[:50] + ('...' if len(prompt) > 50 else '')
            )
            session.add(conversation)
            await session.flush()
        
        user_message = Message(
            conversation_id=conversation.id,
            role='user',
            content=prompt
        )
        session.add(user_message)
        await session.commit()
        conv_id = conversation.id
    
    # Generate response
    result = await AsyncLLMService.generate_response(prompt, user_id, conv_id)
    
    # Save results
    async with async_session_factory() as session:
        result_user = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result_user.scalar_one_or_none()
        
        if user:
            user.tokens -= result['tokens_used']
            user.total_tokens_used = (user.total_tokens_used or 0) + result['tokens_used']
            user.total_requests = (user.total_requests or 0) + 1
            
            transaction = TokenTransaction(
                user_id=user_id,
                amount=-result['tokens_used'],
                transaction_type='usage',
                description='Async chat completion',
                tokens_processed=len(result['response'].split()),
                processing_time=result['processing_time']
            )
            session.add(transaction)
        
        assistant_message = Message(
            conversation_id=conv_id,
            role='assistant',
            content=result['response'],
            tokens_used=result['tokens_used']
        )
        session.add(assistant_message)
        
        await session.commit()
    
    return jsonify({
        'response': result['response'],
        'tokens_used': result['tokens_used'],
        'tokens_remaining': user.tokens if user else 0,
        'conversation_id': conv_id,
        'from_cache': result.get('from_cache', False),
        'processing_time': result.get('processing_time', 0),
        'async': True
    }), 200