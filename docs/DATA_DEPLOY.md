# Data deploy (Render, no LFS checkout)

GitHub LFS bandwidth blocks Render from smudging large files at clone. **Full longitudinal data stays in git** as normal blobs:

| Committed file | Size (approx) | Build step |
|----------------|---------------|------------|
| `facility_quarterly_metrics.csv.gz` | ~65 MB | Decompress → `facility_quarterly_metrics.csv` (all quarters) |
| `provider_info_combined_latest.csv` | ~10 MB | Used as-is |
| `provider_info/ProviderInfoNorm_*.csv` | varies | Used as-is (newest wins in app); backfill + validate in build |
| `provider_info/NH_ProviderInfo_*.csv` | usually **not** on Render | Gitignored except Jan/Feb 2026 whitelist — **backfill Norm before commit** |

Build script: `scripts/ensure_deploy_csvs.py` (first step in `render.yaml` `buildCommand`, **not** in start). **Fails** if fewer than 12 distinct `CY_Qtr` values after decompress (full verify on build; use `--quick` only when CSV already present).

**ProviderInfoNorm gates:** build runs `backfill_provider_norm_urban.py` then `validate_provider_norm_snapshot.py`. When paired NH is absent on Render, validate uses **self-check** fill counts on the committed Norm (CMI/urban must already be backfilled in git). Before push, run `python scripts/simulate_render_deploy_gates.py` — hides local-only `provider_info` files and re-runs those gates.

**Start command:** `python scripts/render_start.py` → Gunicorn on `0.0.0.0:$PORT` immediately. With `PBJ_SKIP_START_CSV_ENSURE=1`, restart does not re-run CSV work. **Do not** set Dashboard start to `ensure_deploy_csvs && gunicorn` — health checks get `connection refused` until Gunicorn binds (~20–30s).

**State pages (`/state/*`):** `python scripts/build_state_page_aggregates.py` runs after CSV materialization and writes `data/state_page_aggregates.json.gz` (facility counts, case-mix medians, rural shares, high-risk buckets for the canonical quarter). At runtime the app hydrates in-memory caches from that file; if missing or stale (CSV mtime changed), it falls back to the same compute paths as before.

If provider pages return 404 instantly, Render likely skipped the build script — confirm **Build Command** starts with `python scripts/ensure_deploy_csvs.py` (see `render.yaml`).

## Ownership + provider info (structural)

Provider-page **Ownership** blocks need three artifacts in sync:

| Artifact | Build |
|----------|--------|
| `ownership/SNF_All_Owners_*.csv` | CMS download (newest dated file in `ownership/`) |
| `ownership/snf_owners_lookup.sqlite` + `snf_owners_org_index.json.gz` | `python scripts/build_snf_owners_index.py` |
| `ownership/snf_owners_ccn_index.json.gz` | `python scripts/build_snf_owners_ccn_index.py` |

**Provider legal names:** `lookup_cms_ownership_for_provider` crosswalks CMS enrollment legal names to CCNs using `legal_business_name` from **`provider_info_combined_latest.csv` first**. Monthly `provider_info/ProviderInfoNorm_*.csv` (e.g. PBJapp exports) is used for Care Compare fields but often has an empty `legal_business_name` column — do not drop or stop reading the combined file when adding a new Norm export.

After any SNF owners or provider-info upload:

```powershell
python scripts/build_snf_owners_index.py
python scripts/build_snf_owners_ccn_index.py
python scripts/validate_ownership_linkage.py
```

Deploy runs the same steps via `render.yaml` and **fails the build** if validation fails.

## Updating facility metrics (quarterly release)

1. Rebuild local `facility_quarterly_metrics.csv` (full history).
2. Regenerate gzip:
   ```bash
   python -c "import gzip,shutil; shutil.copyfileobj(open('facility_quarterly_metrics.csv','rb'), gzip.open('facility_quarterly_metrics.csv.gz','wb',compresslevel=6))"
   ```
3. Commit **`facility_quarterly_metrics.csv.gz`** only (not the 190 MB raw file).
4. Deploy.

## Local dev

```bash
python scripts/ensure_deploy_csvs.py
```

Or keep your own `facility_quarterly_metrics.csv` from `git lfs pull` (old history).

## Staffing compliance bundle (PBJ daily thresholds)

Facility-quarter **counts** from PBJapp (`scripts/build_facility_quarter_staffing_compliance.py`), shipped to pbj-root for public provider pages. Flagged calendar dates stay in PBJapp only (Premium).

| Committed in pbj-root | Built at deploy |
|----------------------|-----------------|
| `data/compliance/staffing_compliance_summary.csv.gz` | Decompress → `staffing_compliance_summary.csv` |
| `data/compliance/staffing_compliance_manifest.json` | Validated (schema + quarters list) |
| `data/compliance/staffing_compliance_thresholds.json` | Config copy (labels / enabled states) |
| — | `data/compliance/staffing_compliance_index.sqlite` (ccn + quarter lookup) |

**PBJapp → pbj-root sync** (after building bundle):

```powershell
cd C:\Users\egold\PycharmProjects\PBJapp
python scripts/build_facility_quarter_staffing_compliance.py --latest-quarters 1
python scripts/export_staffing_compliance_bundle_to_pbj_root.py
cd ..\pbj-root
python scripts/ensure_staffing_compliance_bundle.py
python scripts/build_staffing_compliance_runtime_index.py
```

**Incremental quarters:** re-run the build script (parts under `PBJapp/data/compliance/parts/` are merged by quarter). Re-export gzip + manifest, commit, deploy.

**Add a state:** edit `PBJapp/config/staffing_compliance_thresholds.json` (`state_thresholds`), rebuild, re-export. No app.py branch per state.

**Skip on Render:** `PBJ_SKIP_STAFFING_COMPLIANCE_BUNDLE=1` (optional artifact; site works without it).

**Runtime:** `staffing_compliance_bundle.lookup_public_summary(ccn, quarter)`; provider takeaway shows count-only bullets when data exists.

**Post-deploy smoke (ownership + compliance pages):** `docs/ny_ct_production_playwright_qa.md` — `python scripts/audit_ny_ct_playwright.py --out scripts/_ny_ct_playwright_report.json`.
