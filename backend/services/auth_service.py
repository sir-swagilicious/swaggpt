from models import db, User, TokenTransaction
from flask_bcrypt import Bcrypt
from redis_client import redis_client
from config import Config
from datetime import datetime, timedelta  # <-- ADD timedelta here
import jwt
import re
import secrets
import requests

bcrypt = Bcrypt()

class AuthService:
    @staticmethod
    def validate_email(email):
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def register_user(username, email, password):
        """Register a new user"""
        # Validation
        if not username or not email or not password:
            raise ValueError('All fields are required')
        
        if len(username) < 3:
            raise ValueError('Username must be at least 3 characters')
        
        if len(password) < 6:
            raise ValueError('Password must be at least 6 characters')
        
        if not AuthService.validate_email(email):
            raise ValueError('Invalid email format')
        
        # Check existing user
        if User.query.filter_by(username=username).first():
            raise ValueError('Username already taken')
        
        if User.query.filter_by(email=email).first():
            raise ValueError('Email already registered')
        
        # Create user
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            tokens=1000
        )
        
        db.session.add(user)
        db.session.flush()
        
        # Add welcome bonus transaction
        transaction = TokenTransaction(
            user_id=user.id,
            amount=1000,
            transaction_type='bonus',
            description='Welcome bonus'
        )
        db.session.add(transaction)
        db.session.commit()
        
        # Create Redis session
        redis_client.set_session(user.id, {
            'user_id': user.id,
            'username': user.username,
            'created_at': datetime.utcnow().isoformat()
        })
        
        return user
    
    @staticmethod
    def login_user(username_or_email, password):
        """Authenticate and login user"""
        user = User.query.filter(
            (User.username == username_or_email) | 
            (User.email == username_or_email.lower())
        ).first()
        
        if not user or not bcrypt.check_password_hash(user.password_hash, password):
            raise ValueError('Invalid username or password')
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Create Redis session
        redis_client.set_session(user.id, {
            'user_id': user.id,
            'username': user.username,
            'login_time': datetime.utcnow().isoformat()
        })
        
        return user
    
    @staticmethod
    def logout_user(user_id):
        """Logout user and clear session"""
        redis_client.delete_session(user_id)
    
    @staticmethod
    def get_user_by_id(user_id):
        """Get user by ID with Redis caching"""
        # Try Redis first
        cached = redis_client.get_session(user_id)
        if cached:
            user = User.query.get(user_id)
            if user:
                return user
        
        return User.query.get(user_id)
    
    @staticmethod
    def create_access_token(user_id, username):
        """Create JWT access token"""
        payload = {
            'user_id': user_id,
            'username': username,
            'type': 'access',
            'exp': datetime.utcnow() + timedelta(hours=1),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')
    
    @staticmethod
    def create_refresh_token(user_id):
        """Create JWT refresh token"""
        payload = {
            'user_id': user_id,
            'type': 'refresh',
            'exp': datetime.utcnow() + timedelta(days=30),
            'iat': datetime.utcnow()
        }
        token = jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')
        
        # Store refresh token in Redis with 30-day TTL
        redis_client.client.setex(
            f"refresh_token:{user_id}",
            30 * 24 * 3600,
            token
        )
        
        return token
    
    @staticmethod
    def verify_token(token, token_type='access'):
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
            
            if payload.get('type') != token_type:
                raise ValueError('Invalid token type')
            
            # Check if refresh token is in Redis
            if token_type == 'refresh':
                stored_token = redis_client.client.get(
                    f"refresh_token:{payload['user_id']}"
                )
                if not stored_token or stored_token != token:
                    raise ValueError('Refresh token revoked')
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise ValueError('Token expired')
        except jwt.InvalidTokenError:
            raise ValueError('Invalid token')
    
    @staticmethod
    def refresh_access_token(refresh_token):
        """Get new access token using refresh token"""
        payload = AuthService.verify_token(refresh_token, 'refresh')
        
        user = User.query.get(payload['user_id'])
        if not user:
            raise ValueError('User not found')
        
        return AuthService.create_access_token(user.id, user.username)
    
    @staticmethod
    def revoke_refresh_token(user_id):
        """Revoke refresh token (logout)"""
        redis_client.client.delete(f"refresh_token:{user_id}")
    
    @staticmethod
    def github_oauth_callback(code, state):
        """Handle GitHub OAuth callback"""
        # Validate state
        if not redis_client.validate_oauth_state(state):
            raise ValueError('Invalid OAuth state')
        
        # Exchange code for access token
        token_response = requests.post(
            'https://github.com/login/oauth/access_token',
            data={
                'client_id': Config.GITHUB_CLIENT_ID,
                'client_secret': Config.GITHUB_CLIENT_SECRET,
                'code': code
            },
            headers={'Accept': 'application/json'}
        )
        
        if token_response.status_code != 200:
            raise ValueError('Failed to get GitHub token')
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            raise ValueError('No access token received')
        
        # Get user info from GitHub
        user_response = requests.get(
            'https://api.github.com/user',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        if user_response.status_code != 200:
            raise ValueError('Failed to get GitHub user info')
        
        github_user = user_response.json()
        github_id = str(github_user.get('id'))
        email = github_user.get('email', f'{github_id}@github.com')
        username = github_user.get('login', f'github_user_{github_id}')
        
        # Find or create user
        user = User.query.filter_by(email=email).first()
        
        if not user:
            user = User(
                username=username,
                email=email,
                password_hash=bcrypt.generate_password_hash(secrets.token_hex(16)).decode('utf-8'),
                tokens=1000
            )
            db.session.add(user)
            db.session.commit()
        
        # Create Redis session
        redis_client.set_session(user.id, {
            'user_id': user.id,
            'username': user.username,
            'github_id': github_id,
            'login_time': datetime.utcnow().isoformat()
        })
        
        return user