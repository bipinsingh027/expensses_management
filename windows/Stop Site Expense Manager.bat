@echo off
setlocal
title Site Expense Manager - Stop
set SEM_PORT=5555

echo Stopping Site Expense Manager on port %SEM_PORT%...

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%SEM_PORT% .*LISTENING"') do (
    echo   Killing PID %%P
    taskkill /F /PID %%P >nul 2>&1
)

echo Done. Your data remains safe in %USERPROFILE%\Documents\SiteExpenseManager
timeout /t 2 >nul
endlocal
