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

rem 1. Check Python virtual environment
if not exist "%~dp0backend\venv" (
    echo [Setup] Creating Python virtual environment...
    python -m venv "%~dp0backend\venv"
    if errorlevel 1 (
        echo [ERROR] Python not found or failed to create venv. Please install Python 3.10+
        pause
        exit /b 1
    )
    echo [Setup] Installing backend dependencies...
    call "%~dp0backend\venv\Scripts\activate.bat"
    pip install -r "%~dp0backend\requirements.txt"
)

rem 2. Check .env
if not exist "%~dp0backend\.env" (
    echo [Setup] Creating default .env configuration...
    copy "%~dp0backend\.env.example" "%~dp0backend\.env" >nul
)

rem 3. Check frontend node_modules
if not exist "%~dp0frontend\node_modules" (
    echo [Setup] Installing frontend dependencies (npm install)...
    cd /d "%~dp0frontend"
    call npm install
)

echo.
echo [1/2] Starting Backend (FastAPI on :8000)...
start "AgentShield Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\activate && uvicorn main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 4 /nobreak >nul

echo [2/2] Starting Frontend (React on :3000)...
start "AgentShield Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo   Both services running:
echo   ======================
echo   Dashboard : http://localhost:3000
echo   API Docs  : http://localhost:8000/docs
echo   Health    : http://localhost:8000/health
echo.

timeout /t 3 /nobreak >nul
start "" "http://localhost:3000"
