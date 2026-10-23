@echo off
REM ============================================================
REM  restore_erp.bat
REM  INTERACTIVE restore workflow for Printing ERP backups.
REM  Location: D:\PrintingERP\print_ERP\restore_erp.bat
REM  (Also copied to D:\PrintingERP\ by setup_backup_system.bat)
REM ============================================================

setlocal

cd /d "%~dp0"

echo.
echo ========================================
echo   Printing ERP - RESTORE
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

REM --- Ensure dirs exist ---
call %PYTHON% -c "from pathlib import Path; root=Path(r'D:\PrintingERP\backups'); [p.mkdir(parents=True, exist_ok=True) for p in [root, root/'daily', root/'weekly', root/'monthly', root/'pre_restore', root/'logs']]" 2>nul

REM --- Run interactive restore ---
%PYTHON% "%~dp0backup_system\restore.py"
set EXITCODE=%errorlevel%

echo.
pause
endlocal
exit /b %EXITCODE%
