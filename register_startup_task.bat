@echo off
REM ============================================================
REM  register_startup_task.bat
REM  ONE-TIME setup: register the "Printing ERP - Startup" task so
REM  start_erp.bat runs automatically at every logon AND once every
REM  day. The daily run makes sure the previous day's backup (IST) is
REM  always produced, even if the PC is never logged off / the server
REM  keeps running for days.
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
echo   Triggers  : 1) At user logon (+ 1 minute delay)
echo               2) Every day at 00:15  ("Start when available" means a
echo                  missed run happens as soon as the PC is next on)
echo   Action    : wscript.exe "%LAUNCHER%"   (runs windowless)
echo   Server    : starts in the background (no browser is opened)
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
  "$triggerLogon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME;" ^
  "$triggerLogon.Delay = 'PT1M';" ^
  "$triggerDaily = New-ScheduledTaskTrigger -Daily -At '00:15';" ^
  "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew;" ^
  "$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive;" ^
  "Register-ScheduledTask -TaskName '%TASK_NAME%' -Action $action -Trigger $triggerLogon,$triggerDaily -Settings $settings -Principal $principal -Force"

schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if %errorlevel%==0 (
    echo.
    echo ================================================================
    echo    [OK] Task registered. Runs at logon and once every day.
    echo ================================================================
    echo.
    echo   What happens on every run ^(logon or the daily 00:15 run^):
    echo     1^) Previous day's backup ^(IST^) is checked.
    echo     2^) A catch-up backup is created if that day has none.
    echo     3^) The ERP starts silently on 0.0.0.0:8000 for all Wi-Fi / LAN
    echo        devices - no console window is shown. If a server is
    echo        already running it is left untouched.
    echo.
    echo   The daily run guarantees the previous day's backup even if the
    echo   PC is never logged off. If it was off/asleep at 00:15 the run
    echo   happens as soon as the PC is next switched on.
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
