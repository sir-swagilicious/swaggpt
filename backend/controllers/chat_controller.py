from flask import Blueprint, request, jsonify, Response, stream_with_context
from flask_login import login_required, current_user
from services.chat_service import ChatService
from services.llm_service import LLMService
from models import db
import json
import asyncio

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    """Get all conversations for current user"""
    conversations = ChatService.get_conversations(current_user.id)
    return jsonify({
        'conversations': [conv.to_dict() for conv in conversations]
    }), 200

@chat_bp.route('/api/conversations', methods=['POST'])
@login_required
def create_conversation():
    """Create a new conversation"""
    data = request.json or {}
    title = data.get('title', 'New Conversation')
    
    conversation = ChatService.create_conversation(current_user.id, title)
    
    return jsonify({
        'conversation': conversation.to_dict()
    }), 201

@chat_bp.route('/api/conversations/<int:conversation_id>', methods=['GET'])
@login_required
def get_conversation(conversation_id):
    """Get specific conversation with messages"""
    conversation, messages = ChatService.get_conversation(
        conversation_id, current_user.id
    )
    
    if not conversation:
        return jsonify({'error': 'Conversation not found'}), 404
    
    return jsonify({
        'conversation': conversation.to_dict(),
        'messages': [msg.to_dict() for msg in messages]
    }), 200

@chat_bp.route('/api/conversations/<int:conversation_id>', methods=['PUT'])
@login_required
def update_conversation(conversation_id):
    """Update conversation title"""
    data = request.json
    conversation, _ = ChatService.get_conversation(conversation_id, current_user.id)
    
    if not conversation:
        return jsonify({'error': 'Conversation not found'}), 404
    
    if 'title' in data:
        conversation.title = data['title']
        db.session.commit()
    
    return jsonify({'conversation': conversation.to_dict()}), 200

@chat_bp.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
@login_required
def delete_conversation(conversation_id):
    """Delete a conversation"""
    try:
        ChatService.delete_conversation(conversation_id, current_user.id)
        return jsonify({'message': 'Conversation deleted'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404

@chat_bp.route('/api/chat/sync', methods=['POST'])
@login_required
def chat_sync():
    """Synchronous chat endpoint"""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        conversation_id = data.get('conversation_id')
        
        if not prompt:
            return jsonify({'error': 'No prompt provided'}), 400
        
        # Save user message
        conversation, user_message = ChatService.save_user_message(
            conversation_id, current_user.id, prompt
        )
        
        # Generate response (async)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            LLMService.generate_response(prompt, current_user.id, conversation.id)
        )
        loop.close()
        
        # Deduct tokens
        user = ChatService.deduct_tokens(
            current_user.id,
            result['tokens_used'],
            f'Chat completion in conversation #{conversation.id}',
            tokens_processed=len(result['response'].split()),
            processing_time=result['processing_time']
        )
        
        # Save assistant message
        assistant_message = ChatService.save_assistant_message(
            conversation.id,
            result['response'],
            result['tokens_used']
        )
        
        return jsonify({
            'response': result['response'],
            'tokens_used': result['tokens_used'],
            'tokens_remaining': user.tokens,
            'conversation_id': conversation.id,
            'from_cache': result.get('from_cache', False)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@chat_bp.route('/api/chat', methods=['POST'])
@login_required
def chat_stream():
    """Streaming chat endpoint"""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        conversation_id = data.get('conversation_id')
        
        if not prompt:
            return jsonify({'error': 'No prompt provided'}), 400
        
        # Save user message
        conversation, user_message = ChatService.save_user_message(
            conversation_id, current_user.id, prompt
        )
        
        def generate():
            try:
                # Get streaming response
                response = LLMService.generate_response_stream(
                    prompt, current_user.id, conversation.id
                )
                
                full_response = ""
                
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            
                            if 'response' in data:
                                text_chunk = data['response']
                                full_response += text_chunk
                                yield f"data: {json.dumps({'text': text_chunk, 'done': data.get('done', False)})}\n\n"
                            
                            if data.get('done', False):
                                # Calculate cost
                                token_cost = LLMService.calculate_token_cost(
                                    len(prompt), len(full_response), 0
                                )
                                
                                # Deduct tokens
                                user = ChatService.deduct_tokens(
                                    current_user.id,
                                    token_cost,
                                    f'Chat completion in conversation #{conversation.id}',
                                    tokens_processed=len(full_response.split()),
                                    processing_time=0
                                )
                                
                                # Save assistant message
                                ChatService.save_assistant_message(
                                    conversation.id,
                                    full_response,
                                    token_cost
                                )
                                
                                yield f"data: {json.dumps({'done': True, 'tokens_used': token_cost, 'tokens_remaining': user.tokens, 'conversation_id': conversation.id})}\n\n"
                                
                        except json.JSONDecodeError:
                            continue
                            
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500