from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import User, TokenTransaction
from database import async_session_factory
from flask_bcrypt import Bcrypt
from redis_client import async_redis_client
from config import Config
from datetime import datetime, timedelta
import jwt
import re
import secrets

bcrypt = Bcrypt()

class AsyncAuthService:
    @staticmethod
    def validate_email(email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    async def register_user(username: str, email: str, password: str):
        """Async user registration"""
        if not username or not email or not password:
            raise ValueError('All fields are required')
        
        if len(username) < 3:
            raise ValueError('Username must be at least 3 characters')
        
        if len(password) < 6:
            raise ValueError('Password must be at least 6 characters')
        
        if not AsyncAuthService.validate_email(email):
            raise ValueError('Invalid email format')
        
        async with async_session_factory() as session:
            # Check existing user
            result = await session.execute(
                select(User).where(User.username == username)
            )
            if result.scalar_one_or_none():
                raise ValueError('Username already taken')
            
            result = await session.execute(
                select(User).where(User.email == email)
            )
            if result.scalar_one_or_none():
                raise ValueError('Email already registered')
            
            # Create user
            password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                tokens=1000
            )
            session.add(user)
            await session.flush()
            
            # Add welcome bonus
            transaction = TokenTransaction(
                user_id=user.id,
                amount=1000,
                transaction_type='bonus',
                description='Welcome bonus'
            )
            session.add(transaction)
            await session.commit()
            
            # Cache in Redis async
            await async_redis_client.set_session(user.id, {
                'user_id': user.id,
                'username': user.username,
                'created_at': datetime.utcnow().isoformat()
            })
            
            return user
    
    @staticmethod
    async def login_user(username_or_email: str, password: str):
        """Async user login"""
        async with async_session_factory() as session:
            # Find user
            result = await session.execute(
                select(User).where(
                    (User.username == username_or_email) | 
                    (User.email == username_or_email.lower())
                )
            )
            user = result.scalar_one_or_none()
            
            if not user or not bcrypt.check_password_hash(user.password_hash, password):
                raise ValueError('Invalid username or password')
            
            # Update last login
            user.last_login = datetime.utcnow()
            await session.commit()
            
            # Cache session
            await async_redis_client.set_session(user.id, {
                'user_id': user.id,
                'username': user.username,
                'login_time': datetime.utcnow().isoformat()
            })
            
            return user
    
    @staticmethod
    async def get_user_by_id(user_id: int):
        """Async get user by ID"""
        # Try Redis first
        cached = await async_redis_client.get_session(user_id)
        if cached:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    return user
        
        async with async_session_factory() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()
    
    @staticmethod
    def create_access_token(user_id: int, username: str):
        """Create JWT access token (sync - no IO needed)"""
        payload = {
            'user_id': user_id,
            'username': username,
            'type': 'access',
            'exp': datetime.utcnow() + timedelta(hours=1),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')
    
    @staticmethod
    def create_refresh_token(user_id: int):
        """Create JWT refresh token"""
        payload = {
            'user_id': user_id,
            'type': 'refresh',
            'exp': datetime.utcnow() + timedelta(days=30),
            'iat': datetime.utcnow()
        }
        token = jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')
        return token
    
    @staticmethod
    async def store_refresh_token(user_id: int, token: str):
        """Store refresh token in Redis async"""
        await async_redis_client.client.setex(
            f"refresh_token:{user_id}",
            30 * 24 * 3600,
            token
        )
    
    @staticmethod
    def verify_token(token: str, token_type: str = 'access'):
        """Verify JWT token (sync - no IO needed)"""
        try:
            payload = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
            
            if payload.get('type') != token_type:
                raise ValueError('Invalid token type')
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise ValueError('Token expired')
        except jwt.InvalidTokenError:
            raise ValueError('Invalid token')
    
    @staticmethod
    async def verify_refresh_token(token: str):
        """Verify refresh token with Redis check (async)"""
        payload = AsyncAuthService.verify_token(token, 'refresh')
        
        stored_token = await async_redis_client.client.get(
            f"refresh_token:{payload['user_id']}"
        )
        if not stored_token or stored_token.decode() != token:
            raise ValueError('Refresh token revoked')
        
        return payload