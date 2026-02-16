# How to Run and Deploy the PBJ Site (Including Owners / Political Contributions)

## You only run one thing

- **Local:** Run `app.py` — that’s the whole backend. You do **not** run `owner_donor_dashboard.py` by itself.
- **Production (e.g. Render):** The start command runs `app.py` via Gunicorn. Same single app.

The owner dashboard (Political Contributions, `/owners`) is built into `app.py` and **loaded on first `/owners` visit** (lazy) so the app can bind quickly for Render’s port check. For production, warm the owner dashboard after deploy (see "After deploy" below) so the first user doesn't wait.

---

## Local development

1. **Terminal in project root** (where `app.py` and `requirements.txt` are):
   ```bash
   pip install -r requirements.txt
   python app.py
   ```
2. Open **http://127.0.0.1:5000** (or the URL shown in the terminal).
3. Go to **http://127.0.0.1:5000/owners** for the Political Contributions page.

**Optional:** Set a FEC API key so “View Political Contributions” works:

- Create `donor/.env` with: `FEC_API_KEY=your_key_here`
- Or set the env var: `set FEC_API_KEY=your_key_here` (Windows) / `export FEC_API_KEY=your_key_here` (Mac/Linux)

Without the key, the contributions search will return an error when you click “View Political Contributions”.

---

## Deploying to Render (or similar)

### 1. Push your code

- Commit and push to GitHub (or whatever repo Render uses).
- Make sure these are in the repo and **not** ignored:
  - `app.py`
  - `requirements.txt`
  - `donor/` (including `owner_donor_dashboard.py`, `fec_api_client.py`, templates)
  - Data files you need (e.g. CSVs under `donor/output/`, `provider_info/`, `ownership/` as required by your code)

### 2. Render: create/use a Web Service

- **Build command:**  
  `pip install -r requirements.txt`
- **Start command (required so Render detects the port):**  
  `gunicorn app:app -c gunicorn_config.py`  
  The config file reads `PORT` from the environment and binds to `0.0.0.0:PORT` (avoids shell `$PORT` expansion issues that can cause "No open HTTP ports" on Render). The repo has `Procfile` and `render.yaml` with this. **Health check (required on Render):** In Render → Settings → Health Check Path, set **`/health`** so Render pings HTTP instead of port-scan only; otherwise Render may report "No open HTTP ports" and kill the service. Owner data loads on first `/owners` visit (lazy). Two workers keep the site responsive.

Render will install deps, then run that one command. That starts the same Flask app that includes the owner dashboard; no separate “backend” to run.

### 3. Set environment variables on Render

In the Render dashboard for this service:

- **FEC_API_KEY** = your FEC API key (required for “View Political Contributions” and FEC docquery links to work).
- **FEC_COMMITTEE_TIMEOUT** (optional) = seconds per request when loading committee contributions via API (default 120). If you see “FEC API may have timed out”, try `180` or higher.
- **FEC_API_TIMEOUT** (optional) = seconds for other FEC API requests (default 90). Set in env or `donor/.env`.
- **FEC_SEARCH_MAX_PAGES** (optional) = max API pages per name when searching by contributor (default 5 ≈ 500 results). Lower this if the FEC search request times out on your host (e.g. Render 30s); raise for more results.

Add any other env vars your app or data paths expect (e.g. if you load files from env).

### 4. After deploy

- Your site URL will be something like `https://your-service.onrender.com`.
- Owners / Political Contributions: **https://your-service.onrender.com/owners**
- **Warm-up (recommended):** After deploy, open or curl `https://your-service.onrender.com/owners` once so the owner dashboard is loaded. Otherwise the first visitor to `/owners` may see a slow response while the app loads. The `/health` check is side-effect free and does not trigger this load.
- When a user clicks **“View Political Contributions”**, the app calls the FEC API and shows contributions; each row that has FEC data will show a **“View on FEC”** link to the FEC docquery page.

---

## Will the FEC docquery links work after push?

Yes, **if**:

1. **FEC_API_KEY** is set on the deployed site (e.g. in Render env vars).
2. Users click **“View Political Contributions”** (or your “Search Contributions” button) so the app fetches live data from the FEC API.  
   - Links are built from that live response (`committee_id` + `sub_id`).  
   - Preloaded CSV data doesn’t have those IDs, so those rows won’t get links until you run a live FEC search.

So: run one backend (`app.py` locally, `gunicorn app:app` in production), set `FEC_API_KEY` in production, and the full process (including links) will work when you push to the site.
