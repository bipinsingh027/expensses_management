@echo off
setlocal
title Site Expense Manager
cd /d "%~dp0.."

set SEM_PORT=5555
set SEM_DATA_DIR=%USERPROFILE%\Documents\SiteExpenseManager
set SEM_ALLOWED_ORIGINS=http://localhost:%SEM_PORT%,http://127.0.0.1:%SEM_PORT%

if not exist "backend\.venv\Scripts\python.exe" (
    echo [X] The app is not installed yet.
    echo     Please run "Install.bat" once first.
    pause
    exit /b 1
)

if not exist "frontend\build\index.html" (
    echo [X] The frontend has not been built yet.
    echo     Please run "Install.bat" once first.
    pause
    exit /b 1
)

if not exist "%SEM_DATA_DIR%" mkdir "%SEM_DATA_DIR%"

echo === Site Expense Manager ===
echo Data folder : %SEM_DATA_DIR%
echo URL         : http://localhost:%SEM_PORT%
echo.
echo Close this window (or run "Stop Site Expense Manager.bat") to stop the app.
echo Your data will remain safely stored in the data folder above.
echo.

REM Open the browser once the server is ready.
start "" cmd /c "timeout /t 3 >nul && start http://localhost:%SEM_PORT%"

REM Run the backend in the foreground so closing the window stops the server.
backend\.venv\Scripts\python.exe -m uvicorn server:app --app-dir backend --host 127.0.0.1 --port %SEM_PORT%

endlocal
