@echo off
setlocal enabledelayedexpansion
cls
echo ========================================
echo   PBJ Wrapped Q2 2025 - DEBUG MODE
echo ========================================
echo.
echo Current directory: %CD%
echo Script directory: %~dp0
echo.

REM Change to script directory
cd /d %~dp0
if errorlevel 1 (
    echo ERROR: Could not change to script directory!
    echo Script location: %~dp0
    pause
    exit /b 1
)

echo Changed to: %CD%
echo.

REM Check if node_modules exists
if not exist "node_modules" (
    echo Installing dependencies...
    call npm install
    if errorlevel 1 (
        echo ERROR: npm install failed!
        pause
        exit /b 1
    )
    echo.
) else (
    echo node_modules exists, skipping install
    echo.
)

REM Check if data directory exists
if not exist "public\data" (
    echo Creating public\data directory...
    mkdir "public\data"
    mkdir "public\data\json"
) else (
    echo public\data directory exists
)

REM Check if images directory exists and copy logo if needed
if not exist "public\images" (
    echo Creating public\images directory...
    mkdir "public\images"
) else (
    echo public\images directory exists
)

REM Copy logo if it doesn't exist
if not exist "public\images\phoebe-wrapped-wide.png" (
    if exist "..\phoebe-wrapped-wide.png" (
        echo Copying Phoebe logo from parent directory...
        copy "..\phoebe-wrapped-wide.png" "public\images\phoebe-wrapped-wide.png"
    ) else if exist "phoebe-wrapped-wide.png" (
        echo Copying Phoebe logo from current directory...
        copy "phoebe-wrapped-wide.png" "public\images\phoebe-wrapped-wide.png"
    ) else (
        echo WARNING: phoebe-wrapped-wide.png not found!
    )
) else (
    echo Logo file already exists
)

echo.
echo Press any key to continue with preprocessing check...
pause >nul

REM Check if JSON files exist, if not run preprocessing
if not exist "public\data\json\state_q2.json" (
    echo ========================================
    echo   Preprocessing Data Files
    echo ========================================
    echo.
    echo JSON files not found. Running preprocessing for faster loading...
    echo This will take 1-2 minutes (one-time only)...
    echo.
    call npm run preprocess
    if errorlevel 1 (
        echo.
        echo ERROR: Preprocessing failed!
        echo Please check the error messages above.
        pause
        exit /b 1
    )
    echo.
    echo ========================================
    echo   Preprocessing Complete!
    echo ========================================
    echo.
) else (
    echo JSON files found - using fast mode!
    echo.
)

echo Press any key to continue with server startup...
pause >nul

REM Check if server is running
echo Checking if server is already running...
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -Uri 'http://localhost:5173' -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1

if errorlevel 1 (
    echo Starting development server...
    echo.
    start "PBJ Wrapped Dev Server" cmd /k "cd /d %~dp0 && npm run dev"
    echo Waiting 8 seconds for server to start...
    timeout /t 8 >nul
    echo.
) else (
    echo Server is already running!
    echo.
)

echo Opening browser...
timeout /t 3 >nul
start http://localhost:5173 2>nul
if errorlevel 1 (
    echo.
    echo Could not open browser automatically.
    echo Please manually open: http://localhost:5173
    echo.
)

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Server is running at http://localhost:5173
echo.
echo Choose what to view:
echo   - USA: http://localhost:5173/wrapped/2025/usa
echo   - States: http://localhost:5173/wrapped/2025/{state-code}
echo     Example: http://localhost:5173/wrapped/2025/al
echo   - Regions: http://localhost:5173/wrapped/2025/region{1-10}
echo     Example: http://localhost:5173/wrapped/2025/region1
echo.
echo Press Ctrl+C in the server window to stop it.
echo ========================================
echo.
echo Press any key to close this window...
pause >nul


