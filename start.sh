#!/bin/bash

# Lease Management System - Startup Script

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting Lease Management Application..."
echo "📍 Working directory: $(pwd)"

# Install dependencies if needed
echo "📦 Checking dependencies..."
pip3 install --user Flask flask-cors bcrypt cryptography python-dateutil werkzeug 2>&1 | grep -v "already satisfied" || true

# Kill old processes on port 5001
echo "🛑 Stopping existing processes..."
pkill -f "app.py" 2>/dev/null || true
lsof -ti:5001 | xargs kill -9 2>/dev/null || true
sleep 2

# Ensure logs directory exists
mkdir -p "$SCRIPT_DIR/lease_application/logs"

# Start Flask application
echo "🚀 Starting Flask application..."
python3 -m lease_application.app > "$SCRIPT_DIR/lease_application/logs/lease_app.log" 2>&1 &
FLASK_PID=$!
echo "✅ Flask app started (PID: $FLASK_PID)"

# Wait for server to be ready
echo "⏳ Waiting for server to start..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:5001/login.html > /dev/null 2>&1; then
        echo "✅ Server is ready!"
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
    echo -n "."
done
echo ""

if [ $attempt -eq $max_attempts ]; then
    echo "⚠️  Server may still be starting. Check logs if pages don't load."
fi

# Open application in browser
echo "🌐 Opening application in browser..."
sleep 1
open http://localhost:5001/login.html 2>/dev/null || \
    start http://localhost:5001/login.html 2>/dev/null || \
    xdg-open http://localhost:5001/login.html 2>/dev/null || \
    echo "   Please open http://localhost:5001/login.html in your browser"

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "   📊 Application Ready!"
echo "══════════════════════════════════════════════════════════════"
echo ""
echo "🔗 Application URL: http://localhost:5001"
echo "📝 Login Page:      http://localhost:5001/login.html"
echo "📊 Dashboard:       http://localhost:5001/dashboard.html"
echo "📄 Logs:            $SCRIPT_DIR/lease_application/logs/lease_app.log"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Tail logs
tail -f "$SCRIPT_DIR/lease_application/logs/lease_app.log"
