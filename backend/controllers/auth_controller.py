from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from services.auth_service import AuthService
from services.chat_service import ChatService
from models import db, TokenTransaction
from config import Config
from redis_client import redis_client
import secrets

auth_bp = Blueprint('auth', __name__)

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
        
        login_user(user)
        
        return jsonify({
            'message': 'Registration successful',
            'user': user.to_dict()
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Registration failed'}), 500

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.json
        user = AuthService.login_user(
            username_or_email=data.get('username', '').strip(),
            password=data.get('password', '')
        )
        
        login_user(user)
        
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict()
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': 'Login failed'}), 500

@auth_bp.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    """Logout user"""
    AuthService.logout_user(current_user.id)
    logout_user()
    return jsonify({'message': 'Logout successful'}), 200

@auth_bp.route('/api/auth/user', methods=['GET'])
@login_required
def get_user():
    """Get current user info"""
    return jsonify({'user': current_user.to_dict()}), 200

@auth_bp.route('/api/auth/tokens/add', methods=['POST'])
@login_required
def add_tokens():
    """Add free tokens to user account"""
    try:
        data = request.json
        amount = data.get('amount', 500)
        
        current_user.tokens += amount
        
        transaction = TokenTransaction(
            user_id=current_user.id,
            amount=amount,
            transaction_type='bonus',
            description='Free token refill'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'message': f'Added {amount} tokens',
            'user': current_user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/api/auth/transactions', methods=['GET'])
@login_required
def get_transactions():
    """Get user's transaction history"""
    transactions = TokenTransaction.query.filter_by(
        user_id=current_user.id
    ).order_by(TokenTransaction.created_at.desc()).limit(50).all()
    
    return jsonify({
        'transactions': [t.to_dict() for t in transactions]
    }), 200

@auth_bp.route('/api/auth/github', methods=['GET'])
def github_login():
    """Initiate GitHub OAuth"""
    state = secrets.token_hex(16)
    redis_client.store_oauth_state(state)
    
    github_url = f"https://github.com/login/oauth/authorize"
    github_url += f"?client_id={Config.GITHUB_CLIENT_ID}"
    github_url += f"&redirect_uri=http://localhost:5000/api/auth/github/callback"
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
        login_user(user)
        
        # Redirect to frontend with success
        return jsonify({
            'message': 'GitHub login successful',
            'user': user.to_dict()
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'OAuth failed'}), 500