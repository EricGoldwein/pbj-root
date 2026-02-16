"""
Gunicorn config for Render. Binds to 0.0.0.0:PORT so Render's port scan detects the service.
Using Python to read PORT avoids shell $PORT expansion issues.
"""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
workers = 2
timeout = 120
