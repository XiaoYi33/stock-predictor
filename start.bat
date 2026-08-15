@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===== Starting Stock Predictor =====

echo [1/3] Starting backend...
powershell -Command "Start-Process 'D:\ProgramData\Anaconda3\python.exe' -ArgumentList 'backend\app.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden"
timeout /t 8 /nobreak >nul
echo Backend started (port 5000)

echo [2/3] Starting frontend...
powershell -Command "Start-Process 'node' -ArgumentList 'node_modules\vite\bin\vite.js' -WorkingDirectory '%~dp0frontend' -WindowStyle Hidden"
timeout /t 4 /nobreak >nul
echo Frontend started (port 5173)

echo [3/3] Opening browser...
start http://localhost:5173
echo ===== All services started =====
exit