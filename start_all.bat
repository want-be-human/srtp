@echo off
echo Starting Backend and Frontend services using PowerShell...

start "Backend" powershell -NoExit -Command "cd backend; python -m uvicorn main:app --reload"

start "Frontend" powershell -NoExit -Command "cd front; npm run dev"

echo All services are starting in new PowerShell windows.
