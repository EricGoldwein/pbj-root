# Data deploy (Render, no LFS checkout)

GitHub LFS bandwidth blocks Render from smudging large files at clone. **Full longitudinal data stays in git** as normal blobs:

| Committed file | Size (approx) | Build step |
|----------------|---------------|------------|
| `facility_quarterly_metrics.csv.gz` | ~65 MB | Decompress → `facility_quarterly_metrics.csv` (all quarters) |
| `provider_info_combined_latest.csv` | ~10 MB | Used as-is |
| `provider_info/ProviderInfoNorm_*.csv` | varies | Used as-is (newest wins in app) |

Build script: `scripts/ensure_deploy_csvs.py` (first step in `render.yaml` **and** `Procfile` start). **Fails** if fewer than 12 distinct `CY_Qtr` values after decompress.

**State pages (`/state/*`):** `python scripts/build_state_page_aggregates.py` runs after CSV materialization and writes `data/state_page_aggregates.json.gz` (facility counts, case-mix medians, rural shares, high-risk buckets for the canonical quarter). At runtime the app hydrates in-memory caches from that file; if missing or stale (CSV mtime changed), it falls back to the same compute paths as before.

If provider pages return 404 instantly, Render likely skipped the build script — confirm **Start Command** includes `python scripts/ensure_deploy_csvs.py &&` (see `Procfile`).

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
