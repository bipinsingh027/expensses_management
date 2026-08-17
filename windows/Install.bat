@echo off
setlocal
title Site Expense Manager - Install
cd /d "%~dp0.."

echo.
echo === Site Expense Manager :: First-time install ===
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [X] Python was not found in PATH.
    echo     Please install Python 3.11+ from https://www.python.org/downloads/windows/
    echo     and tick "Add Python to PATH" during installation, then run Install.bat again.
    pause
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo [X] Node.js was not found in PATH.
    echo     Please install Node.js 18 LTS from https://nodejs.org/en/download
    echo     then run Install.bat again.
    pause
    exit /b 1
)

echo [1/5] Creating Python virtual environment...
if not exist "backend\.venv" (
    python -m venv backend\.venv
    if errorlevel 1 goto :err
)

echo [2/5] Installing Python dependencies (this can take a few minutes)...
call backend\.venv\Scripts\python.exe -m pip install --upgrade pip
call backend\.venv\Scripts\pip.exe install --prefer-binary --only-binary=:all: -r backend\requirements-local.txt
if errorlevel 1 (
    echo.
    echo   Falling back to a mixed install ^(some packages may build from source^)...
    call backend\.venv\Scripts\pip.exe install --prefer-binary -r backend\requirements-local.txt
)
if errorlevel 1 goto :err

echo [3/5] Installing frontend dependencies...
pushd frontend
call npm install --no-audit --no-fund --legacy-peer-deps
if errorlevel 1 (
    popd
    goto :err
)

echo [4/5] Building the frontend for offline local use...
call npm run build
if errorlevel 1 (
    popd
    goto :err
)
popd

echo [5/5] Creating Desktop shortcuts...
set APP_DIR=%CD%
set DESKTOP=%USERPROFILE%\Desktop
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%DESKTOP%\Site Expense Manager.lnk');" ^
  "$s.TargetPath='%APP_DIR%\windows\Start Site Expense Manager.bat';" ^
  "$s.WorkingDirectory='%APP_DIR%\windows';" ^
  "$s.IconLocation='%SystemRoot%\System32\SHELL32.dll,167';" ^
  "$s.Save()" 2>nul
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%DESKTOP%\Stop Site Expense Manager.lnk');" ^
  "$s.TargetPath='%APP_DIR%\windows\Stop Site Expense Manager.bat';" ^
  "$s.WorkingDirectory='%APP_DIR%\windows';" ^
  "$s.IconLocation='%SystemRoot%\System32\SHELL32.dll,131';" ^
  "$s.Save()" 2>nul

echo.
echo === Install complete ===
echo Data folder    : %USERPROFILE%\Documents\SiteExpenseManager
echo Desktop icons  : "Site Expense Manager" and "Stop Site Expense Manager"
echo.
echo Start the app anytime by double-clicking the desktop icon.
echo.
pause
exit /b 0

:err
echo.
echo [X] Installation failed. See the messages above.
pause
exit /b 1
