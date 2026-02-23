#!/usr/bin/env bash
# Render: bind to PORT so health check and port scan see the app.
PORT="${PORT:-10000}"
exec gunicorn app:app -c gunicorn_config.py --bind "0.0.0.0:${PORT}"
