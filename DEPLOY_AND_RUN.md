# How to run the PBJ site locally (including Owners / Political Contributions)

**Production deploys:** see **`DEPLOYMENT.md`** — the canonical runbook for Render settings, build pipeline, health checks (`/healthz`), smoke tests by risk level, rollback, and deploy timing. This file covers **local development** and owner-dashboard notes only.

---

## You only run one thing

- **Local:** Run `app.py` — that is the whole backend. You do **not** run `owner_donor_dashboard.py` by itself.
- **Production:** Same Flask app on Render (`pbj` web service). Start command, build steps, and smoke tests are in **`DEPLOYMENT.md`** — not duplicated here.

The owner dashboard (Political Contributions, `/owners`) is built into `app.py` and **loaded on first `/owners` visit** (lazy) so the app can bind quickly for health checks. On production, warm `/owners` after deploy if you touched owner flows — see **`DEPLOYMENT.md`** for the full post-deploy checklist (`/warmup` is readiness smoke only, not the Render health check).

---

## Local development

1. **Terminal in project root** (where `app.py` and `requirements.txt` are):

   ```powershell
   pip install -r requirements.txt
   python app.py
   ```

2. Open **http://127.0.0.1:10000** (default `PORT`; or the URL shown in the terminal).
3. Go to **http://127.0.0.1:10000/owners** for the Political Contributions page.

### Optional: FEC API key

Set a FEC API key so “View Political Contributions” works locally:

- Create `donor/.env` with: `FEC_API_KEY=your_key_here`
- Or set the env var: `$env:FEC_API_KEY = "your_key_here"` (PowerShell)

Without the key, the contributions search returns an error when you click “View Political Contributions”.

### Optional: local Gunicorn (manual testing only)

Not the Render production start command. Production uses `python scripts/render_start.py` (see **`DEPLOYMENT.md`**).

To approximate production threading locally:

```powershell
gunicorn app:app -c gunicorn_config.py
```

Bind address and port come from `gunicorn_config.py` (`PORT` env, default `10000`).

---

## Production pointers (do not configure from this doc)

| Topic | Where |
|-------|--------|
| Deploy flow, risk levels, rollback | **`DEPLOYMENT.md`** |
| Start command | `python scripts/render_start.py` (`Procfile`, `render.yaml`) |
| Health check | `/healthz` (not `/warmup`) |
| Build pipeline | `render.yaml` `buildCommand` only — includes CSV materialization, indexes, sitemap, `pbj-wrapped` build |
| Memory tuning, provider cache warming | `RENDER_DEPLOY.md` |
| CSV/index build gates | `docs/DATA_DEPLOY.md` |

### FEC on production

Set in Render Dashboard → **pbj** → Environment (details in **`DEPLOYMENT.md`** for high-risk env changes):

- **FEC_API_KEY** — required for “View Political Contributions” and FEC docquery links
- **FEC_COMMITTEE_TIMEOUT** (optional, default 120) — raise if committee loads time out
- **FEC_API_TIMEOUT** (optional, default 90)
- **FEC_SEARCH_MAX_PAGES** (optional, default 5) — lower if FEC search times out on the host

### After production deploy (owners)

If you changed owner or FEC behavior:

1. Follow the smoke checklist in **`DEPLOYMENT.md`** for your deploy risk level.
2. Optionally hit `/owners` once after `/warmup` so the first real user does not wait on lazy import.

---

## Will FEC docquery links work after push?

Yes, **if**:

1. **FEC_API_KEY** is set on the deployed site (Render env vars).
2. Users click **“View Political Contributions”** so the app fetches live FEC data.  
   Links come from that response (`committee_id` + `sub_id`). Preloaded CSV rows without those IDs get links only after a live FEC search.

Locally: `python app.py` + `FEC_API_KEY`. Production: same app via `python scripts/render_start.py` — see **`DEPLOYMENT.md`** before pushing.
