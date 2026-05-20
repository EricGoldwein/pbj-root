"""
Gunicorn config for Render. Binds to 0.0.0.0:PORT so Render's port scan detects the service.
Using Python to read PORT avoids shell $PORT expansion issues. Health check path /health
should be set in Render so it uses HTTP GET instead of port-scan only.
"""
import os
import sys

_PORT = os.environ.get("PORT", "10000")
try:
    _PORT = str(int(_PORT))
except (ValueError, TypeError):
    _PORT = "10000"

bind = f"0.0.0.0:{_PORT}"
workers = 2
timeout = 120
graceful_timeout = 60  # finish in-flight requests before exit on SIGTERM (Render deploy); reduces 502s during deploy

def when_ready(server):
    """Log so Render/ops see that we're listening."""
    sys.stderr.write(f"[gunicorn] Listening on {bind}\n")
    sys.stderr.write("Owner donor dashboard loads on first /owners visit; / and /health respond immediately.\n")
    sys.stderr.flush()
