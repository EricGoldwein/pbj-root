# CMS Special Focus Facility (SFF) data

## Overview

CMS publishes a monthly **Special Focus Facility (SFF) Posting with Candidate List** PDF containing four tables:

| Table | CMS meaning | `category` in derived data |
|-------|-------------|----------------------------|
| A | Current Special Focus Facilities | `SFF` |
| B | Graduated from SFF program | `Graduate` |
| C | No longer participating in Medicare/Medicaid | `Terminated` |
| D | SFF candidates | `Candidate` |

Active SFFs and candidates are **never collapsed** into a single flag. The app and APIs use the `category` field.

**Current release:** see `data_sources/cms/sff/current_release.json` (updated by `publish_sff_artifacts.py` after each pipeline run).

## Directory layout

```
data_sources/cms/sff/
  current_release.json          # pointer to active release + publish targets
  raw/
    YYYY-MM/
      sff-posting-with-candidate-list-<month>-<year>.pdf
      manifest.json             # sha256, ingestion date, notes

data/derived/sff/
  tables/                       # extracted intermediate CSVs (sff_table_a–d.csv)
  sff_facilities.json           # canonical app dataset
  sff_facilities.csv            # flat export mirror

scripts/sff/
  ingest_sff_release.py         # add a new raw PDF + manifest
  extract_sff_posting.py        # PDF -> tables/*.csv (pdfplumber)
  build_sff_dataset.py          # tables -> derived JSON/CSV
  publish_sff_artifacts.py      # copy derived + current PDF -> pbj-wrapped/public
  validate_sff_dataset.py       # schema, hashes, app load smoke
  run_pipeline.py               # extract -> build -> publish -> validate
  legacy/                       # deprecated PyPDF2 parsers (reference only)

pbj-wrapped/public/             # deploy-facing copies (Flask + Vite static)
  sff-facilities.json
  sff_table_*.csv
  sff-posting-with-candidate-list-<current>.pdf
```

## Ingesting a new CMS posting

1. Download the PDF from CMS (program page: `site_public_config.CMS_SFF_PROGRAM_URL`).
2. Ingest into the raw archive (preserves filename and writes `manifest.json`). Use the **actual CMS filename** (month and year vary each release):

   ```powershell
   python scripts/sff/ingest_sff_release.py path\to\sff-posting-with-candidate-list-<month>-<year>.pdf
   ```

   Example after downloading June 2026: `...\sff-posting-with-candidate-list-june-2026.pdf`. The `<month>-<year>` segment must match CMS’s naming convention.

3. Run the full pipeline from repo root:

   ```powershell
   python scripts/sff/run_pipeline.py
   ```

4. Optionally rebuild the wrapped SPA so `pbj-wrapped/dist/` picks up JSON:

   ```powershell
   cd pbj-wrapped; npm run build
   ```

## How the app consumes SFF data

| Consumer | Artifact | Notes |
|----------|----------|-------|
| `app.load_sff_facilities()` | `data/derived/sff/sff_facilities.json` (fallback: `pbj-wrapped/public/`) | Provider badges, state high-risk tabs, `/sff` SSR helpers |
| `/sff/*` React app | `pbj-wrapped/public/sff-facilities.json` (via publish) | SFF explorer UI |
| `/downloads/sff/<pdf>` | current PDF in `pbj-wrapped/public/` + raw archive | `get_sff_source_url()` → `/downloads/sff/<latest-filename>` |
| `/api/dates` | — | `sff_posting` (e.g. `Jun. 2026`) + `sff_source_url` for `/sff` page source line |
| `generate_search_index.py` | `sff_facilities.json` | Enriches search index when CSV lacks `sff_status` |

**PBJapp:** No SFF artifact export from pbj-root to PBJapp was found; dependency is internal to pbj-root only.

## PDF extraction limitations

- Extraction uses **pdfplumber** with fixed page ranges (Tables A–D). Table C rows are filtered to rows with valid termination dates; spillover onto the next page uses a text fallback.
- Table structure changes from CMS may require updating `scripts/sff/extract_sff_posting.py` page ranges or parsers.
- Manual review of row counts vs the PDF summary page is recommended after each release.

## Validation

```powershell
python scripts/sff/validate_sff_dataset.py
```

Checks manifest SHA-256, required columns/categories, CCN format, state codes, duplicate keys, document date vs latest raw PDF, and `app.load_sff_facilities()`.

## Historical raw sources

Prior postings remain under `data_sources/cms/sff/raw/YYYY-MM/` and are not overwritten when a new month is ingested.
