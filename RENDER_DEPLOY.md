# Render: "No open HTTP ports"

- **render.yaml** now passes `--bind 0.0.0.0:${PORT}` so the port is explicit and sets `healthCheckPath: /health`.
- If deploy still hangs: **Dashboard** → your service → **Settings** → **Health Check** → set path to **`/health`** → Save → **Redeploy**.
