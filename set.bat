@echo off
cd /d "%~dp0"
title Quiz App - Auto Setup

echo ========================================================
echo Quiz Application - Setup and Run
echo ========================================================
echo.

echo [0/5] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)

if exist "venv\Scripts\python.exe" (
    echo [1/5] Virtual environment already exists. Skipping...
) else (
    if exist "venv" (
        echo [1/5] Broken venv found. Deleting and recreating...
        rmdir /s /q venv
    ) else (
        echo [1/5] Creating virtual environment...
    )
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created!
)
echo.

echo [2/5] Installing dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)
echo [OK] Dependencies installed!
echo.

echo [3/5] Setting up database...
venv\Scripts\python.exe manage.py migrate --run-syncdb
if errorlevel 1 (
    echo [ERROR] Database migration failed!
    pause
    exit /b 1
)
echo [OK] Database ready!
echo.

echo [4/5] Collecting static files...
venv\Scripts\python.exe manage.py collectstatic --noinput >nul 2>&1
echo [OK] Static files ready!
echo.

echo [5/5] Starting server...
echo URL: http://127.0.0.1:8000
echo Admin: http://127.0.0.1:8000/admin/
echo Press Ctrl+C to stop.
echo ========================================================
echo.

venv\Scripts\python.exe manage.py runserver

pause
