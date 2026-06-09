"""
Gunicorn config for Render. Binds to 0.0.0.0:PORT so Render's port scan detects the service.
Using Python to read PORT avoids shell $PORT expansion issues. Health check path /healthz
(or /health) should be set in Render so it uses HTTP GET instead of port-scan only.

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

# Default 2 workers locally; always 1 worker on Render unless PBJ_ALLOW_MULTI_WORKER=1.
try:
    _workers_default = "1" if _on_render else "2"
    workers = max(1, int(os.environ.get("PBJ_GUNICORN_WORKERS", _workers_default)))
except (TypeError, ValueError):
    workers = 1 if _on_render else 2
if _on_render and workers > 1 and not (os.environ.get("PBJ_ALLOW_MULTI_WORKER") or "").strip():
    sys.stderr.write(
        "[gunicorn] Render: forcing workers=1 (duplicate workers OOM on 2GB; "
        "set PBJ_ALLOW_MULTI_WORKER=1 to override)\n"
    )
    workers = 1

worker_class = "gthread"
# Render: 4 threads — keeps /health responsive when provider cold-renders stack up.
# CPU-heavy provider work is still gated by app-level cold slots/rate limits.
try:
    _threads_default = "4" if _on_render else "4"
    threads = max(1, int(os.environ.get("PBJ_GUNICORN_THREADS", _threads_default)))
except (TypeError, ValueError):
    threads = 4 if _on_render else 4

timeout = 120
graceful_timeout = 60  # finish in-flight requests before exit on SIGTERM (Render deploy); reduces 502s during deploy

# Worker recycle: default OFF on Render. With workers=1, max_requests>0 leaves no listener
# during fork/re-import → Render health "connection refused" / Instance failed.
# Set PBJ_GUNICORN_MAX_REQUESTS only after confirming RSS creep (e.g. 5000+).
try:
    _mr_raw = (os.environ.get("PBJ_GUNICORN_MAX_REQUESTS") or "").strip()
    max_requests = int(_mr_raw) if _mr_raw else 0
except (TypeError, ValueError):
    max_requests = 0
max_requests = max(0, max_requests)

# No --preload: each gthread worker imports app:app after fork (see post_fork / when_ready logs).


def on_starting(server):
    import time

    ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    sys.stderr.write(
        f'[gunicorn] on_starting bind={bind} workers={workers} threads={threads} '
        f'max_requests={max_requests} at {ts}\n'
    )
    sys.stderr.flush()


def post_fork(server, worker):
    import time

    ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    sys.stderr.write(
        f'[gunicorn] post_fork worker pid={worker.pid} age={worker.age} at {ts}\n'
    )
    sys.stderr.flush()


def worker_exit(server, worker):
    import time

    ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    sys.stderr.write(f'[gunicorn] worker_exit pid={worker.pid} age={worker.age} at {ts}\n')
    sys.stderr.flush()


def worker_abort(worker):
    import time

    ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    sys.stderr.write(f'[gunicorn] worker_abort pid={worker.pid} at {ts}\n')
    sys.stderr.flush()


def when_ready(server):
    """Log so Render/ops see that we're listening."""
    import time

    ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    sys.stderr.write(f"[gunicorn] Listening on {bind} at {ts}\n")
    sys.stderr.write(
        f"Owner donor dashboard loads on first /owners visit; / and /health respond immediately "
        f"({workers} x {worker_class}, threads={threads}, timeout={timeout}s).\n"
    )
    sys.stderr.flush()
