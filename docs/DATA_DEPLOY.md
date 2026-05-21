# Data deploy (Render, no LFS checkout)

GitHub LFS bandwidth blocks Render from smudging large files at clone. **Full longitudinal data stays in git** as normal blobs:

| Committed file | Size (approx) | Build step |
|----------------|---------------|------------|
| `facility_quarterly_metrics.csv.gz` | ~65 MB | Decompress → `facility_quarterly_metrics.csv` (all quarters) |
| `provider_info_combined_latest.csv` | ~10 MB | Used as-is |
| `provider_info/ProviderInfoNorm_*.csv` | varies | Used as-is (newest wins in app) |

Build script: `scripts/ensure_deploy_csvs.py` (first step in `render.yaml`). **Fails** if fewer than 12 distinct `CY_Qtr` values after decompress.

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
