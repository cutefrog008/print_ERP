@echo off
REM ============================================================
REM  register_startup_task.bat
REM  ONE-TIME setup: register the "Printing ERP - Startup" task so
REM  start_erp.bat runs automatically every time you log in.
REM
REM  Run as a normal user (no admin needed).
REM  To undo: schtasks /Delete /TN "Printing ERP - Startup" /F
REM ============================================================

setlocal

cd /d "%~dp0"

set "TASK_NAME=Printing ERP - Startup"
set "WORKDIR=%~dp0"
set "SCRIPT=%WORKDIR%start_erp.bat"
set "LAUNCHER=%WORKDIR%start_erp_hidden.vbs"

echo.
echo ================================================================
echo    PRINTING ERP - REGISTER BOOT STARTUP TASK
echo ================================================================
echo.
echo   Task name : %TASK_NAME%
echo   Trigger   : At user logon (+ 1 minute delay)
echo   Action    : wscript.exe "%LAUNCHER%"   (runs windowless)
echo   Server    : starts in the background, Brave opens the login page
echo.
pause

if not exist "%SCRIPT%" (
    echo [ERROR] start_erp.bat not found next to this script.
    echo         Expected: %SCRIPT%
    echo.
    pause
    exit /b 1
)

if not exist "%LAUNCHER%" (
    echo [ERROR] start_erp_hidden.vbs not found next to this script.
    echo         Expected: %LAUNCHER%
    echo.
    pause
    exit /b 1
)

REM --- Remove any previous registration (idempotent) ---
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

echo [INFO] Registering scheduled task...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument '%LAUNCHER%' -WorkingDirectory '%WORKDIR%';" ^
  "$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME;" ^
  "$trigger.Delay = 'PT1M';" ^
  "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew;" ^
  "$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive;" ^
  "Register-ScheduledTask -TaskName '%TASK_NAME%' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force"

schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if %errorlevel%==0 (
    echo.
    echo ================================================================
    echo    [OK] Task registered. It will start at every logon.
    echo ================================================================
    echo.
    echo   What happens at logon:
    echo     1) Previous day's backup (IST) is checked.
    echo     2) A catch-up backup is created if that day has none.
    echo     3) The ERP starts silently on 0.0.0.0:8000 for all Wi-Fi / LAN
    echo        devices - no console window is shown.
    echo     4) Brave opens on the login page.
    echo.
    echo   Logs: startup.log ^(this folder^), backup.log ^(D:\PrintingERP\backups\logs^)
    echo.
    echo   Test it now without rebooting:
    echo     schtasks /Run /TN "%TASK_NAME%"
    echo   Stop the background server later with stop_erp.bat
) else (
    echo.
    echo [ERROR] Could not register the task automatically.
    echo.
    echo Manual steps:
    echo   1. Open Task Scheduler
    echo   2. Create Task ^(not Basic^) named "%TASK_NAME%"
    echo   3. Triggers tab - New - "At log on" - specify your user - OK
    echo   4. Actions tab - New - Start a program:
    echo        Program/script : wscript.exe
    echo        Add arguments  : "%LAUNCHER%"
    echo        Start in       : %WORKDIR%
    echo   5. Settings tab - uncheck "Stop the task if it runs longer than"
    echo   6. OK
)

echo.
pause
endlocal
exit /b 0
