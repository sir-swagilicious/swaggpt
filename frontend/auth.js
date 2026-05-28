class AuthManager {
    constructor() {
        this.apiBaseUrl = 'http://localhost:5000/api';
        this.initializeEventListeners();
    }
    
    initializeEventListeners() {
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });
        
        // Login form
        document.getElementById('login-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.login();
        });
        
        // Register form
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
            console.log('Attempting login...');
            
            const response = await fetch(`${this.apiBaseUrl}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',  // Important for cookies
                body: JSON.stringify({ username, password })
            });
            
            console.log('Login response status:', response.status);
            
            const data = await response.json();
            console.log('Login response data:', data);
            
            if (response.ok) {
                localStorage.setItem('user', JSON.stringify(data.user));
                console.log('Login successful, redirecting...');
                window.location.href = '/';
            } else {
                errorDiv.textContent = data.error || 'Login failed';
            }
        } catch (error) {
            console.error('Login error:', error);
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
            console.log('Attempting registration...');
            
            const response = await fetch(`${this.apiBaseUrl}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',  // Important for cookies
                body: JSON.stringify({ username, email, password })
            });
            
            console.log('Register response status:', response.status);
            
            const data = await response.json();
            console.log('Register response data:', data);
            
            if (response.ok) {
                localStorage.setItem('user', JSON.stringify(data.user));
                console.log('Registration successful, redirecting...');
                window.location.href = '/';
            } else {
                errorDiv.textContent = data.error || 'Registration failed';
            }
        } catch (error) {
            console.error('Registration error:', error);
            errorDiv.textContent = 'Network error. Please try again.';
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new AuthManager();
});