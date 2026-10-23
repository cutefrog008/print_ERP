@echo off
REM ============================================================
REM  show_lan_ip.bat
REM  Display the current IPv4 LAN addresses of this computer
REM ============================================================

echo.
echo ========================================
echo   Printing ERP - Current LAN IP
echo ========================================
echo.

echo Active IPv4 addresses (non-link-local):
echo ------------------------------------------------
for /f "usebackq delims=" %%a in (`
    powershell -NoProfile -Command ^
        "Get-NetIPAddress -AddressFamily IPv4 ^
         | Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -eq 'Dhcp' -or $_.SuffixOrigin -eq 'Manual' -and $_.IPAddress -notlike '169.254.*' } ^
         | Select-Object -ExpandProperty IPAddress"
`) do (
    echo   %%a
)

echo.
echo ------------------------------------------------
echo.
echo ERP URL on the LAN (your primary LAN IP):
echo.
echo   http://192.168.1.50:8000
echo.
echo ========================================
echo.
pause
