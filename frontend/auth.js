class AuthManager {
    constructor() {
        this.apiBaseUrl = 'http://localhost:5000/api';
        this.initializeEventListeners();
    }
    
    initializeEventListeners() {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });
        
        document.getElementById('login-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.login();
        });
        
        document.getElementById('register-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.register();
        });
    }
    
    switchTab(tab) {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });
        
        document.getElementById('login-form').classList.toggle('active', tab === 'login');
        document.getElementById('register-form').classList.toggle('active', tab === 'register');
        
        document.querySelectorAll('.error-message').forEach(el => el.textContent = '');
    }
    
    async login() {
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;
        const errorDiv = document.getElementById('login-error');
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Store tokens
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);
                localStorage.setItem('user', JSON.stringify(data.user));
                
                window.location.href = '/';
            } else {
                errorDiv.textContent = data.error || 'Login failed';
            }
        } catch (error) {
            errorDiv.textContent = 'Network error. Please try again.';
        }
    }
    
    async register() {
        const username = document.getElementById('reg-username').value;
        const email = document.getElementById('reg-email').value;
        const password = document.getElementById('reg-password').value;
        const confirmPassword = document.getElementById('reg-confirm-password').value;
        const errorDiv = document.getElementById('register-error');
        
        if (password !== confirmPassword) {
            errorDiv.textContent = 'Passwords do not match';
            return;
        }
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, email, password })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Store tokens
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);
                localStorage.setItem('user', JSON.stringify(data.user));
                
                window.location.href = '/';
            } else {
                errorDiv.textContent = data.error || 'Registration failed';
            }
        } catch (error) {
            errorDiv.textContent = 'Network error. Please try again.';
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new AuthManager();
});