from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from models import db, User, TokenTransaction
from datetime import datetime
import re

auth_bp = Blueprint('auth', __name__)
bcrypt = Bcrypt()

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def calculate_token_cost(prompt_length, response_length, processing_time):
    """
    Calculate token cost based on usage.
    More expensive for longer prompts, responses, and processing time.
    """
    # Base cost
    base_cost = 1
    
    # Input tokens cost (roughly 4 chars = 1 token)
    input_tokens = max(1, prompt_length // 4)
    
    # Output tokens cost
    output_tokens = max(1, response_length // 4)
    
    # Processing time factor (per second)
    time_factor = max(1, int(processing_time))
    
    # Calculate total cost
    # Input: 1 token per input token
    # Output: 2 tokens per output token
    # Time: 5 tokens per second
    total_cost = input_tokens * 1 + output_tokens * 2 + time_factor * 5
    
    return int(total_cost)

@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        # Validation
        if not username or not email or not password:
            return jsonify({'error': 'All fields are required'}), 400
        
        if len(username) < 3:
            return jsonify({'error': 'Username must be at least 3 characters'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already taken'}), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        # Create user
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            tokens=1000  # Starting bonus
        )
        
        db.session.add(user)
        
        # Add welcome bonus transaction
        welcome_transaction = TokenTransaction(
            user=user,
            amount=1000,
            transaction_type='bonus',
            description='Welcome bonus'
        )
        db.session.add(welcome_transaction)
        
        db.session.commit()
        
        # Log in the user
        login_user(user)
        
        return jsonify({
            'message': 'Registration successful',
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
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
        
        # Find user by username or email
        user = User.query.filter(
            (User.username == username) | (User.email == username.lower())
        ).first()
        
        if not user or not bcrypt.check_password_hash(user.password_hash, password):
            return jsonify({'error': 'Invalid username or password'}), 401
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Log in the user
        login_user(user)
        
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Login failed: {str(e)}'}), 500

@auth_bp.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    """Logout user"""
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
        amount = data.get('amount', 500)  # Default 500 tokens
        
        # Update user tokens
        current_user.tokens += amount
        
        # Record transaction
        transaction = TokenTransaction(
            user=current_user,
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
        return jsonify({'error': f'Failed to add tokens: {str(e)}'}), 500

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