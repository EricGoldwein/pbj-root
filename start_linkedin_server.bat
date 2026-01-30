@echo off
echo Starting server for LinkedIn video recording...
echo.
echo Open this URL in your browser:
echo http://localhost:8000/state-evolution-linkedin.html
echo.
echo Press Ctrl+C to stop the server
echo.
python -m http.server 8000
