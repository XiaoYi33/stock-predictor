@echo off
chcp 65001 >nul
echo ===== Stopping Stock Predictor =====

powershell -Command "& { Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force; Write-Host ('Backend (port 5000) closed') } }"
powershell -Command "& { Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force; Write-Host ('Frontend (port 5173) closed') } }"

echo ===== All services stopped =====
pause