@echo off
REM Run after indiv24.parquet build completes. Re-runs top contributors and verifies Steven Stroll.
cd /d "%~dp0.."
python -m donor.top_nursing_home_contributors_2026 --top 500
echo.
python -m donor.verify_stroll_on_top
pause
