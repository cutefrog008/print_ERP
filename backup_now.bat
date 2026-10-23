@echo off
REM ============================================================
REM  backup_now.bat
REM  Create a VERIFIED MANUAL backup of the Printing ERP.
REM  Location: D:\PrintingERP\print_ERP\backup_now.bat
REM  (Also copied to D:\PrintingERP\ by setup_backup_system.bat)
REM ============================================================

setlocal

cd /d "%~dp0"

echo.
echo ========================================
echo   Printing ERP - MANUAL BACKUP
echo ========================================
echo.

REM --- Find python from venv ---
set PYTHON=
if exist "venv\Scripts\python.exe" (
    set PYTHON="%~dp0venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set PYTHON=python
    ) else (
        echo [ERROR] Python not found. Expected venv\Scripts\python.exe
        echo Please run this script from D:\PrintingERP\print_ERP\
        pause
        exit /b 1
    )
)

REM --- Ensure backup dir structure exists (user-facing bat can create when run directly) ---
call %PYTHON% -c "from pathlib import Path; root=Path(r'D:\PrintingERP\backups'); [p.mkdir(parents=True, exist_ok=True) for p in [root, root/'daily', root/'weekly', root/'monthly', root/'pre_restore', root/'logs']]" 2>nul

REM --- Run backup ---
echo [INFO] Starting manual backup...
echo.

%PYTHON% "%~dp0backup_system\backup.py" manual
set EXITCODE=%errorlevel%

echo.
if %EXITCODE%==0 (
    echo ========================================
    echo   BACKUP COMPLETED SUCCESSFULLY
    echo ========================================
    echo.
    echo Backup files are stored in:
    echo   D:\PrintingERP\backups\
    echo.
    echo Latest status:
    type "D:\PrintingERP\backups\logs\latest_backup_status.txt" 2>nul
) else (
    echo ========================================
    echo   BACKUP FAILED  (exit code %EXITCODE%)
    echo ========================================
    echo.
    echo See log: D:\PrintingERP\backups\logs\backup.log
)

echo.
pause
endlocal
exit /b %EXITCODE%
