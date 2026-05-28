Llama Chat - Local AI Chat Application
A full-stack chat application that provides a ChatGPT-like interface for interacting with your local Llama 3.1 model through Ollama. Features user authentication, token management, conversation history, and fun mini-games to earn tokens.


🏗️ Architecture
┌─────────────────────────────────────────────────────────┐
│                    Your Web Browser                      │
│                  http://localhost:8000                   │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Frontend Server (Node.js)                   │
│                    Port 8000                             │
│  Serves static HTML/CSS/JS files                        │
└─────────────────────┬───────────────────────────────────┘
                      │ API Calls
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Backend Server (Flask/Python)               │
│                    Port 5000                             │
│  • User Authentication                                  │
│  • Token Management                                     │
│  • Conversation Storage                                 │
│  • Request Routing to Ollama                            │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Ollama AI Server                            │
│                    Port 11434                            │
│  Running Llama 3.1 8B model                            │
└─────────────────────────────────────────────────────────┘
✨ Features
Core Features
💬 Real-time Chat: Stream responses from Llama 3.1 8B model

🔐 User Authentication: Register and login system with secure password hashing

💰 Token Economy: Token-based usage system that simulates pay-per-use LLM services

📝 Conversation Management: Save, load, and switch between multiple conversations

🎨 Modern UI: Clean, responsive design with dark/light theme support

📱 Mobile Responsive: Works on desktop and mobile devices

Token System
1000 Starting Tokens: New users receive 1000 free tokens

Dynamic Pricing: Token cost calculated based on:

Input length (1 token per 4 characters)

Output length (2 tokens per 4 characters)

Processing time (5 tokens per second)

Real-time Display: Current token balance always visible

Low Token Warning: Alerts when balance drops below 100 tokens

🎮 Token Earning Games
Math Challenge (100 Tokens)
Solve a simple addition problem

Numbers between 1-50

Unlimited attempts until correct

Difficulty: Easy

Llama Chase (500 Tokens)
A llama emoji runs across your screen

Random trajectory and timing (2-4 seconds)

Click the llama before it escapes

Difficulty: Medium

Number Guessing Game (1000 Tokens)
Guess a secret number between 1-100,000

Only 4 attempts allowed

Receive only "Higher" or "Lower" hints

Exact guess wins 1000 tokens

Close guesses earn consolation prizes

Difficulty: Hard

📋 Prerequisites
Before you begin, ensure you have the following installed:

Required Software
Python 3.8+ - Download Python

Node.js 14+ - Download Node.js

Ollama - Download Ollama

System Requirements
RAM: Minimum 8GB (16GB recommended)

Storage: ~5GB for the Llama 3.1 8B model

GPU: Optional but recommended for faster responses

OS: Linux, macOS, or Windows

🚀 Installation Guide
Step 1: Install Ollama
Linux

curl -fsSL https://ollama.ai/install.sh | sh
macOS

# Download from https://ollama.ai/download
# Or use Homebrew:
brew install ollama
Windows

# Download the installer from https://ollama.ai/download
# Run the .exe file and follow the installation wizard
Step 2: Start Ollama and Download the Model
Start the Ollama service:


ollama serve
In a new terminal, download the Llama 3.1 8B model:


ollama pull llama3.1:8b
This will download approximately 4.7GB. The download time depends on your internet speed.

Verify the model is installed:


ollama list
You should see llama3.1:8b in the list.

Step 3: Clone and Setup the Project
Clone or download this repository:


git clone https://github.com/sir-swagilicious/swaggpt
cd llama-chat-app
Install Python dependencies:


cd backend
pip install -r requirements.txt
The required packages are:

Flask 3.0.0

Flask-CORS 4.0.0

Flask-SQLAlchemy 3.1.1

Flask-Login 0.6.3

Flask-Bcrypt 1.0.1

Requests 2.31.0

Install Node.js dependencies:


cd ..  # Back to project root
npm install
Step 4: Start the Application
You need to run three services (each in its own terminal):

Terminal 1: Ollama Service

ollama serve
Keep this running in the background. Ollama runs on port 11434.

Terminal 2: Backend Server

cd backend
python app.py
The Flask backend starts on port 5000. You should see:


🚀 Starting Llama Chat Backend
📡 API Endpoint: http://localhost:5000/api
💾 Ollama URL: http://localhost:11434/api
🎯 Model: llama3.1:8b
Terminal 3: Frontend Server

npm start
The Node.js frontend starts on port 8000. You should see:


🚀 Frontend server running on http://localhost:8000
Step 5: Access the Application
Open your web browser

Navigate to: http://localhost:8000

Register a new account

Start chatting!

🎯 Usage Guide
First Time Setup
Visit http://localhost:8000

Click the "Register" tab

Create an account with:

Username (3+ characters)

Email (valid format)

Password (6+ characters)

You'll receive 1000 free tokens upon registration

Chatting
Start a New Conversation: Click "➕ New Chat" in the sidebar

Type Your Message: Use the text area at the bottom

Send: Press Enter or click the send button (➤)

View Response: Watch the AI respond in real-time

Token Cost: See how many tokens each message costs

Managing Conversations
View History: All conversations appear in the left sidebar

Switch Conversations: Click any conversation to load it

Delete Conversations: Hover over a conversation and click 🗑️

Clear Chat: Click the 🗑️ button in the header to clear current chat

Earning Tokens
Click the "⚡ Get Tokens" button in the header

Choose a game:

100 Tokens: Math problem

500 Tokens: Catch the llama

1000 Tokens: Number guessing game

Complete the challenge to earn tokens

Customization
Dark Mode: Click 🌓 to toggle dark/light theme

Sidebar: Click ☰ to collapse/expand the sidebar

Mobile: The sidebar becomes a slide-out menu on small screens

🔧 Configuration
Changing the Model
Edit backend/app.py:


MODEL_NAME = "llama3.1:8b"  # Change to any model in 'ollama list'
Changing Ports
Backend port (edit backend/app.py):


app.run(host='0.0.0.0', port=5000)  # Change 5000 to desired port
Frontend port (edit server.js):


const PORT = 8000;  // Change 8000 to desired port
Important: If you change ports, also update:

CORS settings in backend/app.py

API URL in frontend/script.js

API URL in frontend/auth.js

Token Pricing
Edit backend/auth.py to modify the calculate_token_cost function:


def calculate_token_cost(prompt_length, response_length, processing_time):
    input_tokens = max(1, prompt_length // 4)
    output_tokens = max(1, response_length // 4)
    time_factor = max(1, int(processing_time))
    total_cost = input_tokens * 1 + output_tokens * 2 + time_factor * 5
    return int(total_cost)
🗄️ Database
The application uses SQLite for data storage. The database file is created automatically at backend/llama_chat.db.

Reset Database
To completely reset the application (delete all users and conversations):


cd backend
python -c "from app import app, db; app.app_context().push(); db.drop_all(); db.create_all(); print('Database reset!')"
Database Structure
users: User accounts and token balances

conversations: Chat conversations

messages: Individual messages within conversations

token_transactions: Record of all token usage and earnings

🛠️ Troubleshooting
Common Issues
"Cannot connect to Ollama"
Ensure Ollama is running: ollama serve

Check if port 11434 is accessible

Verify model is downloaded: ollama list

"Model not found" error

# Check available models
ollama list

# Pull the model if missing
ollama pull llama3.1:8b
"Failed to fetch" in frontend
Ensure all three services are running (Ollama, Backend, Frontend)

Check for port conflicts

Clear browser cache and cookies

Check browser console (F12) for detailed errors

Backend won't start
Ensure Python 3.8+ is installed

Install all dependencies: pip install -r requirements.txt

Check if port 5000 is available

Slow responses
Close other applications to free up RAM

Ensure Ollama is using GPU (check with nvidia-smi)

The first response may be slower as the model loads

Debug Mode
To run the backend in debug mode (auto-reloads on changes):


cd backend
python app.py  # Debug mode is enabled by default
Logs are written to backend/backend_debug.log for troubleshooting.

🎯 API Endpoints
Authentication
POST /api/auth/register - Register new user

POST /api/auth/login - Login user

POST /api/auth/logout - Logout user

GET /api/auth/user - Get current user info

POST /api/auth/tokens/add - Add tokens to user

Conversations
GET /api/conversations - List user's conversations

POST /api/conversations - Create new conversation

GET /api/conversations/:id - Get conversation with messages

PUT /api/conversations/:id - Update conversation title

DELETE /api/conversations/:id - Delete conversation

Chat
POST /api/chat - Streaming chat endpoint

POST /api/chat/sync - Synchronous chat endpoint

Health
GET /api/health - Health check

📁 Project Structure
text
llama-chat-app/
├── backend/
│   ├── app.py              # Main Flask application
│   ├── auth.py             # Authentication routes and token pricing
│   ├── models.py           # Database models
│   ├── requirements.txt    # Python dependencies
│   └── backend_debug.log   # Debug logs
├── frontend/
│   ├── index.html          # Main chat interface
│   ├── login.html          # Login/Register page
│   ├── styles.css          # All styles
│   ├── script.js           # Chat application logic
│   └── auth.js             # Authentication logic
├── server.js               # Node.js frontend server
├── package.json            # Node.js dependencies
└── README.md               # This file
🤝 Contributing
Feel free to submit issues and enhancement requests!

📄 License
This project is open source and available under the MIT License.

🙏 Acknowledgments
Ollama for making local LLMs accessible

Meta for the Llama 3.1 model

Flask for the Python web framework

All the open source libraries that made this project possible

DeepSeek for allowing me to vibecode this entire project

🆘 Support
If you encounter any issues:

Check the troubleshooting section above

Look at the debug logs in backend/backend_debug.log

Check browser console (F12) for frontend errors

Ensure all three services are running

