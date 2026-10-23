@echo off
REM ============================================================
REM  start_lan_server.bat
REM  Start Printing ERP Django server accessible over LAN
REM ============================================================

echo.
echo ========================================
echo   Printing ERP - LAN Server Starter
echo ========================================
echo.

cd /d "%~dp0"

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
) else (
    echo [ERROR] Virtual environment not found at: %~dp0venv
    echo Expected: %~dp0venv\Scripts\activate.bat
    pause
    exit /b 1
)

echo [OK] Virtual environment activated.
echo [INFO] Starting Django server on 0.0.0.0:8000 ...
echo.
echo Access URLs:
echo   On this computer:     http://127.0.0.1:8000
echo   On LAN / Wi-Fi:       http://192.168.1.50:8000
echo.
echo Press Ctrl+C to stop the server.
echo ========================================
echo.

python manage.py runserver 0.0.0.0:8000

pause
