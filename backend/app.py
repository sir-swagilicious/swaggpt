from flask import Flask, jsonify
from flask_cors import CORS
from database import init_db
import asyncio
import logging
import sys
import os

app = Flask(__name__)

# Basic config
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

# Configure CORS
CORS(app, 
     supports_credentials=True,
     origins=["http://localhost:8000", "http://127.0.0.1:8000"],
     allow_headers=["Content-Type", "Authorization", "X-Async-Mode"],
     methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"])

# Import and register blueprints AFTER app is created
from controllers.auth_controller import auth_bp
from controllers.async_chat_controller import async_chat_bp

app.register_blueprint(auth_bp)
app.register_blueprint(async_chat_bp)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('backend_debug.log')
    ]
)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:8000')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Async-Mode')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'model': os.environ.get('MODEL_NAME', 'llama3.1:8b'),
        'async': True
    })

# Initialize database
with app.app_context():
    asyncio.run(init_db())

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Starting Llama Chat Backend (ASYNC)")
    print(f"📡 API: http://localhost:5000/api")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)