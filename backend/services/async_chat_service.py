from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Conversation, Message, User, TokenTransaction
from database import async_session_factory
from datetime import datetime

class AsyncChatService:
    @staticmethod
    async def get_conversations(user_id: int):
        """Async get all conversations"""
        async with async_session_factory() as session:
            result = await session.execute(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .where(Conversation.is_active == True)
                .order_by(Conversation.updated_at.desc())
            )
            return result.scalars().all()
    
    @staticmethod
    async def create_conversation(user_id: int, title: str = 'New Conversation'):
        """Async create conversation"""
        async with async_session_factory() as session:
            conversation = Conversation(
                user_id=user_id,
                title=title
            )
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            return conversation
    
    @staticmethod
    async def get_conversation(conversation_id: int, user_id: int):
        """Async get conversation with messages"""
        async with async_session_factory() as session:
            result = await session.execute(
                select(Conversation)
                .where(Conversation.id == conversation_id)
                .where(Conversation.user_id == user_id)
            )
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                return None, None
            
            result = await session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )
            messages = result.scalars().all()
            
            return conversation, messages
    
    @staticmethod
    async def save_user_message(conversation_id: int, user_id: int, content: str):
        """Async save user message"""
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
                    title=content[:50] + ('...' if len(content) > 50 else '')
                )
                session.add(conversation)
                await session.flush()
            
            message = Message(
                conversation_id=conversation.id,
                role='user',
                content=content
            )
            session.add(message)
            await session.commit()
            await session.refresh(conversation)
            
            return conversation, message
    
    @staticmethod
    async def save_assistant_message(conversation_id: int, content: str, tokens_used: int):
        """Async save assistant message"""
        async with async_session_factory() as session:
            message = Message(
                conversation_id=conversation_id,
                role='assistant',
                content=content,
                tokens_used=tokens_used
            )
            session.add(message)
            
            # Update conversation timestamp
            result = await session.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if conversation:
                conversation.updated_at = datetime.utcnow()
            
            await session.commit()
            return message
    
    @staticmethod
    async def deduct_tokens(user_id: int, amount: int, description: str, 
                           tokens_processed: int = 0, processing_time: float = 0):
        """Async deduct tokens"""
        async with async_session_factory() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
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
            session.add(transaction)
            await session.commit()
            await session.refresh(user)
            
            return user
    
    @staticmethod
    async def delete_conversation(conversation_id: int, user_id: int):
        """Async soft delete conversation"""
        async with async_session_factory() as session:
            result = await session.execute(
                select(Conversation)
                .where(Conversation.id == conversation_id)
                .where(Conversation.user_id == user_id)
            )
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                raise ValueError('Conversation not found')
            
            conversation.is_active = False
            await session.commit()