
class ChatApp {
    constructor() {
        this.apiBaseUrl = 'http://localhost:5000/api';
        this.chatMessages = document.getElementById('chat-messages');
        this.userInput = document.getElementById('user-input');
        this.sendButton = document.getElementById('send-button');
        this.toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
        this.newChatBtn = document.getElementById('new-chat-btn');
        this.themeButton = document.getElementById('toggle-theme');
        this.logoutButton = document.getElementById('logout-btn');
        this.statusIndicator = document.getElementById('connection-status');
        this.charCount = document.getElementById('char-count');
        this.tokenCount = document.getElementById('token-count');
        this.addTokensBtn = document.getElementById('add-tokens-btn');
        this.tokenWarning = document.getElementById('token-warning');
        this.sidebar = document.getElementById('sidebar');
        this.sidebarOverlay = document.getElementById('sidebar-overlay');
        this.conversationsList = document.getElementById('conversations-list');
        
        this.isProcessing = false;
        this.user = null;
        this.currentConversation = null;
        this.conversations = [];
        this.accessToken = localStorage.getItem('access_token');
        
        this.checkAuth();
        this.initializeEventListeners();
        this.loadTheme();
        this.loadConversations();
        
        console.log('✅ ChatApp initialized');
    }
    
    checkAuth() {
        const userData = localStorage.getItem('user');
        const token = localStorage.getItem('access_token');
        
        if (!userData || !token) {
            window.location.href = '/login.html';
            return;
        }
        
        this.user = JSON.parse(userData);
        this.accessToken = token;
        this.updateTokenDisplay();
    }
    
    updateTokenDisplay() {
        if (this.tokenCount) {
            this.tokenCount.textContent = this.user.tokens ? this.user.tokens.toLocaleString() : '0';
        }
        if (this.tokenWarning) {
            if (this.user.tokens < 100) {
                this.tokenWarning.style.display = 'block';
            } else {
                this.tokenWarning.style.display = 'none';
            }
        }
        if (this.user.tokens <= 0) {
            if (this.userInput) {
                this.userInput.disabled = true;
                this.userInput.placeholder = 'Out of tokens! Click "Get Tokens" to continue.';
            }
        } else {
            if (this.userInput) {
                this.userInput.disabled = false;
                this.userInput.placeholder = 'Type your message here... (Shift+Enter for new line)';
            }
        }
        this._updateSendButtonState();
    }
    
    _updateSendButtonState() {
        // Direct state update without triggering events
        if (!this.sendButton || !this.userInput) return;
        
        const hasText = this.userInput.value.trim().length > 0;
        const hasTokens = this.user && this.user.tokens > 0;
        const shouldEnable = hasText && !this.isProcessing && hasTokens;
        
        this.sendButton.disabled = !shouldEnable;
    }
    
    updateSendButton() {
        this._updateSendButtonState();
    }
    
    initializeEventListeners() {
        if (this.sendButton) {
            this.sendButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.sendMessage();
            });
        }
        
        if (this.userInput) {
            this.userInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
            
            this.userInput.addEventListener('input', () => {
                this.userInput.style.height = 'auto';
                this.userInput.style.height = this.userInput.scrollHeight + 'px';
                if (this.charCount) {
                    this.charCount.textContent = this.userInput.value.length;
                }
                this._updateSendButtonState();
            });
        }
        
        if (this.toggleSidebarBtn) {
            this.toggleSidebarBtn.addEventListener('click', () => this.toggleSidebar());
        }
        
        if (this.newChatBtn) {
            this.newChatBtn.addEventListener('click', () => this.createNewConversation());
        }
        
        if (this.themeButton) {
            this.themeButton.addEventListener('click', () => this.toggleTheme());
        }
        
        if (this.logoutButton) {
            this.logoutButton.addEventListener('click', () => this.logout());
        }
        
        if (this.addTokensBtn) {
            this.addTokensBtn.addEventListener('click', () => this.addTokens());
        }
        
        if (this.sidebarOverlay) {
            this.sidebarOverlay.addEventListener('click', () => this.toggleSidebar());
        }
    }
    
    // Helper method for authenticated API calls
    async authFetch(url, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.accessToken}`
        };
        
        if (options.headers) {
            Object.assign(headers, options.headers);
        }
        
        return fetch(url, {
            ...options,
            headers
        });
    }
    
    async loadConversations() {
        try {
            const response = await this.authFetch(`${this.apiBaseUrl}/conversations`);
            
            if (response.ok) {
                const data = await response.json();
                this.conversations = data.conversations;
                this.renderConversationsList();
            } else if (response.status === 401) {
                this.logout();
            }
        } catch (error) {
            console.error('Failed to load conversations:', error);
        }
    }
    
    renderConversationsList() {
        if (!this.conversationsList) return;
        
        this.conversationsList.innerHTML = '';
        
        if (this.conversations.length === 0) {
            this.conversationsList.innerHTML = `
                <div style="padding: 1rem; text-align: center; color: var(--text-secondary);">
                    No conversations yet
                </div>
            `;
            return;
        }
        
        this.conversations.forEach(conv => {
            const item = document.createElement('div');
            item.className = `conversation-item ${this.currentConversation?.id === conv.id ? 'active' : ''}`;
            item.onclick = () => this.loadConversation(conv.id);
            
            const date = new Date(conv.updated_at || conv.created_at);
            const dateStr = date.toLocaleDateString();
            
            item.innerHTML = `
                <div style="flex: 1; min-width: 0;">
                    <div class="conversation-title">${this.escapeHtml(conv.title)}</div>
                    <div class="conversation-date">${dateStr} · ${conv.message_count} messages</div>
                </div>
                <div class="conversation-actions">
                    <button class="conversation-action-btn" title="Delete" onclick="event.stopPropagation(); window.chatApp.deleteConversation(${conv.id})">
                        🗑️
                    </button>
                </div>
            `;
            
            this.conversationsList.appendChild(item);
        });
    }
    
    async createNewConversation() {
        try {
            const response = await this.authFetch(`${this.apiBaseUrl}/conversations`, {
                method: 'POST',
                body: JSON.stringify({ title: 'New Conversation' })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.currentConversation = data.conversation;
                await this.loadConversations();
                this.clearChatWindow();
                if (this.userInput) this.userInput.focus();
            }
        } catch (error) {
            console.error('Failed to create conversation:', error);
        }
    }
    
    async loadConversation(conversationId) {
        try {
            const response = await this.authFetch(`${this.apiBaseUrl}/conversations/${conversationId}`);
            
            if (response.ok) {
                const data = await response.json();
                this.currentConversation = data.conversation;
                this.renderConversationsList();
                this.displayMessages(data.messages);
                
                if (window.innerWidth <= 768) {
                    this.toggleSidebar();
                }
            }
        } catch (error) {
            console.error('Failed to load conversation:', error);
        }
    }
    
    displayMessages(messages) {
        if (!this.chatMessages) return;
        
        this.chatMessages.innerHTML = '';
        
        if (!messages || messages.length === 0) {
            this.chatMessages.innerHTML = `
                <div class="empty-state">
                    <h2>Start a conversation</h2>
                    <p>Send a message to begin</p>
                </div>
            `;
            return;
        }
        
        messages.forEach(msg => {
            const messageDiv = document.createElement('div');
            
            if (msg.role === 'user') {
                messageDiv.className = 'message user';
            } else if (msg.role === 'assistant') {
                messageDiv.className = 'message assistant';
            } else {
                messageDiv.className = 'message error';
            }
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.textContent = msg.content;
            
            messageDiv.appendChild(contentDiv);
            this.chatMessages.appendChild(messageDiv);
        });
        
        this.scrollToBottom();
    }
    
    async deleteConversation(conversationId) {
        if (!confirm('Delete this conversation?')) return;
        
        try {
            await this.authFetch(`${this.apiBaseUrl}/conversations/${conversationId}`, {
                method: 'DELETE'
            });
            
            if (this.currentConversation?.id === conversationId) {
                this.currentConversation = null;
                this.clearChatWindow();
            }
            await this.loadConversations();
        } catch (error) {
            console.error('Failed to delete:', error);
        }
    }
    
// In the ChatApp class, update sendMessage:

async sendMessage() {
    if (!this.userInput) return;
    
    const message = this.userInput.value.trim();
    
    if (!message || this.isProcessing || (this.user && this.user.tokens <= 0)) {
        return;
    }
    
    // Clear empty state
    const emptyState = this.chatMessages?.querySelector('.empty-state');
    if (emptyState) emptyState.remove();
    
    // Add user message to UI
    this._addMessageToUI(message, 'user');
    
    // Clear input
    this.userInput.value = '';
    this.userInput.style.height = 'auto';
    if (this.charCount) this.charCount.textContent = '0';
    this._updateSendButtonState();
    
    // Show typing indicator
    const typingIndicator = this._showTypingIndicator();
    
    try {
        this.isProcessing = true;
        this._updateSendButtonState();
        
        // Use /api/chat with async mode header
        const headers = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.accessToken}`
        };
        
        // Add async mode header if enabled
        if (this.useAsync) {
            headers['X-Async-Mode'] = 'true';
        }
        
        const response = await fetch(`${this.apiBaseUrl}/chat`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                prompt: message,
                conversation_id: this.currentConversation?.id
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Remove typing indicator
        this._removeTypingIndicator(typingIndicator);
        
        // Add assistant message
        if (data.response) {
            this._addMessageToUI(data.response, 'assistant');
        }
        
        // Update tokens
        if (data.tokens_used) {
            this.user.tokens = data.tokens_remaining;
            localStorage.setItem('user', JSON.stringify(this.user));
            this.updateTokenDisplay();
            this._showTokenCost(data.tokens_used);
        }
        
        // Update conversation
        if (data.conversation_id) {
            if (!this.currentConversation) {
                this.currentConversation = { id: data.conversation_id };
            }
            await this.loadConversations();
        }
        
    } catch (error) {
        console.error('Error:', error);
        this._removeTypingIndicator(typingIndicator);
        this._addMessageToUI(`Error: ${error.message}`, 'error');
    } finally {
        this.isProcessing = false;
        this._updateSendButtonState();
    }
}
    
    _addMessageToUI(content, type) {
        if (!this.chatMessages) return;
        
        const messageDiv = document.createElement('div');
        
        if (type === 'user') {
            messageDiv.className = 'message user';
        } else if (type === 'assistant') {
            messageDiv.className = 'message assistant';
        } else {
            messageDiv.className = 'message error';
        }
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = content;
        
        messageDiv.appendChild(contentDiv);
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    _showTypingIndicator() {
        if (!this.chatMessages) return null;
        
        const indicator = document.createElement('div');
        indicator.className = 'message assistant typing-message';
        indicator.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
        this.chatMessages.appendChild(indicator);
        this.scrollToBottom();
        
        return indicator;
    }
    
    _removeTypingIndicator(indicator) {
        if (indicator && indicator.parentNode) {
            indicator.remove();
        }
    }
    
    _showTokenCost(cost) {
        const notification = document.createElement('div');
        notification.textContent = `-${cost} tokens`;
        notification.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            background: #ff6b6b;
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            z-index: 1000;
            animation: slideIn 0.3s ease;
        `;
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 2500);
    }
    
    clearChatWindow() {
        if (!this.chatMessages) return;
        this.chatMessages.innerHTML = `
            <div class="empty-state">
                <h2>Start a conversation</h2>
                <p>Send a message to begin</p>
            </div>
        `;
    }
    
    async addTokens() {
        // Mini-game modal logic remains the same
        const modal = document.createElement('div');
        modal.className = 'token-modal';
        modal.innerHTML = `
            <div class="token-modal-content">
                <h2>🎮 Earn Free Tokens</h2>
                <p>Choose how many tokens you want to earn:</p>
                <div class="token-options">
                    <button class="token-option-btn" data-amount="100">
                        <div class="token-option-icon">➕</div>
                        <div class="token-option-amount">100 Tokens</div>
                        <div class="token-option-desc">Solve a math problem</div>
                        <div class="token-option-difficulty easy">Easy</div>
                    </button>
                    <button class="token-option-btn" data-amount="500">
                        <div class="token-option-icon">🦙</div>
                        <div class="token-option-amount">500 Tokens</div>
                        <div class="token-option-desc">Catch the running Llama</div>
                        <div class="token-option-difficulty medium">Medium</div>
                    </button>
                    <button class="token-option-btn" data-amount="1000">
                        <div class="token-option-icon">🎯</div>
                        <div class="token-option-amount">1000 Tokens</div>
                        <div class="token-option-desc">Guess the secret number</div>
                        <div class="token-option-difficulty hard">Hard</div>
                    </button>
                </div>
                <button class="token-modal-close">Cancel</button>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        modal.querySelector('.token-modal-close').addEventListener('click', () => modal.remove());
        
        modal.querySelectorAll('.token-option-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const amount = parseInt(btn.dataset.amount);
                modal.remove();
                
                switch(amount) {
                    case 100:
                        await this.mathGame();
                        break;
                    case 500:
                        await this.llamaChaseGame();
                        break;
                    case 1000:
                        await this.numberGuessGame();
                        break;
                }
            });
        });
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
    }
    
    async grantTokens(amount) {
        try {
            const response = await this.authFetch(`${this.apiBaseUrl}/auth/tokens/add`, {
                method: 'POST',
                body: JSON.stringify({ amount: amount })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.user = data.user;
                localStorage.setItem('user', JSON.stringify(data.user));
                this.updateTokenDisplay();
            }
        } catch (error) {
            console.error('Failed to grant tokens:', error);
        }
    }
    
    // Math game, Llama chase, Number guess methods remain the same...
    // (Keep your existing game methods, just make sure they use this.authFetch and this.grantTokens)
    
    async mathGame() {
        const num1 = Math.floor(Math.random() * 50) + 1;
        const num2 = Math.floor(Math.random() * 50) + 1;
        const correctAnswer = num1 + num2;
        
        const modal = document.createElement('div');
        modal.className = 'token-modal';
        modal.innerHTML = `
            <div class="token-modal-content game-modal">
                <h2>➕ Math Challenge</h2>
                <p>Solve this problem to earn <strong>100 tokens</strong>:</p>
                <div class="math-problem">
                    <span class="math-number">${num1}</span>
                    <span class="math-operator">+</span>
                    <span class="math-number">${num2}</span>
                    <span class="math-operator">=</span>
                    <span class="math-question">?</span>
                </div>
                <input type="number" class="math-input" placeholder="Your answer..." autofocus>
                <div class="math-feedback"></div>
                <div class="game-buttons">
                    <button class="math-submit-btn">Submit</button>
                    <button class="game-cancel-btn">Cancel</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        const input = modal.querySelector('.math-input');
        const feedback = modal.querySelector('.math-feedback');
        const submitBtn = modal.querySelector('.math-submit-btn');
        
        const checkAnswer = () => {
            const userAnswer = parseInt(input.value);
            if (userAnswer === correctAnswer) {
                feedback.innerHTML = '✅ Correct! You earned 100 tokens! 🎉';
                feedback.style.color = '#34c759';
                submitBtn.disabled = true;
                input.disabled = true;
                this.grantTokens(100);
                setTimeout(() => modal.remove(), 2000);
            } else {
                feedback.innerHTML = '❌ Wrong answer. Try again!';
                feedback.style.color = '#ff3b30';
                input.value = '';
                input.focus();
            }
        };
        
        submitBtn.addEventListener('click', checkAnswer);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') checkAnswer();
        });
        
        modal.querySelector('.game-cancel-btn').addEventListener('click', () => modal.remove());
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
    }

// ============ LLAMA CHASE GAME (500 tokens) ============
async llamaChaseGame() {
    const modal = document.createElement('div');
    modal.className = 'token-modal';
    modal.innerHTML = `
        <div class="token-modal-content game-modal">
            <h2>🦙 Catch the Llama!</h2>
            <p>Click the running Llama to earn <strong>500 tokens</strong>!</p>
            <p class="llama-hint">The Llama will appear somewhere on the page...</p>
            <div class="game-buttons">
                <button class="game-cancel-btn">Cancel</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    modal.querySelector('.game-cancel-btn').addEventListener('click', () => {
        modal.remove();
        if (this.llamaElement) this.llamaElement.remove();
    });
    
    // Close modal after a moment to let the game start
    setTimeout(() => {
        modal.remove();
        this.spawnLlama();
    }, 1500);
}

spawnLlama() {
    // Remove existing llama if any
    if (this.llamaElement) this.llamaElement.remove();
    
    // Create llama element
    const llama = document.createElement('div');
    llama.className = 'running-llama';
    llama.textContent = '🦙';
    llama.style.cssText = `
        position: fixed;
        font-size: 48px;
        cursor: pointer;
        z-index: 9999;
        transition: none;
        user-select: none;
        animation: llamaBounce 0.5s infinite alternate;
    `;
    
    // Random starting position
    const startX = Math.random() > 0.5 ? -100 : window.innerWidth + 100;
    const startY = Math.random() * (window.innerHeight - 200) + 100;
    const endX = startX < 0 ? window.innerWidth + 100 : -100;
    const endY = Math.random() * (window.innerHeight - 200) + 100;
    
    llama.style.left = startX + 'px';
    llama.style.top = startY + 'px';
    
    document.body.appendChild(llama);
    this.llamaElement = llama;
    
    // Animate the llama
    const duration = 2000 + Math.random() * 2000; // 2-4 seconds
    const startTime = performance.now();
    
    const animate = (currentTime) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const currentX = startX + (endX - startX) * progress;
        const currentY = startY + (endY - startY) * progress;
        
        llama.style.left = currentX + 'px';
        llama.style.top = currentY + 'px';
        
        // Flip llama based on direction
        if (endX > startX) {
            llama.style.transform = 'scaleX(1)';
        } else {
            llama.style.transform = 'scaleX(-1)';
        }
        
        if (progress < 1) {
            this.llamaAnimationId = requestAnimationFrame(animate);
        } else {
            // Llama escaped!
            llama.remove();
            this.llamaElement = null;
            this.showLlamaResult(false);
        }
    };
    
    this.llamaAnimationId = requestAnimationFrame(animate);
    
    // Click handler
    const catchLlama = () => {
        cancelAnimationFrame(this.llamaAnimationId);
        llama.remove();
        this.llamaElement = null;
        this.grantTokens(500);
        this.showLlamaResult(true);
    };
    
    llama.addEventListener('click', catchLlama);
}

showLlamaResult(caught) {
    const notification = document.createElement('div');
    notification.className = 'llama-result';
    notification.innerHTML = caught 
        ? '🎉 You caught the Llama! +500 tokens! 🦙'
        : '😢 The Llama escaped! Try again!';
    
    notification.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: ${caught ? '#34c759' : '#ff3b30'};
        color: white;
        padding: 20px 40px;
        border-radius: 16px;
        font-size: 1.2rem;
        z-index: 10000;
        animation: fadeIn 0.3s ease;
        text-align: center;
    `;
    
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 2500);
}

// ============ NUMBER GUESS GAME (1000 tokens) - UPDATED ============
async numberGuessGame() {
    const secretNumber = Math.floor(Math.random() * 100000) + 1;
    const maxAttempts = 4;
    let attempts = 0;
    let gameOver = false;
    
    console.log('🤫 Secret number:', secretNumber); // For debugging
    
    const modal = document.createElement('div');
    modal.className = 'token-modal';
    modal.innerHTML = `
        <div class="token-modal-content game-modal">
            <h2>🎯 Number Guessing Game</h2>
            <p>Guess the secret number between <strong>1 and 100,000</strong></p>
            <div class="guess-info">
                <div class="attempts-counter">Attempts remaining: <strong>${maxAttempts}</strong></div>
            </div>
            <div class="guess-rules">
                <div>🎯 Guess exactly right: <strong>1000 tokens</strong></div>
                <div>📈 Close but not exact: <strong>Consolation prize</strong></div>
                <div>💡 You'll only know if your guess is <strong>higher</strong> or <strong>lower</strong></div>
            </div>
            <input type="number" class="math-input guess-input" placeholder="Enter your guess (1-100000)" min="1" max="100000" autofocus>
            <div class="guess-feedback"></div>
            <div class="guess-history"></div>
            <div class="guess-progress">
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width: 100%"></div>
                </div>
            </div>
            <div class="game-buttons">
                <button class="guess-submit-btn">Guess!</button>
                <button class="game-cancel-btn">Give Up</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    const input = modal.querySelector('.guess-input');
    const feedback = modal.querySelector('.guess-feedback');
    const history = modal.querySelector('.guess-history');
    const submitBtn = modal.querySelector('.guess-submit-btn');
    const attemptsCounter = modal.querySelector('.attempts-counter strong');
    const progressBar = modal.querySelector('.progress-bar');
    
    const makeGuess = () => {
        if (gameOver) return;
        
        const guess = parseInt(input.value);
        
        if (isNaN(guess) || guess < 1 || guess > 100000) {
            feedback.innerHTML = '⚠️ Please enter a number between 1 and 100,000';
            feedback.style.color = '#ff9500';
            feedback.className = 'guess-feedback shake';
            setTimeout(() => feedback.className = 'guess-feedback', 500);
            return;
        }
        
        attempts++;
        const attemptsLeft = maxAttempts - attempts;
        const difference = Math.abs(guess - secretNumber);
        
        // Update progress bar
        const progressPercentage = (attemptsLeft / maxAttempts) * 100;
        progressBar.style.width = progressPercentage + '%';
        
        // Update attempts counter
        attemptsCounter.textContent = attemptsLeft;
        
        // Change progress bar color based on attempts left
        if (attemptsLeft <= 1) {
            progressBar.style.background = '#ff3b30';
        } else if (attemptsLeft <= 2) {
            progressBar.style.background = '#ff9500';
        }
        
        // Create history item
        const historyItem = document.createElement('div');
        historyItem.className = 'guess-history-item';
        
        let hint = '';
        let icon = '';
        
        if (guess === secretNumber) {
            // EXACT GUESS!
            gameOver = true;
            this.grantTokens(1000);
            
            feedback.innerHTML = '🎉🎉🎉 <strong>PERFECT!</strong> You guessed the exact number! 🎉🎉🎉';
            feedback.style.color = '#34c759';
            feedback.className = 'guess-feedback success-pulse';
            
            icon = '🎯';
            hint = 'EXACT!';
            
            historyItem.style.background = 'rgba(52, 199, 89, 0.1)';
            historyItem.style.borderLeft = '3px solid #34c759';
            
            submitBtn.disabled = true;
            input.disabled = true;
            
            // Reveal celebration
            setTimeout(() => {
                feedback.innerHTML += `<br><br>🌟 You earned <strong>1000 tokens</strong>! 🌟`;
            }, 500);
            
            setTimeout(() => modal.remove(), 4000);
            
        } else {
            // Wrong guess
            icon = guess < secretNumber ? '📈' : '📉';
            hint = guess < secretNumber ? 'Higher' : 'Lower';
            
            if (attemptsLeft === 0) {
                // Game over - no more attempts
                gameOver = true;
                
                // Calculate consolation prize based on closeness
                let consolation = 0;
                if (difference <= 1000) {
                    consolation = Math.round(100 * (1 - difference / 1000));
                } else {
                    consolation = 5;
                }
                
                this.grantTokens(consolation);
                
                feedback.innerHTML = `
                    <div>😔 <strong>Game Over!</strong> You're out of attempts.</div>
                    <div style="margin-top: 0.5rem;">The secret number was: <strong>${secretNumber.toLocaleString()}</strong></div>
                    <div style="margin-top: 0.5rem;">You were off by: <strong>${difference.toLocaleString()}</strong></div>
                    <div style="margin-top: 0.5rem;">💝 Consolation prize: <strong>${consolation} tokens</strong></div>
                `;
                feedback.style.color = '#ff9500';
                feedback.className = 'guess-feedback';
                
                historyItem.style.background = 'rgba(255, 149, 0, 0.1)';
                historyItem.style.borderLeft = '3px solid #ff9500';
                
                submitBtn.disabled = true;
                input.disabled = true;
                
                setTimeout(() => modal.remove(), 5000);
                
            } else {
                // Still have attempts
                feedback.innerHTML = `${icon} <strong>${hint}!</strong> Try again.`;
                feedback.style.color = '#007aff';
                feedback.className = 'guess-feedback';
                
                if (attemptsLeft === 1) {
                    feedback.innerHTML += '<br>⚠️ <strong>Last attempt!</strong> Make it count!';
                    feedback.style.color = '#ff3b30';
                }
            }
        }
        
        // Add to history
        historyItem.innerHTML = `
            <span>Guess #${attempts}: <strong>${guess.toLocaleString()}</strong></span>
            <span>${icon} ${hint}</span>
        `;
        history.appendChild(historyItem);
        history.scrollTop = history.scrollHeight;
        
        input.value = '';
        if (!gameOver) {
            input.focus();
        }
    };
    
    submitBtn.addEventListener('click', makeGuess);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') makeGuess();
    });
    
    modal.querySelector('.game-cancel-btn').addEventListener('click', () => {
        if (!gameOver) {
            // Small consolation for trying
            this.grantTokens(5);
        }
        modal.remove();
    });
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            if (!gameOver) {
                this.grantTokens(5);
            }
            modal.remove();
        }
    });
}
// ============ GRANT TOKENS ============
async grantTokens(amount) {
    try {
        const response = await this.authFetch(`${this.apiBaseUrl}/auth/tokens/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ amount: amount })
        });
        
        if (response.ok) {
            const data = await response.json();
            this.user = data.user;
            localStorage.setItem('user', JSON.stringify(data.user));
            this.updateTokenDisplay();
        }
    } catch (error) {
        console.error('Failed to grant tokens:', error);
    }
}
    
    async refreshUserData() {
        try {
            const response = await this.authFetch(`${this.apiBaseUrl}/auth/user`, {
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                this.user = data.user;
                localStorage.setItem('user', JSON.stringify(data.user));
                this.updateTokenDisplay();
            } else if (response.status === 401) {
                this.logout();
            }
        } catch (error) {
            console.error('Failed to refresh user data:', error);
        }
    }
    
    toggleSidebar() {
        if (this.sidebar) this.sidebar.classList.toggle('collapsed');
        if (this.sidebarOverlay) this.sidebarOverlay.classList.toggle('active');
    }
    
    async logout() {
        try {
            await this.authFetch(`${this.apiBaseUrl}/auth/logout`, {
                method: 'POST'
            });
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            localStorage.removeItem('user');
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            window.location.href = '/login.html';
        }
    }
    
    scrollToBottom() {
        if (this.chatMessages) {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }
    }
    
    toggleTheme() {
        const html = document.documentElement;
        const currentTheme = html.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        if (this.themeButton) {
            this.themeButton.textContent = newTheme === 'dark' ? '☀️' : '🌓';
        }
    }
    
    loadTheme() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        if (this.themeButton) {
            this.themeButton.textContent = savedTheme === 'dark' ? '☀️' : '🌓';
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async sendMessageAsync() {
    const message = this.userInput.value.trim();
    
    if (!message || this.isProcessing || this.user.tokens <= 0) return;
    
    // Clear empty state
    const emptyState = this.chatMessages.querySelector('.empty-state');
    if (emptyState) emptyState.remove();
    
    // Add user message to UI
    const userMsgDiv = document.createElement('div');
    userMsgDiv.className = 'message user';
    userMsgDiv.innerHTML = `<div class="message-content">${this.escapeHtml(message)}</div>`;
    this.chatMessages.appendChild(userMsgDiv);
    
    // Clear input
    this.userInput.value = '';
    this.userInput.style.height = 'auto';
    this.charCount.textContent = '0';
    this.updateSendButton();
    
    // Show async processing indicator
    const asyncIndicator = document.createElement('div');
    asyncIndicator.className = 'message assistant async-indicator';
    asyncIndicator.id = 'async-indicator';
    asyncIndicator.innerHTML = `
        <div class="async-status">
            <div class="async-spinner"></div>
            <div class="async-text">
                <div class="async-message">⏳ Processing asynchronously...</div>
                <div class="async-progress">
                    <div class="async-progress-bar" style="width: 0%"></div>
                </div>
                <div class="async-task-id">Task ID: pending...</div>
            </div>
        </div>
    `;
    this.chatMessages.appendChild(asyncIndicator);
    this.scrollToBottom();
    
    try {
        this.isProcessing = true;
        this.updateSendButton();
        
        // Submit async task
        const response = await this.authFetch(`${this.apiBaseUrl}/chat/async`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.accessToken}`
            },
            body: JSON.stringify({
                prompt: message,
                conversation_id: this.currentConversation?.id
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to submit async task');
        }
        
        const data = await response.json();
        const taskId = data.task_id;
        
        // Update task ID display
        const taskIdEl = asyncIndicator.querySelector('.async-task-id');
        if (taskIdEl) taskIdEl.textContent = `Task ID: ${taskId}`;
        
        // Poll for results
        await this.pollTaskStatus(taskId, asyncIndicator);
        
    } catch (error) {
        console.error('Async error:', error);
        const errorDiv = document.createElement('div');
        errorDiv.className = 'message error';
        errorDiv.textContent = `Error: ${error.message}`;
        this.chatMessages.appendChild(errorDiv);
    } finally {
        this.isProcessing = false;
        this.updateSendButton();
    }
}

async pollTaskStatus(taskId, indicatorElement) {
    const maxAttempts = 60; // 60 seconds max
    let attempts = 0;
    
    const messageEl = indicatorElement.querySelector('.async-message');
    const progressBar = indicatorElement.querySelector('.async-progress-bar');
    
    while (attempts < maxAttempts) {
        try {
            const response = await this.authFetch(`${this.apiBaseUrl}/chat/task/${taskId}`, {
                headers: {
                    'Authorization': `Bearer ${this.accessToken}`
                }
            });
            
            if (!response.ok) break;
            
            const data = await response.json();
            
            // Update progress
            if (messageEl) messageEl.textContent = data.message || 'Processing...';
            if (progressBar) progressBar.style.width = (data.progress || 0) + '%';
            
            // Check if complete
            if (data.status === 'SUCCESS') {
                // Replace indicator with actual response
                indicatorElement.className = 'message assistant';
                indicatorElement.innerHTML = `
                    <div class="message-content">${this.escapeHtml(data.response)}</div>
                    <div class="async-complete">
                        ✅ Async response (${data.processing_time.toFixed(2)}s)
                        ${data.from_cache ? ' (cached)' : ''}
                    </div>
                `;
                
                // Update tokens
                if (data.tokens_used) {
                    this.user.tokens = data.tokens_remaining;
                    localStorage.setItem('user', JSON.stringify(this.user));
                    this.updateTokenDisplay();
                    this.showTokenCost(data.tokens_used);
                }
                
                // Update conversation
                if (data.conversation_id) {
                    if (!this.currentConversation) {
                        this.currentConversation = { id: data.conversation_id };
                    }
                    await this.loadConversations();
                }
                
                return;
                
            } else if (data.status === 'FAILURE') {
                indicatorElement.className = 'message error';
                indicatorElement.textContent = `Async task failed: ${data.error || 'Unknown error'}`;
                return;
            }
            
        } catch (error) {
            console.error('Poll error:', error);
        }
        
        // Wait before polling again
        await new Promise(resolve => setTimeout(resolve, 1000));
        attempts++;
    }
    
    // Timeout
    indicatorElement.className = 'message error';
    indicatorElement.textContent = 'Async task timed out. Please try again.';
}
setMode(mode) {
    this.useAsync = (mode === 'async');
    
    document.getElementById('mode-sync').classList.toggle('active', !this.useAsync);
    document.getElementById('mode-async').classList.toggle('active', this.useAsync);
    
    console.log(`🔄 Mode switched to: ${this.useAsync ? 'ASYNC' : 'SYNC'}`);
}

}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        window.chatApp = new ChatApp();
    }, 100);
});
    