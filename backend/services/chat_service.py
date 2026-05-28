from models import db, Conversation, Message, User, TokenTransaction
from datetime import datetime
import hashlib
import json
from redis_client import redis_client

class ChatService:
    @staticmethod
    def create_conversation(user_id, title='New Conversation'):
        """Create a new conversation"""
        conversation = Conversation(
            user_id=user_id,
            title=title
        )
        db.session.add(conversation)
        db.session.commit()
        return conversation
    
    @staticmethod
    def get_conversations(user_id):
        """Get all active conversations for user"""
        return Conversation.query.filter_by(
            user_id=user_id,
            is_active=True
        ).order_by(Conversation.updated_at.desc()).all()
    
    @staticmethod
    def get_conversation(conversation_id, user_id):
        """Get specific conversation with messages"""
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            user_id=user_id
        ).first()
        
        if not conversation:
            return None, None
        
        messages = Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(Message.created_at).all()
        
        return conversation, messages
    
    @staticmethod
    def delete_conversation(conversation_id, user_id):
        """Soft delete a conversation"""
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            user_id=user_id
        ).first()
        
        if not conversation:
            raise ValueError('Conversation not found')
        
        conversation.is_active = False
        db.session.commit()
    
    @staticmethod
    def save_user_message(conversation_id, user_id, content):
        """Save user message and get/create conversation"""
        conversation = None
        
        if conversation_id:
            conversation = Conversation.query.filter_by(
                id=conversation_id,
                user_id=user_id
            ).first()
        
        if not conversation:
            conversation = Conversation(
                user_id=user_id,
                title=content[:50] + ('...' if len(content) > 50 else '')
            )
            db.session.add(conversation)
            db.session.flush()
        
        # Save user message
        message = Message(
            conversation_id=conversation.id,
            role='user',
            content=content
        )
        db.session.add(message)
        db.session.commit()
        
        return conversation, message
    
    @staticmethod
    def save_assistant_message(conversation_id, content, tokens_used):
        """Save assistant response"""
        message = Message(
            conversation_id=conversation_id,
            role='assistant',
            content=content,
            tokens_used=tokens_used
        )
        db.session.add(message)
        
        # Update conversation timestamp
        conversation = Conversation.query.get(conversation_id)
        if conversation:
            conversation.updated_at = datetime.utcnow()
            if conversation.title == 'New Conversation' and content:
                conversation.title = content[:50] + ('...' if len(content) > 50 else '')
        
        db.session.commit()
        return message
    
    @staticmethod
    def deduct_tokens(user_id, amount, description, tokens_processed=0, processing_time=0):
        """Deduct tokens from user and record transaction"""
        user = User.query.get(user_id)
        
        if not user:
            raise ValueError('User not found')
        
        if user.tokens < amount:
            raise ValueError('Insufficient tokens')
        
        user.tokens -= amount
        user.total_tokens_used = (user.total_tokens_used or 0) + amount
        user.total_requests = (user.total_requests or 0) + 1
        
        transaction = TokenTransaction(
            user_id=user_id,
            amount=-amount,
            transaction_type='usage',
            description=description,
            tokens_processed=tokens_processed,
            processing_time=processing_time
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return user