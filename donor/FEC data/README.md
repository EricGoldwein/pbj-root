# FEC bulk data (donor/FEC data)

This folder holds FEC bulk files used for **committee search** and optional **candidate–committee linkage**.

## Committee master (cm*.csv)

- **cm26.csv**, **cm24.csv**, **cm22.csv**, **cm20.csv** (or named `cm26_2025_2026.csv`, etc.)  
- Used for committee name lookup and autocomplete.  
- If present here, they are used after `donor/data/fec_committee_master/` and before `donor/cm*.csv`.

## Individual contributions (indiv*.zip → indiv*.parquet)

- **indiv26.zip**, **indiv24.zip**, **indiv22.zip**, **indiv20.zip** — FEC bulk individual contributions (pipe-delimited inside zip).  
- **Build Parquet (one-time)** so committee search can use local data instead of the API (faster, no timeout for ActBlue/WinRed):

  **Option A – Full parquet** (large; processes all committees):
  ```bash
  cd donor
  python -m donor.fec_indiv_bulk build "FEC data/indiv26.zip" --out "FEC data/indiv26.parquet" --year-from 2020
  ```

  **Option B – Conduit-only extract** (smaller, faster; ActBlue + WinRed only):
  ```bash
  cd donor
  python -m donor.fec_indiv_bulk extract-conduits "FEC data/indiv26.zip" --out "FEC data/indiv26_conduits.parquet" --year-from 2020
  ```
  Extracts only ActBlue (C00401224) and WinRed (C00694323). Add more with `--committees C00401224,C00694323,C01234567`. The loader checks `indiv26_conduits.parquet` when full `indiv26.parquet` doesn't exist. Repeat for indiv24, indiv22, indiv20 if needed.

  **Option C – Owner-extract** (for Top Contributors; small, all committees):
  ```bash
  cd donor
  python -m donor.fec_indiv_bulk extract-owners "FEC data/indiv26.zip" --out "FEC data/indiv26_owners.parquet" --year-from 2020
  ```
  Streams the zip and keeps only rows where the contributor matches a nursing home owner (from `donor/output/owners_database.csv`). Output includes HMP, ActBlue, WinRed, and all committees. Small file (tens of thousands of rows vs 58M). Top Contributors prefers `indiv*_owners.parquet` when available. No full parquet needed.

  Build writes **bulk_manifest.json** with `last_updated` (YYYY-MM-DD) and row counts. The committee search UI shows **Data source: Local bulk data only** and **Local data last updated: M/D/YYYY** when results come from bulk; when from the API it shows **Data source: FEC API** and **No local bulk data used**. Transparency is explicit in both cases.

  Repeat for indiv24, indiv22, indiv20 if you have those zips.  
- **Committee search**: If `indiv26.parquet` (etc.) exists, we use local bulk only (no API). Otherwise we use the FEC API. The UI always states which source was used and, for bulk, the local data last-updated date from the manifest.

- **Export committee CSV (optional)** for ActBlue/WinRed so “download all” can be served from our server instead of the API:
  ```bash
  python -m donor.fec_indiv_bulk export --committee C00401224 --label actblue
  python -m donor.fec_indiv_bulk export --committee C00694323 --label winred
  ```
  Creates `committee_<id>_<label>_<date>.csv` and updates **bulk_manifest.json**. These CSVs are large; keep them out of git (see .gitignore).

**Requires:** `pandas`, `pyarrow` (for Parquet). Add `pyarrow` to `requirements.txt` if needed.

## Candidate–committee linkage (ccl*.zip)

- **ccl26.zip**, **ccl24.zip**, **ccl22.zip**, **ccl20.zip** — links candidate ID to committee ID (e.g. principal campaign committee).  
- Optional: used for conduit attribution (ultimate recipient committee when we have candidate_id).  
- Not yet wired; can be added to resolve candidate → committee for earmarked contributions.

## Data coverage

We use **2020 through present** for regular committees and say so in the UI. For **large/massive committees** (ActBlue, WinRed, and others): we cap bulk at **through 2024** (`BULK_MASSIVE_COMMITTEE_MAX_YEAR`). indiv26 (2025–2026) is excluded for these; use indiv24, indiv22, indiv20. The result page shows the exact years included.

**Large committee criteria:** A committee is "large" if it has ≥50,000 contributions in the parquet (FEC API would timeout). The list is in `fec_indiv_bulk.py` (`MASSIVE_COMMITTEES`). To refresh (quote path on Windows/PowerShell): `python -m donor.analyze_indiv_parquet "donor/FEC data/indiv26.parquet" --threshold 50000 --output-ids`

## Top nursing home owner contributors

Find the biggest FEC contributors who match nursing home owners, sorted by total amount:

```bash
python -m donor.top_nursing_home_contributors_2026 --top 500 [--out path/to/output.csv]
```

**Data source:** Uses all available parquet (indiv26, indiv24, indiv22, indiv20). Prefers **owner-extract parquet** (`indiv*_owners.parquet`) when available—small, all committees including HMP. Falls back to full parquet, then conduit-only. Run `extract-owners` (Option C above) to build owner parquet without a full 58M-row build.

## Analyze parquet: find massive committees

Run this to see which committees have unsustainable contribution counts (API would timeout):

```bash
python -m donor.analyze_indiv_parquet "donor/FEC data/indiv26.parquet" --threshold 50000 --top 30
```
(On Windows/PowerShell, always quote paths with spaces.)

Use `--output-ids` to print committee IDs for pasting into `MASSIVE_COMMITTEES` in fec_indiv_bulk.py. Massive committees are served only from local bulk (through `BULK_MASSIVE_COMMITTEE_MAX_YEAR`); if parquet is missing, we return "Local bulk data required" instead of trying the API.

## When you update local data

- After building parquet or exporting committee CSVs, **bulk_manifest.json** is updated with `last_updated` (today’s date). The app reads that and shows it in committee search as “Local data last updated: M/D/YYYY.”
- Optionally note the date here when you do a new build so you can remember when local data was last refreshed: **Last parquet build:** _indiv26 + indiv24_conduits_ (update when you run a new build).

## Git: what gets pushed

- **Pushed:** This README, code, and (if present) **cm*.csv** committee master files.  
- **Not pushed** (in .gitignore): **\*.parquet**, **\*.zip**, **committee_\*.csv**, **bulk_manifest.json**. Build parquet and export committee CSVs on the server or locally; do not commit the large files.  
- Optional: a small “nursing home connects” CSV with only ownership-matched rows could use a different name and be committed if desired.
