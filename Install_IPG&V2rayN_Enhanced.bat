@echo off
REM ===============================================
REM  Enhanced Google Drive downloader with Tailscale cleanup
REM  Target: %ProgramData%\ATT\IP-Guard\ and \v2rayN\
REM  Auto-elevates to Administrator if needed.
REM  Includes silent Tailscale uninstallation and cleanup.
REM  Tries PowerShell -> curl -> BITS -> certutil.
REM  Adds basic verification (size>0 and HTML detection).
REM ===============================================

setlocal EnableExtensions EnableDelayedExpansion

REM -------- Auto-elevate to Administrator --------
>nul 2>&1 net session
if %errorlevel% NEQ 0 (
  echo [*] Dang yeu cau quyen Administrator...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '%*' -Verb RunAs"
  exit /b
)

REM -------- Enhanced Config --------
set "BASE_DIR=%ProgramData%\ATT"
set "DIR_IPGUARD=%BASE_DIR%\IP-Guard"
set "DIR_V2RAYN=%BASE_DIR%\v2rayN"

set "URL_IPGUARD=https://drive.usercontent.google.com/download?id=1Ztxr0dBHSPbbBzjBuWLQevEnmBE3did4&export=download"
set "URL_V2RAYN=https://drive.usercontent.google.com/download?id=1J1UpPDgFJEoIyH4mZ9xU0hCH_ZF7Roaa&export=download"

REM Change output filenames if you want
set "FILE_IPGUARD=IP-Guard_setup.exe"
set "FILE_V2RAYN=v2rayN.zip"

REM Tailscale cleanup settings
set "CLEANUP_LOGS=1"
set "REMOVE_ATT_DIR=1"
set "SILENT_UNINSTALL=1"

echo.
echo ===============================================
echo  ENHANCED INSTALLER WITH TAILSCALE CLEANUP
echo ===============================================
echo.

REM -------- Step 1: Silent Tailscale Uninstallation --------
echo === Buoc 1: Kiem tra va go cai dat Tailscale ===
call :UninstallTailscale
if errorlevel 1 (
    echo [WARNING] Co loi trong qua trinh go cai dat Tailscale
    echo Tiep tuc voi qua trinh tai xuong...
)

echo.
echo === Buoc 2: Tao thu muc dich ===
call :EnsureDir "%DIR_IPGUARD%" || goto :fail
call :EnsureDir "%DIR_V2RAYN%"  || goto :fail

echo.
echo === Buoc 3: Tai tep IP-Guard ===
call :Download "%URL_IPGUARD%" "%DIR_IPGUARD%\%FILE_IPGUARD%"
if errorlevel 1 goto :fail

echo.
echo === Buoc 4: Tai tep v2rayN ===
call :Download "%URL_V2RAYN%" "%DIR_V2RAYN%\%FILE_V2RAYN%"
if errorlevel 1 goto :fail

echo.
echo === Buoc 5: Lam sach he thong ===
call :FinalCleanup

echo.
echo ===============================================
echo [SUCCESS] Hoan tat tat ca cac buoc!
echo ===============================================
echo  - "%DIR_IPGUARD%\%FILE_IPGUARD%"
echo  - "%DIR_V2RAYN%\%FILE_V2RAYN%"
echo  - Da lam sach Tailscale va cac thanh phan lien quan
echo ===============================================
exit /b 0

:fail
echo.
echo ===============================================
echo [FAIL] Co loi xay ra trong qua trinh cai dat.
echo Vui long kiem tra ket noi/Proxy/Firewall va thu lai.
echo ===============================================
exit /b 1

REM ===================== TAILSCALE UNINSTALLER =====================

:UninstallTailscale
REM Silent Tailscale uninstallation with comprehensive cleanup
echo [INFO] Bat dau go cai dat Tailscale...

REM Stop all Tailscale processes and services
call :StopTailscaleProcesses

REM Remove scheduled tasks
call :RemoveScheduledTasks

REM Uninstall Tailscale MSI
call :UninstallTailscaleMSI

REM Remove registry entries
call :RemoveRegistryEntries

REM Remove application files and directories
call :RemoveApplicationFiles

REM Clean up temporary files
call :CleanupTempFiles

echo [INFO] Hoan tat go cai dat Tailscale
exit /b 0

:StopTailscaleProcesses
echo [INFO] Dang dung cac tien trinh Tailscale...

REM Stop Tailscale service silently
sc stop Tailscale >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Da dung dich vu Tailscale
) else (
    echo [INFO] Dich vu Tailscale khong chay hoac da dung
)

REM Kill any remaining processes silently
taskkill /f /im tailscale.exe >nul 2>&1
taskkill /f /im tailscaled.exe >nul 2>&1
taskkill /f /im att_tailscale_watchdog.exe >nul 2>&1

REM Kill Python processes running watchdog
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python.exe" /fo csv ^| findstr "att_tailscale"') do (
    taskkill /f /pid %%i >nul 2>&1
)

echo [INFO] Da dung tat ca cac tien trinh Tailscale
timeout /t 2 /nobreak >nul
exit /b 0

:RemoveScheduledTasks
echo [INFO] Dang xoa cac tac vu da lap lich...

REM Remove ATT Tailscale Watchdog task
schtasks /delete /tn "ATT_Tailscale_Watchdog" /f >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Da xoa tac vu: ATT_Tailscale_Watchdog
)

REM Remove any other related tasks
schtasks /delete /tn "Tailscale*" /f >nul 2>&1
schtasks /delete /tn "*ATT*" /f >nul 2>&1

exit /b 0

:UninstallTailscaleMSI
echo [INFO] Dang go cai dat Tailscale MSI...

REM Use PowerShell to find and uninstall Tailscale MSI
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$apps = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*' | Where-Object { $_.DisplayName -like '*Tailscale*' -and $_.DisplayName -notlike '*Standalone*' };" ^
  "foreach ($app in $apps) {" ^
  "  if ($app.UninstallString -match 'msiexec\.exe /x\s+(\{[^}]+\})') {" ^
  "    $guid = $matches[1];" ^
  "    Write-Host '[INFO] Go cai dat Tailscale MSI: ' $app.DisplayName;" ^
  "    Start-Process -FilePath 'msiexec.exe' -ArgumentList '/x', $guid, '/quiet', '/norestart' -Wait -WindowStyle Hidden;" ^
  "  }" ^
  "}"

exit /b 0

:RemoveRegistryEntries
echo [INFO] Dang xoa cac muc registry...

REM Remove registry entries silently
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\TailscaleStandalone" /f >nul 2>&1
reg delete "HKLM\SOFTWARE\Tailscale" /f >nul 2>&1
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\TrayNotify" /f >nul 2>&1

REM Remove user-specific entries
reg delete "HKCU\SOFTWARE\Tailscale" /f >nul 2>&1

exit /b 0

:RemoveApplicationFiles
echo [INFO] Dang xoa cac tep ung dung...

REM Remove Tailscale installation directory
if exist "C:\Program Files\Tailscale" (
    rmdir /s /q "C:\Program Files\Tailscale" >nul 2>&1
    echo [INFO] Da xoa thu muc Tailscale
)

REM Remove or clean ATT directory based on settings
if "%REMOVE_ATT_DIR%"=="1" (
    if exist "C:\ProgramData\ATT" (
        rmdir /s /q "C:\ProgramData\ATT" >nul 2>&1
        echo [INFO] Da xoa hoan toan thu muc ATT
    )
) else (
    REM Keep some directories but remove watchdog files
    if exist "C:\ProgramData\ATT\Logs" (
        if "%CLEANUP_LOGS%"=="1" (
            del /f /q "C:\ProgramData\ATT\Logs\*tailscale*" >nul 2>&1
            del /f /q "C:\ProgramData\ATT\Logs\att_*" >nul 2>&1
            echo [INFO] Da xoa cac log Tailscale
        )
    )
    
    REM Remove watchdog files
    if exist "C:\ProgramData\ATT\src" (
        del /f /q "C:\ProgramData\ATT\src\att_tailscale_watchdog.py" >nul 2>&1
        del /f /q "C:\ProgramData\ATT\src\*tailscale*" >nul 2>&1
    )
    
    REM Remove config files
    if exist "C:\ProgramData\ATT\Config" (
        del /f /q "C:\ProgramData\ATT\Config\*tailscale*" >nul 2>&1
        del /f /q "C:\ProgramData\ATT\Config\config.json" >nul 2>&1
        del /f /q "C:\ProgramData\ATT\Config\auth_key.encrypted" >nul 2>&1
    )
)

REM Remove shortcuts
del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Tailscale*.lnk" >nul 2>&1
del /f /q "%USERPROFILE%\Desktop\Tailscale*.lnk" >nul 2>&1

exit /b 0

:CleanupTempFiles
echo [INFO] Dang lam sach cac tep tam thoi...

REM Clean up temporary files
del /f /q "%TEMP%\tailscale*" >nul 2>&1
del /f /q "%TEMP%\att_tailscale*" >nul 2>&1
del /f /q "%TEMP%\*tailscale*" >nul 2>&1

REM Clean up Python cache if exists
if exist "%TEMP%\__pycache__" (
    rmdir /s /q "%TEMP%\__pycache__" >nul 2>&1
)

REM Clean up pip cache related to our installations
pip cache purge >nul 2>&1

exit /b 0

:FinalCleanup
echo [INFO] Thuc hien lam sach cuoi cung...

REM Verify removal
call :VerifyRemoval

REM Additional cleanup
call :CleanupTempFiles

REM Restart Windows Explorer to refresh system tray
taskkill /f /im explorer.exe >nul 2>&1
start explorer.exe

echo [INFO] Hoan tat lam sach he thong
exit /b 0

:VerifyRemoval
echo [INFO] Kiem tra qua trinh go cai dat...

set "ISSUES_FOUND=0"

REM Check for remaining processes
tasklist /fi "imagename eq tailscale*" 2>nul | findstr /i "tailscale" >nul
if not errorlevel 1 (
    echo [WARNING] Van con tien trinh Tailscale dang chay
    set "ISSUES_FOUND=1"
)

REM Check for remaining directories
if exist "C:\Program Files\Tailscale" (
    echo [WARNING] Thu muc Tailscale van ton tai
    set "ISSUES_FOUND=1"
)

if "%ISSUES_FOUND%"=="0" (
    echo [INFO] Kiem tra thanh cong: Tat ca cac thanh phan da duoc go bo
) else (
    echo [WARNING] Mot so thanh phan co the chua duoc go bo hoan toan
)

exit /b 0

REM ===================== ORIGINAL HELPERS =====================

:EnsureDir
REM Create directory if not exists
setlocal
set "D=%~1"
if not exist "%D%" (
  mkdir "%D%" 2>nul
  if errorlevel 1 (
    echo [ERROR] Khong the tao thu muc "%D%".
    endlocal & exit /b 1
  )
)
endlocal & exit /b 0

:Download
REM Usage: call :Download "URL" "OUTFILE"
setlocal
set "URL=%~1"
set "OUT=%~2"

echo -> URL: %URL%
echo -> OUT: %OUT%

REM Delete old temp if exist
if exist "%OUT%" del /f /q "%OUT%" >nul 2>&1

REM ---- 1) PowerShell (Invoke-WebRequest then WebClient fallback) ----
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$u=$args[0]; $o=$args[1]; $ProgressPreference='SilentlyContinue';" ^
  "try {" ^
  "  [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
  "  Invoke-WebRequest -Uri $u -OutFile $o -UseBasicParsing -MaximumRedirection 10; exit 0" ^
  "} catch {" ^
  "  try { (New-Object Net.WebClient).DownloadFile($u,$o); exit 0 } catch { exit 1 }" ^
  "}" ^
  "%URL%" "%OUT%"
if not errorlevel 1 goto :verify

REM ---- 2) curl (Windows 10+ / Server 2019+) ----
where curl.exe >nul 2>&1
if not errorlevel 1 (
  curl.exe -L "%URL%" -o "%OUT%"
  if not errorlevel 1 goto :verify
)

REM ---- 3) BITS (legacy) ----
where bitsadmin >nul 2>&1
if not errorlevel 1 (
  bitsadmin /transfer gdl /download /priority normal "%URL%" "%OUT%" >nul 2>&1
  if not errorlevel 1 goto :verify
)

REM ---- 4) certutil (last resort) ----
where certutil >nul 2>&1
if not errorlevel 1 (
  certutil.exe -urlcache -split -f "%URL%" "%OUT%" >nul 2>&1
  if not errorlevel 1 goto :verify
)

echo    [ERROR] Khong the tai tep bang cac phuong thuc co san.
endlocal & exit /b 1

:verify
REM Basic validation: file exists, size > 0, not obvious HTML
if not exist "%OUT%" (
  echo    [ERROR] Tep chua ton tai sau khi tai.
  endlocal & exit /b 1
)

for %%I in ("%OUT%") do set "SZ=%%~zI"
if "!SZ!"=="0" (
  echo    [ERROR] Tep co kich thuoc 0 bytes.
  del /f /q "%OUT%" >nul 2>&1
  endlocal & exit /b 1
)

REM Check if the downloaded file appears to be HTML (common when Drive chan/quota)
findstr /I /M "<html" "%OUT%" >nul 2>&1
if not errorlevel 1 (
  echo    [ERROR] Noi dung giong HTML (co the bi chan/hoac can dang nhap). Xoa tep.
  del /f /q "%OUT%" >nul 2>&1
  endlocal & exit /b 1
)

echo    [OK] Da tai xong (size !SZ! bytes)
endlocal & exit /b 0
