# Render deploy: "No open HTTP ports" fix

If your deploy fails with **"No open HTTP ports detected"** or **"Port scan timeout reached"**:

1. Open **Render Dashboard** → your **pbj** web service.
2. Go to **Settings** → **Health Check**.
3. Set **Health Check Path** to **`/health`** (no trailing slash).
4. Save and **Redeploy**.

Render will then use HTTP GET requests to `http://<your-service>:PORT/health` instead of relying only on a port scan. The app responds with `200 OK` on `/health` as soon as Gunicorn is listening, so the deploy can succeed.

- If you created the service from this repo’s **Blueprint** (`render.yaml`), `healthCheckPath: /health` is already in the spec; re-applying the Blueprint or creating a new service from it will set this.
- If you created the service manually (e.g. "New Web Service" and then connected the repo), you must set Health Check Path in the dashboard as above.

The app binds to `0.0.0.0:PORT` via `gunicorn_config.py`; Render sets `PORT` (often 10000). The `/health` route in `app.py` is lightweight and does not load the owner dashboard.
