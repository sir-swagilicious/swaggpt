from flask import Blueprint, request, jsonify
from services.auth_service import AuthService
from models import User, TokenTransaction
from database import async_session_factory
from sqlalchemy import select
from functools import wraps
import asyncio

auth_bp = Blueprint('auth', __name__)

# Use the same event loop pattern
_loop = asyncio.new_event_loop()

def _run_async(coro):
    """Run coroutine in persistent loop"""
    return _loop.run_until_complete(coro)

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

@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.json
        user = AuthService.register_user(
            username=data.get('username', '').strip(),
            email=data.get('email', '').strip().lower(),
            password=data.get('password', '')
        )
        
        # user is now a real User object, not a coroutine
        access_token = AuthService.create_access_token(user.id, user.username)
        refresh_token = AuthService.create_refresh_token(user.id)
        AuthService.store_refresh_token(user.id, refresh_token)
        
        return jsonify({
            'message': 'Registration successful',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'bearer'
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        user = AuthService.login_user(username, password)
        
        # user is now a real User object, not a coroutine
        access_token = AuthService.create_access_token(user.id, user.username)
        refresh_token = AuthService.create_refresh_token(user.id)
        AuthService.store_refresh_token(user.id, refresh_token)
        
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'bearer'
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Login failed: {str(e)}'}), 500

@auth_bp.route('/api/auth/logout', methods=['POST'])
@jwt_required
def logout():
    """Logout user"""
    AuthService.revoke_refresh_token(request.user_id)
    return jsonify({'message': 'Logout successful'}), 200

@auth_bp.route('/api/auth/user', methods=['GET'])
@jwt_required
def get_user():
    """Get current user info"""
    user = AuthService.get_user_by_id(request.user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'user': user.to_dict()}), 200

@auth_bp.route('/api/auth/tokens/add', methods=['POST'])
@jwt_required
def add_tokens():
    """Add tokens to user"""
    try:
        data = request.json
        amount = data.get('amount', 500)
        
        async def _add():
            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.id == request.user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    return None
                
                user.tokens += amount
                
                transaction = TokenTransaction(
                    user_id=request.user_id,
                    amount=amount,
                    transaction_type='bonus',
                    description='Free token refill'
                )
                session.add(transaction)
                await session.commit()
                await session.refresh(user)
                
                return user
        
        user = _run_async(_add())
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'message': f'Added {amount} tokens',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500