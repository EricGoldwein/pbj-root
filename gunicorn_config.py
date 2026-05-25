"""
Gunicorn config for Render. Binds to 0.0.0.0:PORT so Render's port scan detects the service.
Using Python to read PORT avoids shell $PORT expansion issues. Health check path /health
should be set in Render so it uses HTTP GET instead of port-scan only.

Render stability: one worker, few gthread threads — cold /provider renders are CPU-bound
(pandas CSV scans). Extra threads increase concurrent cold work and OOM risk (status 137).
Override with PBJ_GUNICORN_WORKERS / PBJ_GUNICORN_THREADS.
"""
import os
import sys

_PORT = os.environ.get("PORT", "10000")
try:
    _PORT = str(int(_PORT))
except (ValueError, TypeError):
    _PORT = "10000"

bind = f"0.0.0.0:{_PORT}"

_on_render = bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"))

# Default 2 workers locally; 1 worker on Render to avoid duplicate pandas indexes per process.
try:
    _workers_default = "1" if _on_render else "2"
    workers = max(1, int(os.environ.get("PBJ_GUNICORN_WORKERS", _workers_default)))
except (TypeError, ValueError):
    workers = 1 if _on_render else 2

worker_class = "gthread"
# Render: 2 threads — enough for health/static while one thread runs a cold provider render.
try:
    _threads_default = "2" if _on_render else "4"
    threads = max(1, int(os.environ.get("PBJ_GUNICORN_THREADS", _threads_default)))
except (TypeError, ValueError):
    threads = 2 if _on_render else 4

timeout = 120
graceful_timeout = 60  # finish in-flight requests before exit on SIGTERM (Render deploy); reduces 502s during deploy


def when_ready(server):
    """Log so Render/ops see that we're listening."""
    sys.stderr.write(f"[gunicorn] Listening on {bind}\n")
    sys.stderr.write(
        f"Owner donor dashboard loads on first /owners visit; / and /health respond immediately "
        f"({workers} x {worker_class}, threads={threads}).\n"
    )
    sys.stderr.flush()
