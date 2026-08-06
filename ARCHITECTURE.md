# ARCHITECTURE.md — pbj-root / PBJ320 public site

Living index for system shape, deploy, and routing.  
**Authority:** Tier 2 — see `docs/AUTHORITY_LADDER.md`. Prefer this over scattered process notes.

## What this app is

Single Flask app (`app.py`) serving:

- Public staffing pages (facility / state / national / entity)
- Insights and PBJPedia
- Owners / political contributions (`donor/`, lazy-loaded on `/owners`)
- SFF pages and downloads (data often under `pbj-wrapped/public/` — Wrapped slideshow product is **parked**, folder still wired)
- Premium and audience surfaces

You run **one** process locally and in production: `app.py` (Gunicorn in prod).

## Local run

See `DEPLOY_AND_RUN.md`.

```powershell
pip install -r requirements.txt
python app.py
```

Default local URL is whatever the terminal prints (often `http://127.0.0.1:5000` or `:10000` depending on config).

## Production (Render)

| Item | Value |
|------|--------|
| Start | `gunicorn app:app -c gunicorn_config.py` |
| Health | **`/health`** (required; set Health Check Path in Render) |
| Blueprint | `render.yaml` / `Procfile` |
| Data gates | `docs/DATA_DEPLOY.md`, `scripts/simulate_render_deploy_gates.py` |

Memory / cache / provider warming: `RENDER_DEPLOY.md`.  
Post-deploy smoke: curl `/`, `/health`, `/provider/<ccn>`, `/search_index.json` (details in `DEPLOY_AND_RUN.md`).

## Routing (high level)

Authoritative walkthrough: `ROUTING_BREAKDOWN.md`.

| Prefix | Role |
|--------|------|
| `/`, marketing HTML | Static / template pages |
| `/provider/*`, `/state/*`, `/entity/*` | Staffing pages |
| `/owners` | FEC / donor dashboard (lazy) |
| `/sff/*`, `/downloads/sff/*` | SFF UI + PDFs/JSON from `pbj-wrapped/public` (active) |
| `/wrapped/*` | Legacy Wrapped SPA (`pbj-wrapped/dist`) — parked product, routes may still exist |
| `/api/audience/*` | Audience module |
| `/health`, `/healthz`, `/warmup` | Ops |

**Route order matter:** JSON/image/CSV and specific blueprints before broad `state_slug` / catch-alls (`ROUTING_FIXES.md` is Tier-3 history; verify in `app.py`).

## Data layers

See `FOLDER_STRUCTURE_CANON.md`.

- Upstream: `provider_info/`, `ownership/`, geo helpers
- Derived: provider indexes, compliance sqlite, wrapped JSON
- Contract: `pbj-contract/` for shared metric language

## Related products (other repos)

| Repo | Role |
|------|------|
| `PBJapp` | Premium / v2 dashboard environment |
| `320website` | 320insight.com + ops / NSU |
| `Dog-of-the-day` | Dog of Day Expo app |

Do not assume those trees are visible from this workspace.
