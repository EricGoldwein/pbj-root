# Render: "No open HTTP ports"

- **render.yaml** uses `startCommand: bash render_start.sh` so the app binds to `0.0.0.0:$PORT` (10000).
- If the deploy log shows **"No open HTTP ports detected"** or the deploy fails:
  1. **Dashboard** → pbj service → **Settings**.
  2. **Start Command**: set to exactly `bash render_start.sh` (so it matches render.yaml; Dashboard can override the YAML).
  3. **Health Check** → **Path**: `/health` → Save.
  4. **Redeploy**.
- Render may keep scanning after that message; if the health check passes, the deploy can still succeed.
