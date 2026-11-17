@echo off
setlocal enabledelayedexpansion

echo.
echo   ___                 _   ____  _     _      _     _
echo  ^|   ^ ^| __ _  ___ _ __ ^| ^|^|  _ \^| ^|__  ^(_) ___^| ^|  __^|
echo  ^| ^|^| ^|/ _` ^|/ _ \ '_ \^|__^| ^|_) ^| '_ \ ^| ^|/ _ \ ^|/ _` ^|
echo  ^|___/^|\__, ^|\___/ ^| ^| ^|  ^|  __/^| ^| ^| ^|^| ^|  __/ ^| (_^| ^|
echo        ^|___/       ^|_^| ^|_^|  ^|_^|  ^|_^| ^|_^|_^|^\_^__^|_^|\__,_^|
echo.
echo   Zero-Trust Security Firewall for AI Agents
echo   ============================================
echo.

rem ── 1. Python venv ──────────────────────────────────────────────
if not exist "%~dp0backend\venv" (
    echo [1/4] Creating Python virtual environment...
    python -m venv "%~dp0backend\venv"
    if errorlevel 1 (
        echo.
        echo  [ERROR] Python not found. Install Python 3.10+ from https://python.org
        pause
        exit /b 1
    )
    echo [2/4] Installing backend dependencies...
    "%~dp0backend\venv\Scripts\pip.exe" install -r "%~dp0backend\requirements.txt"
) else (
    echo [1/4] Python venv found — skipping install.
    echo [2/4] Skipping backend dependencies.
)

rem ── 2. .env with auto-generated secret ──────────────────────────
if not exist "%~dp0backend\.env" (
    echo [3/4] Generating secure .env configuration...
    "%~dp0backend\venv\Scripts\python.exe" -c "import secrets; key=secrets.token_hex(32); lines=['AGENTSHIELD_SECRET='+key,'AGENTSHIELD_ENV=development','TOKEN_EXPIRE_HOURS=24','GEMINI_API_KEY=your-gemini-api-key-here']; open(r'%~dp0backend\.env','w').write('\n'.join(lines)+'\n'); print('  Secret generated: '+key[:8]+'...')"
) else (
    echo [3/4] .env already exists — skipping.
)

rem ── 3. Frontend node_modules ─────────────────────────────────────
if not exist "%~dp0frontend\node_modules" (
    echo [4/4] Installing frontend dependencies...
    cd /d "%~dp0frontend"
    call npm install
) else (
    echo [4/4] node_modules found — skipping.
)

echo.
echo   Starting services...
echo   ====================
echo.
echo [Backend]  Starting FastAPI on http://localhost:8000
start "AgentShield Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\activate && uvicorn main:app --host 0.0.0.0 --port 8000"

timeout /t 4 /nobreak >nul

echo [Frontend] Starting React on http://localhost:3000
start "AgentShield Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo   ✅  AgentShield is running!
echo   ===========================
echo   Dashboard  : http://localhost:3000
echo   API Docs   : http://localhost:8000/docs
echo   Health     : http://localhost:8000/health
echo.
echo   Press Ctrl+C in each window to stop the servers.
echo.

timeout /t 3 /nobreak >nul
start "" "http://localhost:3000"
