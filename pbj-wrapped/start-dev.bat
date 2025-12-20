@echo off
if "%1" neq "KEEPOPEN" (
    cmd /k "%~f0" KEEPOPEN
    exit /b
)

setlocal enabledelayedexpansion
cls

echo ========================================
echo   PBJ Wrapped Q2 2025
echo ========================================
echo.

cd /d "%~dp0"
if errorlevel 1 (
    echo ERROR: Could not change to script directory!
    goto :end
)

echo Working directory: %CD%
echo.

echo [DEBUG] Line 25: Checking node_modules
if not exist "node_modules" (
    echo [DEBUG] Line 27: Installing dependencies...
    call npm install
    if errorlevel 1 (
        echo ERROR: npm install failed!
        goto :end
    )
    echo Dependencies installed
    echo.
) else (
    echo [DEBUG] Line 36: Dependencies already installed
    echo.
)

echo [DEBUG] Line 40: Creating directories
if not exist "public" (
    echo [DEBUG] Line 42: Creating public directory
    mkdir "public" 2>nul
)
if not exist "public\data" (
    echo [DEBUG] Line 46: Creating public\data directory
    mkdir "public\data" 2>nul
)
if not exist "public\data\json" (
    echo [DEBUG] Line 50: Creating public\data\json directory
    mkdir "public\data\json" 2>nul
)
if not exist "public\images" (
    echo [DEBUG] Line 54: Creating public\images directory
    mkdir "public\images" 2>nul
)

echo [DEBUG] Line 58: Checking logo
if not exist "public\images\phoebe-wrapped-wide.png" (
    if exist "..\phoebe-wrapped-wide.png" (
        echo [DEBUG] Line 61: Copying logo from parent
        copy "..\phoebe-wrapped-wide.png" "public\Aimages\phoebe-wrapped-wide.png" >nul 2>&1
        echo Logo copied
    ) else (
        if exist "phoebe-wrapped-wide.png" (
            echo [DEBUG] Line 67: Copying logo from current
            copy "phoebe-wrapped-wide.png" "public\images\phoebe-wrapped-wide.png" >nul 2>&1
            echo Logo copied
        )
    )
)

echo [DEBUG] Line 75: Checking JSON files
set "JSON_FILE=public\data\json\state_q2.json"
echo [DEBUG] Line 77: JSON_FILE variable set to %JSON_FILE%
REM Check if provider JSON files exist - if not, regenerate
REM Also check if state_q1.json exists and is not empty
if exist "%JSON_FILE%" (
    REM Also check if provider files exist (they're critical)
    if not exist "public\data\json\provider_q2.json" (
        echo Provider JSON files missing. Regenerating...
        goto :preprocess_start
    )
    REM Check if state_q1.json exists and has data (not empty)
    if not exist "public\data\json\state_q1.json" (
        echo state_q1.json missing. Regenerating...
        goto :preprocess_start
    )
    REM Check if state_q1.json is empty (0 bytes or just "[]")
    for %%F in ("public\data\json\state_q1.json") do (
        if %%~zF LEQ 10 (
            echo state_q1.json is empty. Regenerating...
            goto :preprocess_start
        )
    )
    echo [DEBUG] Line 85: JSON files found
    echo JSON files found - using fast mode!
    echo.
    goto :after_json_check
)

echo [DEBUG] Line 80: JSON files not found, starting preprocessing
goto :preprocess_start

:preprocess_start
    echo [DEBUG] Line 78: Starting preprocessing
    echo.
    echo ========================================
    echo   Preprocessing Data Files
    echo ========================================
    echo.
    echo Running preprocessing to extract Q1 and Q2 2025 data.
    echo This will take 1-2 minutes (one-time only).
    echo.
    call npm run preprocess
    set PREPROCESS_EXIT=%ERRORLEVEL%
    if %PREPROCESS_EXIT% neq 0 (
        echo.
        echo ========================================
        echo ERROR: Preprocessing failed with exit code %PREPROCESS_EXIT%!
        echo ========================================
        echo.
        echo Check the error messages above for details.
        echo Common issues:
        echo   - Missing CSV files in public\data\
        echo   - CSV files have wrong format
        echo   - Out of memory (try closing other programs)
        echo.
        goto :end
    )
    echo.
    echo Preprocessing complete
    echo.

:after_json_check

echo [DEBUG] Line 100: Checking server status
set SERVER_RUNNING=0
curl -s http://localhost:5173 >nul 2>&1
if not errorlevel 1 (
    set SERVER_RUNNING=1
)

echo [DEBUG] Line 107: SERVER_RUNNING=%SERVER_RUNNING%
if !SERVER_RUNNING!==0 (
    echo [DEBUG] Line 109: Starting server
    echo Starting development server...
    echo.
    echo NOTE: The dev server window will show compilation errors if any occur.
    echo Watch that window for TypeScript/React errors!
    echo.
    start "PBJ Wrapped Dev Server" cmd /k "cd /d %~dp0 && echo Starting Vite dev server... && npm run dev"
    echo Waiting 10 seconds for server to start and compile...
    timeout /t 10 /nobreak >nul
    
    REM Check if server started successfully
    curl -s http://localhost:5173 >nul 2>&1
    if errorlevel 1 (
        echo.
        echo WARNING: Server may not have started successfully.
        echo Check the "PBJ Wrapped Dev Server" window for errors.
        echo.
    ) else (
        echo Server appears to be running.
    )
) else (
    echo [DEBUG] Line 116: Server already running
    echo Server is already running
    echo.
    echo NOTE: If you see errors, check the dev server window.
    echo.
)

echo [DEBUG] Line 121: Opening browser
echo Opening browser...
timeout /t 2 /nobreak >nul
start http://localhost:5173 2>nul

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Server: http://localhost:5173
echo.
echo URLs to try:
echo   USA: http://localhost:5173/wrapped/2025/usa
echo   State: http://localhost:5173/wrapped/2025/al
echo   Region: http://localhost:5173/wrapped/2025/region1
echo.
echo ========================================
echo   TROUBLESHOOTING
echo ========================================
echo.
echo If the page doesn't load:
echo   1. Check the "PBJ Wrapped Dev Server" window for errors
echo   2. Open browser DevTools (F12) and check Console tab
echo   3. Look for TypeScript compilation errors
echo   4. Check Network tab for failed file loads
echo.
echo Common issues:
echo   - TypeScript errors: Check the dev server window
echo   - Missing data files: Check public\data\ directory
echo   - JSON files corrupted: Delete public\data\json\ and rerun
echo.

:end
echo.
echo Press any key to close this window...
pause >nul
pause
