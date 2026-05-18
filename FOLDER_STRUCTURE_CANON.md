# Folder Structure Canon

Use this as the canonical map for where files belong.

## Runtime (served by app)

- `app.py` and `templates/`
- root runtime data artifacts consumed by routes:
  - `facility_quarterly_metrics.csv`
  - `state_quarterly_metrics.csv`
  - `national_quarterly_metrics.csv`
  - `provider_info_combined_latest.csv`
  - `search_index.json`, `*_historical_data.json`, etc.
- `pbj-wrapped/public/` for wrapped/SFF static data assets

## Upstream / Raw Inputs

- `provider_info/` for ProviderInfoNorm snapshots
- `ownership/` for ownership/chain source CSVs
- `data/geo/` for geo/state helper inputs
- source PDFs/zips should stay outside runtime paths until processed

## Derived / Generated

- generated JSONs and merged CSVs used by app
- SFF derived outputs:
  - `pbj-wrapped/public/sff-facilities.json`
  - `pbj-wrapped/public/sff-candidate-months.json`

## Local Artifacts (not for release)

Ignored by `.gitignore`:

- `donor/output/`
- one-off mapping files (`zip_*`, `prov_info_quarter_map.py`, etc.)
- duplicate template drafts at repo root (canonical templates are in `templates/`)

## Rule of Thumb

If a file is required for live routes, it must have one canonical location and be referenced from exactly one loader path in code.

