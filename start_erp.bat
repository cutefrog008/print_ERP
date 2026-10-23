@echo off
REM ============================================================
REM  start_erp.bat
REM  Printing ERP boot-time launcher.
REM
REM  1. Checks whether the PREVIOUS day has a backup (IST). If that
REM     day has no backup, creates a verified catch-up backup.
REM  2. Confirms the firewall rule that lets LAN/Wi-Fi devices in.
REM  3. Starts the Django server on 0.0.0.0:8000 in the
REM     BACKGROUND with a hidden console window, so every device
REM     on the same network (Wi-Fi or LAN) can reach the platform.
REM
REM  Run this by hand, or let it run automatically at logon via
REM  register_startup_task.bat (which launches it windowless
REM  through start_erp_hidden.vbs).
REM
REM  To stop the background server later, run stop_erp.bat.
REM ============================================================

setlocal

cd /d "%~dp0"

REM "hidden" is passed by start_erp_hidden.vbs so the script never
REM blocks on a "pause" that nobody can see or answer.
set "HIDDEN=0"
if /i "%~1"=="hidden" set "HIDDEN=1"

echo.
echo ================================================================
echo    PRINTING ERP - STARTUP
echo ================================================================
echo.

REM --- Locate Python (virtual environment preferred) ---
REM PYTHON keeps the quotes (used for direct calls); PYEXE is the bare
REM path (used by Start-Process).
set PYTHON=
set PYEXE=
if exist "venv\Scripts\python.exe" (
    set PYTHON="%~dp0venv\Scripts\python.exe"
    set PYEXE=%~dp0venv\Scripts\python.exe
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set PYTHON=python
        set PYEXE=python
    ) else (
        echo [ERROR] Python not found. Expected venv\Scripts\python.exe
        echo         Run this script from D:\PrintingERP\print_ERP\
        echo.
        if "%HIDDEN%"=="0" pause
        exit /b 1
    )
)
echo [OK] Python: %PYTHON%
echo.

REM --- Step 1 + 2: previous-day (IST) backup check / catch-up ---
echo [1/3] Checking previous day's backup (IST)...
echo ----------------------------------------------------------------
%PYTHON% "%~dp0backup_system\startup.py" check
set BACKUP_RC=%errorlevel%
echo ----------------------------------------------------------------
if %BACKUP_RC%==0 (
    echo [OK] Previous day's backup verified or created.
) else (
    echo [WARNING] Previous day's backup could NOT be produced. Code: %BACKUP_RC%
    echo           Starting the ERP anyway so the platform stays available.
    echo           Details: D:\PrintingERP\backups\logs\backup.log
)
echo.

REM --- Step 2: confirm the firewall rule that lets LAN/Wi-Fi devices in ---
echo [2/3] Checking firewall rule for TCP 8000...
netsh advfirewall firewall show rule name="Printing ERP Django (TCP 8000)" >nul 2>&1
if %errorlevel%==0 (
    echo [OK] Firewall rule present - LAN and Wi-Fi devices may connect.
) else (
    echo [WARNING] Firewall rule "Printing ERP Django (TCP 8000)" is missing.
    echo           Other devices will be blocked until you run
    echo           allow_django_firewall.bat once, as administrator.
)
echo.

REM --- Step 3: start the server in the BACKGROUND (no console window) ---
echo [3/3] Starting Django server on 0.0.0.0:8000 in the background...
echo ----------------------------------------------------------------
echo  On this computer : http://127.0.0.1:8000/login/
set "LAN_IP="
for /f "tokens=2 delims=:(" %%a in ('ipconfig ^| findstr /i "IPv4"') do if not defined LAN_IP set "LAN_IP=%%a"
if defined LAN_IP set "LAN_IP=%LAN_IP: =%"
if defined LAN_IP echo  On Wi-Fi / LAN   : http://%LAN_IP%:8000/login/

REM Start Django as a detached process with a HIDDEN console window.
REM (pythonw.exe is NOT used: it has no console handles at all, which
REM makes Django's runserver hang and never bind the port.)
REM --noreload keeps it a single, stable background process.
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
if %errorlevel%==0 (
    echo [INFO] A server is already listening on port 8000 - not starting another.
) else (
    powershell -NoProfile -Command "Start-Process -FilePath '%PYEXE%' -ArgumentList 'manage.py','runserver','0.0.0.0:8000','--noreload' -WorkingDirectory '%CD%' -WindowStyle Hidden"
    echo [OK] Django launched with a hidden window.
)
echo.

REM --- Wait until the server actually accepts connections ---
echo [INFO] Waiting for the server to accept connections...
powershell -NoProfile -Command "for($i=0;$i -lt 40;$i++){try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',8000);$c.Close();exit 0}catch{Start-Sleep -Milliseconds 500}}; exit 1" >nul 2>&1
if %errorlevel%==0 (
    echo [OK] Server is up.
) else (
    echo [WARNING] Server did not respond within 20 seconds.
)
echo.

echo ================================================================
echo    Server is running in the background (no window).
echo    To stop it later, run  stop_erp.bat
echo ================================================================
echo.

if "%HIDDEN%"=="0" pause

endlocal
exit /b 0
