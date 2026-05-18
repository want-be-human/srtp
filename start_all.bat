@echo off
chcp 65001 >nul 2>&1
title SRTP Welding Detection System Launcher
color 0A

:HEADER
cls
echo.
echo  ================================================================
echo       SRTP Welding Detection System v2.1
echo       Intelligent Welding Teaching System
echo  ================================================================
echo.

:CHECK_ENVIRONMENT
echo [Checking Environment] Validating runtime environment...
echo.

:: Check Python
echo [1/4] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ERROR] Python not detected! Please install Python 3.8+
    echo Download: https://www.python.org/downloads/
    goto ERROR_EXIT
)
for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [OK] %PYTHON_VERSION%
echo.

:: Check Node.js
echo [2/4] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ERROR] Node.js not detected! Please install Node.js 16+
    echo Download: https://nodejs.org/
    goto ERROR_EXIT
)
for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
echo [OK] Node.js %NODE_VERSION%
echo.

:: Check backend directory
echo [3/4] Checking backend environment...
if not exist "backend\main.py" (
    color 0C
    echo [ERROR] backend\main.py not found!
    echo Please run this script from project root directory.
    goto ERROR_EXIT
)
if not exist "backend\requirements.txt" (
    color 0E
    echo [WARNING] requirements.txt not found
) else (
    echo [INFO] Backend dependencies: FastAPI, Uvicorn, OpenCV, Ultralytics YOLO
    echo [INFO] If backend fails, run: cd backend ^&^& pip install -r requirements.txt
)
if not exist "backend\services\yolo\zonghe_hanjie_zhiliang_jiance_xitong.py" (
    color 0E
    echo [WARNING] YOLO detection module not found, will use mock data
)
echo [OK] Backend directory structure is valid
echo.

:: Check frontend directory
echo [4/4] Checking frontend environment...
if not exist "front\package.json" (
    color 0C
    echo [ERROR] front\package.json not found!
    echo Please run this script from project root directory.
    goto ERROR_EXIT
)
if not exist "front\node_modules" (
    color 0E
    echo [WARNING] node_modules not found
    echo [INFO] Run: cd front ^&^& npm install --legacy-peer-deps
    echo.
    set /p INSTALL_DEPS="Install frontend dependencies now? (Y/N): "
    if /i "!INSTALL_DEPS!"=="Y" (
        echo [EXECUTING] Installing frontend dependencies...
        cd front
        call npm install --legacy-peer-deps
        cd ..
        echo [DONE] Dependencies installed
        echo.
    )
)
echo [OK] Frontend directory structure is valid
echo.

:START_SERVICES
echo.
echo ================================================================
echo  Starting services...
echo ================================================================
echo.

:: Check and kill processes on port 8000
echo [Pre-check] Checking port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo [INFO] Port 8000 is occupied by PID %%a, terminating...
    taskkill //F //PID %%a >nul 2>&1
)

:: Check and kill processes on port 3000
echo [Pre-check] Checking port 3000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    echo [INFO] Port 3000 is occupied by PID %%a, terminating...
    taskkill //F //PID %%a >nul 2>&1
)

timeout /t 1 /nobreak >nul

echo.
echo  Backend Service: http://localhost:8000
echo  Frontend Service: http://localhost:3000
echo  API Documentation: http://localhost:8000/docs
echo.
timeout /t 1 /nobreak >nul

echo [1/2] Starting Backend Service (FastAPI)...
start "SRTP-Backend" cmd /k "title Backend-FastAPI && color 0A && echo [Backend] Starting... && cd backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"

echo [INFO] Backend starting, waiting 3 seconds before frontend...
timeout /t 3 /nobreak >nul

echo [2/2] Starting Frontend Service (Next.js)...
start "SRTP-Frontend" cmd /k "title Frontend-NextJS && color 0B && echo [Frontend] Starting... && cd front && npm run dev"

echo.
echo ================================================================
echo  System Startup Completed!
echo ================================================================
echo.
echo  [Status] Services are running in background
echo.
echo  [Access] Frontend UI: http://localhost:3000
echo  [Access] Backend API: http://localhost:8000
echo  [Access] API Docs: http://localhost:8000/docs
echo.
echo  [INFO] Frontend may take 30-60 seconds to fully start
echo  [INFO] Close backend/frontend windows to stop services
echo.
echo ================================================================
echo.

:: Ask to open browser
set /p OPEN_BROWSER="Open browser automatically? (Y/N, default N): "
if /i "%OPEN_BROWSER%"=="Y" (
    echo [EXECUTING] Opening browser...
    timeout /t 5 /nobreak >nul
    start http://localhost:3000
    echo [DONE] Browser opened
)

echo.
echo Press any key to close this window (services will keep running)...
pause >nul
exit

:ERROR_EXIT
echo.
echo ================================================================
echo  Startup Failed! Please check the error messages above
echo ================================================================
echo.
echo Common Solutions:
echo  1. Install Python 3.8+: https://www.python.org/downloads/
echo  2. Install Node.js 16+: https://nodejs.org/
echo  3. Install backend dependencies: cd backend ^&^& pip install -r requirements.txt
echo  4. Install frontend dependencies: cd front ^&^& npm install --legacy-peer-deps
echo.
echo Press any key to exit...
pause >nul
exit
