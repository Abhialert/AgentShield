#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

echo ""
echo "  ___                 _   ____  _     _      _     _"
echo " |   | __ _  ___ _ __ | ||  _ \| |__  (_) ___| |  __|"
echo " | || |/ _\` |/ _ \ '_ \|__| |_) | '_ \ | |/ _ \ |/ _\` |"
echo " |___/|\__, |\___/ | | |  |  __/| | | || |  __/ | (_| |"
echo "       |___/       |_| |_|  |_|  |_| |_|_|\___|_|\__,_|"
echo ""
echo "  Zero-Trust Security Firewall for AI Agents"
echo "  ============================================"
echo ""

# 1. Check Python virtual environment
if [ ! -d "$DIR/backend/venv" ]; then
    echo "[Setup] Creating Python virtual environment..."
    python3 -m venv "$DIR/backend/venv"
    source "$DIR/backend/venv/bin/activate"
    echo "[Setup] Installing backend dependencies..."
    pip install -r "$DIR/backend/requirements.txt"
else
    source "$DIR/backend/venv/bin/activate"
fi

# 2. Check .env
if [ ! -f "$DIR/backend/.env" ]; then
    echo "[Setup] Creating default .env configuration..."
    cp "$DIR/backend/.env.example" "$DIR/backend/.env"
fi

# 3. Check frontend node_modules
if [ ! -d "$DIR/frontend/node_modules" ]; then
    echo "[Setup] Installing frontend dependencies (npm install)..."
    (cd "$DIR/frontend" && npm install)
fi

echo ""
echo "[1/2] Starting Backend (FastAPI on :8000)..."
(cd "$DIR/backend" && uvicorn main:app --reload --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!

sleep 3

echo "[2/2] Starting Frontend (React on :3000)..."
(cd "$DIR/frontend" && npm run dev) &
FRONTEND_PID=$!

# Trap Ctrl+C to cleanly kill both processes
trap "echo 'Stopping AgentShield...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

echo ""
echo "  Both services running:"
echo "  ======================"
echo "  Dashboard : http://localhost:3000"
echo "  API Docs  : http://localhost:8000/docs"
echo "  Health    : http://localhost:8000/health"
echo ""

# Attempt to open browser automatically
if command -v open >/dev/null 2>&1; then
    open "http://localhost:3000"
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://localhost:3000"
fi

wait
