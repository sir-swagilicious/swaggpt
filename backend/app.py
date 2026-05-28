from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from flask_login import LoginManager, login_required, current_user
from models import db, User, TokenTransaction, Conversation, Message
from auth import auth_bp, bcrypt, calculate_token_cost
import requests
import json
import logging
import time
import sys
import os
from datetime import datetime

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.urandom(24).hex()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///llama_chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

# Initialize extensions
db.init_app(app)
bcrypt.init_app(app)

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({'error': 'Unauthorized'}), 401

# Configure CORS
CORS(app, 
     supports_credentials=True,
     origins=["http://localhost:8000", "http://127.0.0.1:8000"],
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"]
)

# Register blueprints
app.register_blueprint(auth_bp)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('backend_debug.log')
    ]
)
logger = logging.getLogger(__name__)

# Ollama API configuration
OLLAMA_API_URL = "http://localhost:11434/api"
MODEL_NAME = "llama3.1:8b"

# Store conversation context for Ollama
conversation_contexts = {}

# Create database tables
with app.app_context():
    db.create_all()

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:8000')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# Conversation Management Endpoints
@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    """Get all conversations for the current user"""
    try:
        conversations = Conversation.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(Conversation.updated_at.desc()).all()
        
        logger.info(f"📋 Retrieved {len(conversations)} conversations for user {current_user.username}")
        
        return jsonify({
            'conversations': [conv.to_dict() for conv in conversations]
        }), 200
    except Exception as e:
        logger.error(f"❌ Error getting conversations: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations', methods=['POST'])
@login_required
def create_conversation():
    """Create a new conversation"""
    try:
        data = request.json or {}
        title = data.get('title', 'New Conversation')
        
        conversation = Conversation(
            user_id=current_user.id,
            title=title
        )
        
        db.session.add(conversation)
        db.session.commit()
        
        logger.info(f"📝 Created conversation {conversation.id} for user {current_user.username}")
        
        return jsonify({
            'conversation': conversation.to_dict()
        }), 201
    except Exception as e:
        logger.error(f"❌ Error creating conversation: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations/<int:conversation_id>', methods=['GET'])
@login_required
def get_conversation(conversation_id):
    """Get a specific conversation with messages"""
    try:
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            user_id=current_user.id
        ).first()
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        messages = Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(Message.created_at).all()
        
        logger.info(f"📖 Retrieved conversation {conversation_id} with {len(messages)} messages")
        
        return jsonify({
            'conversation': conversation.to_dict(),
            'messages': [msg.to_dict() for msg in messages]
        }), 200
    except Exception as e:
        logger.error(f"❌ Error getting conversation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations/<int:conversation_id>', methods=['PUT'])
@login_required
def update_conversation(conversation_id):
    """Update conversation title"""
    try:
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            user_id=current_user.id
        ).first()
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        data = request.json
        if 'title' in data:
            conversation.title = data['title']
            db.session.commit()
        
        return jsonify({
            'conversation': conversation.to_dict()
        }), 200
    except Exception as e:
        logger.error(f"❌ Error updating conversation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
@login_required
def delete_conversation(conversation_id):
    """Soft delete a conversation"""
    try:
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            user_id=current_user.id
        ).first()
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        conversation.is_active = False
        db.session.commit()
        
        logger.info(f"🗑️ Deleted conversation {conversation_id}")
        
        return jsonify({'message': 'Conversation deleted'}), 200
    except Exception as e:
        logger.error(f"❌ Error deleting conversation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# Chat Endpoint - Simplified and Fixed
@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    """Streaming chat endpoint"""
    if request.method == 'OPTIONS':
        return '', 200
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Please log in to continue'}), 401
    
    start_time = time.time()
    
    try:
        data = request.json
        prompt = data.get('prompt', '')
        conversation_id = data.get('conversation_id')
        
        logger.info(f"📨 Chat request - User: {current_user.username}, ConvID: {conversation_id}, Prompt: {prompt[:50]}...")
        
        if not prompt:
            return jsonify({'error': 'No prompt provided'}), 400
        
        # Check tokens
        if current_user.tokens <= 0:
            return jsonify({'error': 'Insufficient tokens. Please get more tokens.'}), 402
        
        # Get or create conversation
        conversation = None
        if conversation_id:
            conversation = Conversation.query.filter_by(
                id=conversation_id,
                user_id=current_user.id
            ).first()
            if not conversation:
                logger.warning(f"⚠️ Conversation {conversation_id} not found, creating new one")
        
        if not conversation:
            conversation = Conversation(
                user_id=current_user.id,
                title=prompt[:50] + ('...' if len(prompt) > 50 else '')
            )
            db.session.add(conversation)
            db.session.flush()  # Get the ID without committing
            logger.info(f"📝 Created new conversation {conversation.id}")
        
        # Save user message IMMEDIATELY
        user_message = Message(
            conversation_id=conversation.id,
            role='user',
            content=prompt
        )
        db.session.add(user_message)
        db.session.commit()
        logger.info(f"💾 Saved user message for conversation {conversation.id}")
        
        # Get Ollama context
        ollama_context = conversation_contexts.get(f"{current_user.id}_{conversation.id}", [])
        
        # Prepare Ollama request
        ollama_payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": True
        }
        
        if ollama_context and isinstance(ollama_context, list) and len(ollama_context) > 0:
            ollama_payload["context"] = ollama_context
        
        logger.info(f"🚀 Sending to Ollama: {prompt[:50]}...")
        
        def generate():
            chunk_count = 0
            full_response = ""
            new_context = []
            
            try:
                # Make request to Ollama
                response = requests.post(
                    f"{OLLAMA_API_URL}/generate",
                    json=ollama_payload,
                    stream=True,
                    timeout=120
                )
                
                logger.info(f"📥 Ollama response status: {response.status_code}")
                
                if response.status_code != 200:
                    error_msg = f"Ollama error: {response.text}"
                    logger.error(f"❌ {error_msg}")
                    yield f"data: {json.dumps({'error': error_msg})}\n\n"
                    return
                
                for line in response.iter_lines():
                    if line:
                        chunk_count += 1
                        try:
                            json_response = json.loads(line)
                            
                            if 'context' in json_response:
                                new_context = json_response['context']
                            
                            if 'response' in json_response:
                                text_chunk = json_response['response']
                                full_response += text_chunk
                                yield f"data: {json.dumps({'text': text_chunk, 'done': json_response.get('done', False)})}\n\n"
                            
                            if json_response.get('done', False):
                                processing_time = time.time() - start_time
                                token_cost = calculate_token_cost(
                                    len(prompt), len(full_response), processing_time
                                )
                                
                                logger.info(f"✅ Generation complete - {len(full_response)} chars, {token_cost} tokens")
                                
                                # Use a new session to update database (to avoid session conflicts)
                                from models import db as models_db
                                
                                # Update user tokens
                                user = db.session.get(User, current_user.id)
                                if user:
                                    user.tokens -= token_cost
                                    user.total_tokens_used = (user.total_tokens_used or 0) + token_cost
                                    user.total_requests = (user.total_requests or 0) + 1
                                    logger.info(f"💰 Updated tokens: {user.tokens} remaining")
                                
                                # Record transaction
                                transaction = TokenTransaction(
                                    user_id=current_user.id,
                                    amount=-token_cost,
                                    transaction_type='usage',
                                    description=f'Chat completion',
                                    tokens_processed=chunk_count,
                                    processing_time=processing_time
                                )
                                db.session.add(transaction)
                                
                                # Save assistant message
                                assistant_message = Message(
                                    conversation_id=conversation.id,
                                    role='assistant',
                                    content=full_response,
                                    tokens_used=token_cost
                                )
                                db.session.add(assistant_message)
                                
                                # Update conversation
                                conv = db.session.get(Conversation, conversation.id)
                                if conv:
                                    conv.updated_at = datetime.utcnow()
                                    if conv.title == 'New Conversation':
                                        conv.title = prompt[:50] + ('...' if len(prompt) > 50 else '')
                                
                                db.session.commit()
                                logger.info(f"💾 Saved assistant message and updated tokens")
                                
                                # Save context for next message
                                if new_context:
                                    conversation_contexts[f"{current_user.id}_{conversation.id}"] = new_context
                                
                                # Send final update
                                final_data = {
                                    'done': True,
                                    'tokens_used': token_cost,
                                    'tokens_remaining': user.tokens if user else 0,
                                    'conversation_id': conversation.id
                                }
                                yield f"data: {json.dumps(final_data)}\n\n"
                                
                        except json.JSONDecodeError as e:
                            logger.debug(f"JSON decode error: {e}")
                            continue
                            
            except Exception as e:
                logger.error(f"❌ Streaming error: {e}", exc_info=True)
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
        logger.error(f"❌ Chat error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/sync', methods=['POST'])
@login_required
def chat_sync():
    """Synchronous chat endpoint - RELIABLE FALLBACK"""
    start_time = time.time()
    
    try:
        data = request.json
        prompt = data.get('prompt', '')
        conversation_id = data.get('conversation_id')
        
        logger.info(f"📨 Sync chat - User: {current_user.username}, ConvID: {conversation_id}")
        
        if not prompt:
            return jsonify({'error': 'No prompt provided'}), 400
        
        if current_user.tokens <= 0:
            return jsonify({'error': 'Insufficient tokens'}), 402
        
        # Get or create conversation
        conversation = None
        if conversation_id:
            conversation = Conversation.query.filter_by(
                id=conversation_id,
                user_id=current_user.id
            ).first()
        
        if not conversation:
            conversation = Conversation(
                user_id=current_user.id,
                title=prompt[:50] + ('...' if len(prompt) > 50 else '')
            )
            db.session.add(conversation)
            db.session.flush()
        
        # Save user message
        user_message = Message(
            conversation_id=conversation.id,
            role='user',
            content=prompt
        )
        db.session.add(user_message)
        db.session.commit()
        logger.info(f"💾 Saved user message")
        
        # Get Ollama context
        ollama_context = conversation_contexts.get(f"{current_user.id}_{conversation.id}", [])
        
        # Make non-streaming request
        ollama_payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False
        }
        
        if ollama_context:
            ollama_payload["context"] = ollama_context
        
        logger.info(f"🚀 Sending sync request to Ollama...")
        
        response = requests.post(
            f"{OLLAMA_API_URL}/generate",
            json=ollama_payload,
            timeout=120
        )
        
        if response.status_code != 200:
            logger.error(f"❌ Ollama error: {response.text}")
            return jsonify({'error': f'Ollama error: {response.text}'}), 500
        
        result = response.json()
        full_response = result.get('response', '')
        new_context = result.get('context', [])
        
        processing_time = time.time() - start_time
        token_cost = calculate_token_cost(len(prompt), len(full_response), processing_time)
        
        logger.info(f"✅ Sync complete - {len(full_response)} chars, {token_cost} tokens")
        
        # Update user tokens
        user = db.session.get(User, current_user.id)
        user.tokens -= token_cost
        user.total_tokens_used = (user.total_tokens_used or 0) + token_cost
        user.total_requests = (user.total_requests or 0) + 1
        
        # Record transaction
        transaction = TokenTransaction(
            user_id=current_user.id,
            amount=-token_cost,
            transaction_type='usage',
            description='Chat completion (sync)',
            tokens_processed=len(full_response.split()),
            processing_time=processing_time
        )
        db.session.add(transaction)
        
        # Save assistant message
        assistant_message = Message(
            conversation_id=conversation.id,
            role='assistant',
            content=full_response,
            tokens_used=token_cost
        )
        db.session.add(assistant_message)
        
        # Update conversation
        conversation.updated_at = datetime.utcnow()
        if conversation.title == 'New Conversation':
            conversation.title = prompt[:50] + ('...' if len(prompt) > 50 else '')
        
        db.session.commit()
        logger.info(f"💾 Saved assistant message and updated tokens: {user.tokens} remaining")
        
        # Save context
        if new_context:
            conversation_contexts[f"{current_user.id}_{conversation.id}"] = new_context
        
        return jsonify({
            'response': full_response,
            'tokens_used': token_cost,
            'tokens_remaining': user.tokens,
            'conversation_id': conversation.id
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Sync chat error: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'model': MODEL_NAME,
        'authenticated': current_user.is_authenticated
    })

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Starting Llama Chat Backend")
    print(f"📡 API: http://localhost:5000/api")
    print(f"🎯 Model: {MODEL_NAME}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)