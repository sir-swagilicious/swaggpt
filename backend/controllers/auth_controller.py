from flask import Blueprint, request, jsonify
from services.auth_service import AuthService
from models import db, TokenTransaction, User
from config import Config
from redis_client import redis_client
from datetime import datetime
import secrets
import json
from functools import wraps

auth_bp = Blueprint('auth', __name__)

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
    """Register a new user - returns JWT tokens"""
    try:
        data = request.json
        user = AuthService.register_user(
            username=data.get('username', '').strip(),
            email=data.get('email', '').strip().lower(),
            password=data.get('password', '')
        )
        
        # Create tokens
        access_token = AuthService.create_access_token(user.id, user.username)
        refresh_token = AuthService.create_refresh_token(user.id)
        
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
        db.session.rollback()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """Login user - returns JWT tokens"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        user = AuthService.login_user(
            username_or_email=username,
            password=password
        )
        
        # Create tokens
        access_token = AuthService.create_access_token(user.id, user.username)
        refresh_token = AuthService.create_refresh_token(user.id)
        
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
        return jsonify({'error': f'Login failed: {str(e)}'}), 500

@auth_bp.route('/api/auth/refresh', methods=['POST'])
def refresh_token():
    """Refresh access token"""
    try:
        data = request.json
        refresh_token = data.get('refresh_token')
        
        if not refresh_token:
            return jsonify({'error': 'Refresh token required'}), 400
        
        new_access_token = AuthService.refresh_access_token(refresh_token)
        
        return jsonify({
            'access_token': new_access_token,
            'token_type': 'bearer'
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 401

@auth_bp.route('/api/auth/logout', methods=['POST'])
@jwt_required
def logout():
    """Logout user - revoke refresh token"""
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
    """Add free tokens to user account"""
    try:
        data = request.json
        amount = data.get('amount', 500)
        
        user = AuthService.get_user_by_id(request.user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user.tokens += amount
        
        transaction = TokenTransaction(
            user_id=request.user_id,
            amount=amount,
            transaction_type='bonus',
            description='Free token refill'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'message': f'Added {amount} tokens',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/api/auth/transactions', methods=['GET'])
@jwt_required
def get_transactions():
    """Get user's transaction history"""
    transactions = TokenTransaction.query.filter_by(
        user_id=request.user_id
    ).order_by(TokenTransaction.created_at.desc()).limit(50).all()
    
    return jsonify({
        'transactions': [t.to_dict() for t in transactions]
    }), 200

@auth_bp.route('/api/auth/github', methods=['GET'])
def github_login():
    """Initiate GitHub OAuth"""
    state = secrets.token_hex(16)
    redis_client.store_oauth_state(state)
    
    github_url = "https://github.com/login/oauth/authorize"
    github_url += f"?client_id={Config.GITHUB_CLIENT_ID}"
    github_url += "&redirect_uri=http://localhost:5000/api/auth/github/callback"
    github_url += f"&state={state}"
    github_url += "&scope=user:email"
    
    return jsonify({'url': github_url}), 200

@auth_bp.route('/api/auth/github/callback', methods=['GET'])
def github_callback():
    """Handle GitHub OAuth callback"""
    try:
        code = request.args.get('code')
        state = request.args.get('state')
        
        if not code or not state:
            return jsonify({'error': 'Missing code or state'}), 400
        
        user = AuthService.github_oauth_callback(code, state)
        
        # Create tokens
        access_token = AuthService.create_access_token(user.id, user.username)
        refresh_token = AuthService.create_refresh_token(user.id)
        
        return jsonify({
            'message': 'GitHub login successful',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'bearer'
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'OAuth failed'}), 500