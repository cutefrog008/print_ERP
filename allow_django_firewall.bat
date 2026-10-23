@echo off
REM ============================================================
REM  allow_django_firewall.bat
REM  Add Windows Firewall inbound rule for TCP port 8000
REM  (does NOT disable the firewall)
REM ============================================================

set "RULE_NAME=Printing ERP Django (TCP 8000)"

echo.
echo ========================================
echo   Printing ERP - Firewall Rule Setup
echo ========================================
echo.

REM Require admin
fltmc >nul 2>&1 || (
    echo [ERROR] Administrator privileges are required to modify Windows Firewall.
    echo         Please right-click this file and choose "Run as administrator".
    echo.
    pause
    exit /b 1
)

REM Remove any existing rule with the same name first (idempotent)
netsh advfirewall firewall delete rule name="%RULE_NAME%" dir=in protocol=TCP localport=8000 >nul 2>&1

REM Add the inbound rule (LAN/Wi-Fi only - scope=LocalSubnet, all profiles)
netsh advfirewall firewall add rule ^
    name="%RULE_NAME%" ^
    dir=in ^
    action=allow ^
    protocol=TCP ^
    localport=8000 ^
    profile=private,domain,public ^
    remoteip=LocalSubnet ^
    enable=yes ^
    description="Allow LAN devices to reach the Printing ERP Django server on TCP port 8000. Created by allow_django_firewall.bat."

REM --- Detect the primary LAN IPv4 address (first match wins) ---
set "LAN_IP="
for /f "tokens=2 delims=:(" %%a in ('ipconfig ^| findstr /i "IPv4"') do if not defined LAN_IP set "LAN_IP=%%a"
if defined LAN_IP set "LAN_IP=%LAN_IP: =%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Firewall rule added successfully.
    echo      Name      : %RULE_NAME%
    echo      Protocol  : TCP
    echo      Port      : 8000
    echo      Scope     : Local LAN / Wi-Fi only (LocalSubnet)
    echo      Profiles  : Private, Domain, Public
    echo.
    if defined LAN_IP (
        echo Other devices on the same network can now reach the ERP at:
        echo   http://%LAN_IP%:8000/login/
    ) else (
        echo Other devices on the same network can now reach the ERP at:
        echo   http://YOUR-LAN-IP:8000/login/
    )
    echo.
) else (
    echo.
    echo [ERROR] Failed to add firewall rule.
    echo.
)

pause
