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

# ── 1. Python venv ───────────────────────────────────────────────
if [ ! -d "$DIR/backend/venv" ]; then
    echo "[1/4] Creating Python virtual environment..."
    python3 -m venv "$DIR/backend/venv" || {
        echo "[ERROR] Python 3 not found. Install Python 3.10+ from https://python.org"
        exit 1
    }
    echo "[2/4] Installing backend dependencies..."
    "$DIR/backend/venv/bin/pip" install -r "$DIR/backend/requirements.txt"
else
    echo "[1/4] Python venv found — skipping install."
    echo "[2/4] Skipping backend dependencies."
fi

# ── 2. .env with auto-generated secret ───────────────────────────
if [ ! -f "$DIR/backend/.env" ]; then
    echo "[3/4] Generating secure .env configuration..."
    "$DIR/backend/venv/bin/python3" -c "
import secrets
key = secrets.token_hex(32)
env_content = f'''AGENTSHIELD_SECRET={key}
AGENTSHIELD_ENV=development
TOKEN_EXPIRE_HOURS=24
GEMINI_API_KEY=your-gemini-api-key-here
'''
with open('$DIR/backend/.env', 'w') as f:
    f.write(env_content)
print(f'  Secret generated: {key[:8]}...')
"
else
    echo "[3/4] .env already exists — skipping."
fi

# ── 3. Frontend node_modules ─────────────────────────────────────
if [ ! -d "$DIR/frontend/node_modules" ]; then
    echo "[4/4] Installing frontend dependencies..."
    (cd "$DIR/frontend" && npm install)
else
    echo "[4/4] node_modules found — skipping."
fi

echo ""
echo "  Starting services..."
echo "  ===================="
echo ""

# Start backend
echo "[Backend]  Starting FastAPI on http://localhost:8000"
(cd "$DIR/backend" && "$DIR/backend/venv/bin/uvicorn" main:app --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!

sleep 3

# Start frontend
echo "[Frontend] Starting React on http://localhost:3000"
(cd "$DIR/frontend" && npm run dev) &
FRONTEND_PID=$!

# Clean shutdown on Ctrl+C
trap "echo ''; echo 'Stopping AgentShield...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

echo ""
echo "  ✅  AgentShield is running!"
echo "  ==========================="
echo "  Dashboard  : http://localhost:3000"
echo "  API Docs   : http://localhost:8000/docs"
echo "  Health     : http://localhost:8000/health"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo ""

# Auto-open browser
if command -v open >/dev/null 2>&1; then
    sleep 2 && open "http://localhost:3000" &
elif command -v xdg-open >/dev/null 2>&1; then
    sleep 2 && xdg-open "http://localhost:3000" &
fi

wait
