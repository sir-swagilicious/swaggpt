const express = require('express');
const path = require('path');
const cors = require('cors');

const app = express();
const PORT = 8000;

app.use(cors());
app.use(express.static(path.join(__dirname, 'frontend')));

// Routes
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'frontend', 'index.html'));
});

app.get('/login.html', (req, res) => {
    res.sendFile(path.join(__dirname, 'frontend', 'login.html'));
});

app.get('/health', (req, res) => {
    res.json({ status: 'healthy', server: 'frontend', port: PORT });
});

app.listen(PORT, () => {
    console.log(`🚀 Frontend server running on http://localhost:${PORT}`);
    console.log(`📁 Serving files from: ${path.join(__dirname, 'frontend')}`);
    console.log(`🔗 Backend API expected at: http://localhost:5000/api`);
    console.log('\nPress Ctrl+C to stop the server\n');
});
