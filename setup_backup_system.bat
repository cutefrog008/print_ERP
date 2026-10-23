@echo off
REM ============================================================
REM  setup_backup_system.bat
REM  ONE-TIME SETUP for the Printing ERP Backup & Restore System
REM
REM  Run as: Double-click this file as a normal user (no admin needed).
REM  What it does:
REM    1. Creates D:\PrintingERP\backups\ with all subdirectories
REM    2. Copies user-facing .bat scripts to D:\PrintingERP\
REM    3. Registers Windows Task Scheduler "Printing ERP - Morning Backup"
REM       Trigger: At system startup, delay = ERP_BACKUP_DELAY env var or 10 min
REM    4. Runs a TEST MANUAL BACKUP to validate everything works
REM ============================================================

setlocal

cd /d "%~dp0"

echo.
echo ================================================================
echo    PRINTING ERP - BACKUP & RESTORE SYSTEM - ONE-TIME SETUP
echo ================================================================
echo.
echo This script will:
echo   1. Create backup directory structure at D:\PrintingERP\backups\
echo   2. Copy backup_now.bat and restore_erp.bat to D:\PrintingERP\
echo   3. Register Windows Task Scheduler: "Printing ERP - Morning Backup"
echo        Trigger: At startup + 10min delay (configurable later)
echo   4. Run a test manual backup
echo.
pause

REM ---- 0. Ensure Python exists
set PYTHON=
if exist "venv\Scripts\python.exe" (
    set PYTHON="%~dp0venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set PYTHON=python
    ) else (
        echo.
        echo [ERROR] Python not found in venv or PATH.
        echo Please run this from D:\PrintingERP\print_ERP\ where venv\ exists.
        pause
        exit /b 1
    )
)
echo [OK] Python found.

REM ---- 1. Create D:\PrintingERP\backups\  +  subdirs
echo.
echo [1/4] Creating D:\PrintingERP\backups\ directory structure ...
call %PYTHON% -c "from pathlib import Path; root=Path(r'D:\PrintingERP\backups'); [p.mkdir(parents=True, exist_ok=True) for p in [root, root/'daily', root/'weekly', root/'monthly', root/'pre_restore', root/'logs']]" 2>nul
if exist "D:\PrintingERP\backups\logs" (
    echo [OK] Backup directories created successfully.
) else (
    echo [WARNING] Could not verify backup directories. Please create them manually:
    echo    D:\PrintingERP\backups\daily
    echo    D:\PrintingERP\backups\weekly
    echo    D:\PrintingERP\backups\monthly
    echo    D:\PrintingERP\backups\pre_restore
    echo    D:\PrintingERP\backups\logs
)

REM ---- 2. Copy user-facing BATs to D:\PrintingERP\
echo.
echo [2/4] Copying user-facing scripts to D:\PrintingERP\ ...
copy /y "backup_now.bat"   "..\backup_now.bat"       >nul 2>&1
copy /y "restore_erp.bat"  "..\restore_erp.bat"     >nul 2>&1
copy /y "start_lan_server.bat" "..\start_lan_server.bat" >nul 2>&1
copy /y "allow_django_firewall.bat" "..\allow_django_firewall.bat" >nul 2>&1
copy /y "show_lan_ip.bat" "..\show_lan_ip.bat" >nul 2>&1
copy /y "BACKUP_RESTORE.md" "..\BACKUP_RESTORE.md" >nul 2>&1
echo [OK] Scripts copied to D:\PrintingERP\

REM ---- 3. Register Task Scheduler task
echo.
echo [3/4] Registering Windows Task Scheduler task: "Printing ERP - Morning Backup" ...

REM Paths used by the scheduled task:
set TASK_EXE=cmd.exe
set TASK_ARGS=/c """"%~dp0backup_system\morning_backup.bat""""
REM Working directory = D:\PrintingERP\print_ERP\  (this script's dir)
set WORKDIR=%~dp0

REM Delay is controlled inside morning_backup.bat via BACKUP_STARTUP_DELAY_MINUTES (default 10),
REM but we also add a small Task Scheduler 30s delay to let the Windows
REM startup scripts settle.
schtasks /Create /TN "Printing ERP - Morning Backup" /SC ONSTART /DELAY 0000:30:00 ^
  /TR "cmd /c \"%WORKDIR%backup_system\morning_backup.bat\"" ^
  /F /RL HIGHEST 2>nul

REM Use PowerShell fallback for /DELAY not present in older schtasks versions
set TASK_OK=1
schtasks /Query /TN "Printing ERP - Morning Backup" >nul 2>&1
if %errorlevel% neq 0 (
    echo   [INFO] Trying PowerShell method for Task Scheduler ...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$action = New-ScheduledTaskAction -Execute '%WORKDIR%backup_system\morning_backup.bat' -WorkingDirectory '%WORKDIR%';" ^
      "$trigger = New-ScheduledTaskTrigger -AtStartup;" ^
      "$trigger.Delay = 'PT10M';" ^
      "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 1 -RestartInterval (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew;" ^
      "$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest;" ^
      "Register-ScheduledTask -TaskName 'Printing ERP - Morning Backup' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force" 2>nul
    schtasks /Query /TN "Printing ERP - Morning Backup" >nul 2>&1
    if %errorlevel% neq 0 set TASK_OK=0
)

if %TASK_OK%==1 (
    echo [OK] Task Scheduler task registered successfully.
    echo.
    echo   Task name : Printing ERP - Morning Backup
    echo   Trigger   : At system startup (Task Scheduler delay 30s)
    echo   + python internal delay: BACKUP_STARTUP_DELAY_MINUTES (default 10)
    echo   Action    : Run backup_system\morning_backup.bat
) else (
    echo [WARNING] Task Scheduler task could NOT be registered automatically.
    echo.
    echo How to register manually (step-by-step):
    echo   1. Open Task Scheduler (press WinKey - type Task Scheduler)
    echo   2. Right-click Task Scheduler Library -^> Create Basic Task
    echo   3. Name: "Printing ERP - Morning Backup" -^> Next
    echo   4. When do you want the task to start? Select "When the computer starts" -^> Next
    echo   5. Action: "Start a program" -^> Next
    echo   6. Program/script:  %WORKDIR%backup_system\morning_backup.bat
    echo      Start in (optional): %WORKDIR%
    echo   7. Next -^> Finish
    echo   8. Double-click the new task to open properties:
    echo        - Triggers tab -^> Edit trigger -^> check "Delay task for: 10 minutes" -^> OK
    echo        - Settings tab -^> check "Run task as soon as possible after a scheduled start is missed"
    echo        - OK
)

REM ---- 4. Run a TEST MANUAL BACKUP
echo.
echo [4/4] Running TEST MANUAL BACKUP (this will take a moment) ...
echo.
call "backup_now.bat"
set TEST_RC=%errorlevel%

echo.
echo ================================================================
echo    SETUP COMPLETE
echo ================================================================
echo.
echo Quick guide:
echo   - Manual backup : D:\PrintingERP\backup_now.bat   (double-click anytime)
echo   - Restore     : D:\PrintingERP\restore_erp.bat   (interactive menu)
echo   - Backups dir : D:\PrintingERP\backups\
echo   - Logs        : D:\PrintingERP\backups\logs\backup.log
echo   - Latest stat    : D:\PrintingERP\backups\logs\latest_backup_status.txt
echo   - Documentation: D:\PrintingERP\BACKUP_RESTORE.md
echo.
echo NOTE for morning backups:
echo   When Windows starts, the scheduled task fires:
echo     1) Waits ~10 min (BACKUP_STARTUP_DELAY_MINUTES)
echo     2) Checks if today's backup already exists
echo     3) If not, creates a verified backup
echo     4) Writes log
echo.
echo To change the delay, edit config.py or set the Windows environment variable:
echo   setx ERP_BACKUP_DELAY 5    (5 minutes instead of 10)
echo.
pause
endlocal
exit /b 0
