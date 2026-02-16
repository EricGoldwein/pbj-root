# Donor Pipeline – Quick Run

## Prerequisites

- `donor/output/owners_database.csv` (from `build_schedule_a_docquery.py`)
- FEC data: either indiv*.zip OR indiv*.parquet in `donor/FEC data/`

## One-Click (Windows)

```bat
donor\run_donor_pipeline.bat
```

Runs: extract-owners (if zip exists) → top contributors → verify Stroll.

## Manual Steps

### 1. Build owner-extract parquet (optional; if you have indiv*.zip)

```bat
python -m donor.fec_indiv_bulk extract-owners "donor/FEC data/indiv26.zip" --out "donor/FEC data/indiv26_owners.parquet"
python -m donor.fec_indiv_bulk extract-owners "donor/FEC data/indiv24.zip" --out "donor/FEC data/indiv24_owners.parquet"
```

Small output, all committees (HMP, ActBlue, WinRed). No full 58M-row parquet needed.

### 2. Run top contributors

```bat
python -m donor.top_nursing_home_contributors_2026 --top 500
```

Output: `donor/FEC data/top_nursing_home_contributors_2026.csv`

### 3. Verify (optional)

```bat
python -m donor.verify_stroll_on_top
```

## Data Priority

Top contributors uses (in order):
1. `indiv*_owners.parquet` (owner-extract; preferred)
2. `indiv*.parquet` (full)
3. `indiv*_conduits.parquet` (ActBlue/WinRed only)

If you only have full parquet or conduit parquet, step 2 still works.
