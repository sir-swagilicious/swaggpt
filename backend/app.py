from flask import Flask, jsonify
from flask_cors import CORS
from models import db
from config import Config
from controllers.auth_controller import auth_bp
from controllers.chat_controller import chat_bp
from redis_client import redis_client
import logging
import sys

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)

# Configure CORS
CORS(app, 
     supports_credentials=True,
     origins=["http://localhost:8000", "http://127.0.0.1:8000"],
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"])

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)

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

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:8000')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'model': Config.MODEL_NAME
    })

# Create tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Starting Llama Chat Backend")
    print(f"📡 API: http://localhost:5000/api")
    print(f"🎯 Model: {Config.MODEL_NAME}")
    print(f"🔐 Auth: JWT + Redis")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)