@echo off
cls
echo ========================================
echo   PBJ Wrapped - Preprocess Data
echo ========================================
echo.
echo This will convert CSV files to JSON for faster loading.
echo This only needs to be run once (or when data files change).
echo.
pause

echo.
echo Installing papaparse if needed...
call npm install papaparse --save-dev

echo.
echo Running preprocessing script...
call npm run preprocess

echo.
echo Done! JSON files are in public/data/json/
echo The app will now load much faster.
echo.
pause











