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

echo [1/4] Creating Python virtual environment...
if not exist "backend\.venv" (
    python -m venv backend\.venv
    if errorlevel 1 goto :err
)

echo [2/4] Installing Python dependencies (this can take a few minutes)...
call backend\.venv\Scripts\python.exe -m pip install --upgrade pip
call backend\.venv\Scripts\pip.exe install -r backend\requirements-local.txt
if errorlevel 1 goto :err

echo [3/4] Installing frontend dependencies...
pushd frontend
call npm install --no-audit --no-fund
if errorlevel 1 (
    popd
    goto :err
)

echo [4/4] Building the frontend for offline local use...
call npm run build
if errorlevel 1 (
    popd
    goto :err
)
popd

echo.
echo === Install complete ===
echo Data folder: %USERPROFILE%\Documents\SiteExpenseManager
echo Start the app with:  "Start Site Expense Manager.bat"
echo.
pause
exit /b 0

:err
echo.
echo [X] Installation failed. See the messages above.
pause
exit /b 1
