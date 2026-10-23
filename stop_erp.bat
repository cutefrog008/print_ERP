@echo off
REM ============================================================
REM  stop_erp.bat
REM  Stops the background Printing ERP server (TCP 8000).
REM
REM  The server is started windowless by start_erp.bat, so this
REM  is the way to shut it down again.
REM ============================================================

setlocal

echo.
echo ================================================================
echo    PRINTING ERP - STOP SERVER
echo ================================================================
echo.

powershell -NoProfile -Command ^
  "$pids = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique;" ^
  "if (-not $pids) { Write-Host '[INFO] Nothing is listening on port 8000.'; exit 0 };" ^
  "foreach ($p in $pids) { $proc = Get-Process -Id $p -ErrorAction SilentlyContinue; if ($proc) { Write-Host ('[INFO] Stopping {0} (PID {1})...' -f $proc.ProcessName, $p); Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } };" ^
  "Start-Sleep -Milliseconds 800;" ^
  "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { Write-Host '[ERROR] Port 8000 is still in use.'; exit 1 } else { Write-Host '[OK] Printing ERP server stopped.'; exit 0 }"

echo.
pause
endlocal
exit /b 0
