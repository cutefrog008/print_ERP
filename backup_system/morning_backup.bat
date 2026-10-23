@echo off
REM ============================================================
REM  morning_backup.bat
REM  Called by Windows Task Scheduler at system startup.
REM  Waits configurable minutes, ensures one backup per day,
REM  then creates a verified backup.
REM  Location: D:\PrintingERP\print_ERP\backup_system\
REM ============================================================

setlocal

cd /d "%~dp0"

REM --- Find python from venv ---
set PYTHON=
if exist "..\venv\Scripts\python.exe" (
    set PYTHON="%~dp0..\venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set PYTHON=python
    ) else (
        REM Fallback: log failure to event log-ish location
        mkdir "%TEMP%\printing_erp" 2>nul
        echo [%date% %time%] morning_backup.bat: PYTHON NOT FOUND >> "%TEMP%\printing_erp\backup_errors.log"
        exit /b 1
    )
)

REM --- Ensure backup dir structure exists ---
call %PYTHON% -c "from pathlib import Path; root=Path(r'D:\PrintingERP\backups'); [p.mkdir(parents=True, exist_ok=True) for p in [root, root/'daily', root/'weekly', root/'monthly', root/'pre_restore', root/'logs']]" 2>nul

REM --- Run morning backup (delay + one-per-day check inside Python) ---
%PYTHON% "%~dp0backup.py" morning
set EXITCODE=%errorlevel%

exit /b %EXITCODE%
endlocal
