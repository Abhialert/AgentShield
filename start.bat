@echo off
echo.
echo  ___                 _   ____  _     _      _     _
echo ^|   ^ ^| __ _  ___ _ __ ^| ^|^|  _ \^| ^|__  ^(_) ___^| ^|  __^|
echo ^| ^|^| ^|/ _` ^|/ _ \ '_ \^|__^| ^|_) ^| '_ \ ^| ^|/ _ \ ^|/ _` ^|
echo ^|___/^|\__, ^|\___/ ^| ^| ^|  ^|  __/^| ^| ^| ^|^| ^|  __/ ^| (_^| ^|
echo       ^|___/       ^|_^| ^|_^|  ^|_^|  ^|_^| ^|_^|_^|^\_^__^|_^|\__,_^|
echo.
echo  Zero-Trust Security Firewall for AI Agents
echo  ============================================
echo.

echo [1/2] Starting Backend (FastAPI on :8000)...
start "AgentShield Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\activate && uvicorn main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 4 /nobreak >nul

echo [2/2] Starting Frontend (React on :3000)...
start "AgentShield Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo  Both services starting...
echo  Backend  : http://localhost:8000
echo  Frontend : http://localhost:3000
echo  API Docs : http://localhost:8000/docs
echo.

timeout /t 3 /nobreak >nul
start "" "http://localhost:3000"
