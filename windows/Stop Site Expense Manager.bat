@echo off
setlocal
title Site Expense Manager - Stop
set SEM_PORT=5555
set SEM_DATA_DIR=%USERPROFILE%\Documents\SiteExpenseManager

echo Creating a safety backup before stopping...
if exist "%SEM_DATA_DIR%\site_expense_manager.sqlite3" (
    if not exist "%SEM_DATA_DIR%\reports" mkdir "%SEM_DATA_DIR%\reports"
    powershell -NoProfile -Command ^
      "$d=Get-Date -Format 'yyyy-MM-dd_HHmmss';" ^
      "$dst=Join-Path '%SEM_DATA_DIR%\reports' ('AutoBackup_' + $d + '.zip');" ^
      "$items=@((Join-Path '%SEM_DATA_DIR%' 'site_expense_manager.sqlite3'));" ^
      "if (Test-Path (Join-Path '%SEM_DATA_DIR%' 'statements')) { $items += (Join-Path '%SEM_DATA_DIR%' 'statements') }" ^
      "if (Test-Path (Join-Path '%SEM_DATA_DIR%' 'documents')) { $items += (Join-Path '%SEM_DATA_DIR%' 'documents') }" ^
      "Compress-Archive -Path $items -DestinationPath $dst -Force;" ^
      "Write-Host ('  Auto backup saved to ' + $dst)"
)

echo.
echo Stopping Site Expense Manager on port %SEM_PORT%...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%SEM_PORT% .*LISTENING"') do (
    echo   Killing PID %%P
    taskkill /F /PID %%P >nul 2>&1
)

echo Done. Your data remains safe in %SEM_DATA_DIR%
timeout /t 2 >nul
endlocal
