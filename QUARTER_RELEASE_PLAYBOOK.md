# Quarter Release Playbook

This document is the canonical operational guide for PBJ quarter updates, provider-info refreshes, SFF refreshes, and live deployment safety checks.

Use this every release cycle to avoid quarter drift, inconsistent source usage, and oversized git push failures.

## Why This Exists

Recent release issues exposed repeat failure modes:

- Multiple quarter sources with different freshness (Q3 vs Q4) used by different pages.
- Confusion between snapshot provider data and quarter-keyed provider data.
- Large CSV files crossing GitHub size limits and blocking push.
- Inconsistent file paths (`templates/insights_hub.html` vs root `insights_hub.html`).
- Ad-hoc commits that mixed critical release files with unrelated local artifacts.

This playbook fixes those with one explicit pipeline and guard rails.

## Single Source of Truth Policy

### Quarter truth (PBJ longitudinal)

- **Canonical quarter file (local/full):** `facility_quarterly_metrics.csv` (gitignored; may exist via LFS history locally)
- **Deploy snapshot (committed):** `facility_quarterly_metrics_latest.csv` — built with `scripts/build_facility_quarterly_deploy_snapshot.py` (default last 8 quarters)
- **Render runtime:** build copies `_latest` → `facility_quarterly_metrics.csv` — see **`docs/DATA_DEPLOY.md`**
- **Canonical quarter field:** `CY_Qtr`
- **Required release quarter:** whatever `max(CY_Qtr)` is in canonical file

Every page that displays PBJ quarter data must trace to this source (or a generated derivative from this source).

### Provider info truth (snapshot + quarter enrichment)

- **Snapshot source:** `provider_info/ProviderInfoNorm_YYYY_MM.csv` (most recent processing date)
- **Derived web file:** `provider_info_combined_latest.csv`
- If `quarter` is blank in snapshot rows, logic must still use latest `processing_date` row per CCN.

### SFF truth

- **Source PDF:** `pbj-wrapped/public/sff-posting-with-candidate-list-<month>-<year>.pdf`
- **Derived JSONs:** `pbj-wrapped/public/sff-facilities.json`, `pbj-wrapped/public/sff-candidate-months.json`
- Document date must come from source file metadata/filename, not hardcoded month/year.

### Owners truth

- **Chain performance source:** `ownership/Nursing_Home_Chain_Performance_Measures_<Mon>_<Year>.csv`
- **Owners source:** `ownership/SNF_All_Owners_<YYYY.MM.DD>.csv`
- Runtime source label shown in UI must reflect actual file used.

## Required Folder/Path Discipline

### Runtime templates

- Keep server templates only in `templates/`.
- Do not create root duplicates for runtime templates (`insights_hub.html` in root is non-canonical).

### Data zones

- `provider_info/` = raw/snapshot upstream provider files.
- root `*_combined*.csv` = derived runtime artifacts only.
- `pbj-wrapped/public/` = static web artifacts consumed by wrapped/SFF app.
- `data/` = non-runtime working files only (never assume app reads from here unless explicitly wired).

### Exclusion zone (never release by default)

- `donor/output/*`
- `__pycache__/*`
- ad-hoc mapping scratch files (`zip_*`, `*_old.csv`, one-off analysis scripts) unless explicitly approved.

## Release Pipeline (Quarterly)

1. **Ingest PBJ source**
   - Refresh canonical `facility_quarterly_metrics.csv`.
   - Verify `max(CY_Qtr)` equals intended quarter (e.g., `2025Q4`).
   - Run `python scripts/build_facility_quarterly_deploy_snapshot.py` and commit `facility_quarterly_metrics_latest.csv` (do **not** commit the 190 MB full file).

2. **Generate downstream PBJ artifacts**
   - Regenerate `state_quarterly_metrics.csv` and `national_quarterly_metrics.csv` (and related aggregates) from canonical facility data.
   - **Required:** `python scripts/patch_state_quarterly_medians.py` — adds the six `*_Median` columns to `state_quarterly_metrics.csv` from facility-level data (`Total_Nurse_HPRD_Median`, `RN_HPRD_Median`, `Nurse_Care_HPRD_Median`, `RN_Care_HPRD_Median`, `Nurse_Assistant_HPRD_Median`, `Contract_Percentage_Median`). `/report` map median mode depends on these columns; do not skip after regenerating state metrics.
   - Regenerate state/national/search JSON artifacts.
   - Ensure homepage/search/report pages consume regenerated outputs.

3. **Refresh provider info**
   - Import latest `ProviderInfoNorm_YYYY_MM.csv`.
   - Rebuild `provider_info_combined_latest.csv`.
   - Validate sample CCNs have expected reported/case-mix values even if `quarter` blank.

4. **Refresh SFF**
   - Parse latest PDF.
   - Rebuild `sff-facilities.json` and `sff-candidate-months.json`.
   - Verify document month/year matches latest posting.

5. **Refresh owners/chain files**
   - Place latest ownership + chain performance CSVs.
   - Verify runtime source labels resolve correctly.

6. **Run pre-release validation script** (required; see guard rails below).

7. **Commit only release-scoped files** and push.

## Guard Rails (Automatable)

Add/maintain a release validation script (recommended: `scripts/validate_release.py`) with hard fails on:

- PBJ quarter mismatch:
  - `facility_quarterly_metrics.csv max(CY_Qtr)` < expected quarter.
- Cross-file mismatch:
  - state/national/search artifacts not aligned to canonical PBJ quarter.
- Provider snapshot freshness:
  - latest `processing_date` older than expected month.
- SFF date mismatch:
  - SFF JSON `document_date` not matching latest source PDF.
- Oversized Git object risk:
  - any staged non-LFS file > 100MB.
- Template path sanity:
  - root-level duplicates of runtime templates.

## Git / deploy data rules

- **Do not** commit `facility_quarterly_metrics.csv` or `provider_info_combined_latest.csv` (removed from tree; see `docs/DATA_DEPLOY.md`).
- Commit **`facility_quarterly_metrics_latest.csv`** after `build_facility_quarterly_deploy_snapshot.py` (keep under ~95 MB).
- Commit **`provider_info/ProviderInfoNorm_*.csv`** snapshots.
- Before commit: `git diff --stat` on `_latest`; build log should list multiple `CY_Qtr` values.

## Pre-Push Checklist (Go/No-Go)

- [ ] Canonical PBJ file has correct max quarter.
- [ ] `state_quarterly_metrics.csv` includes six `*_Median` columns (`python scripts/patch_state_quarterly_medians.py` after state metrics rebuild).
- [ ] Provider snapshot and case-mix values are fresh for sample CCNs.
- [ ] SFF JSONs show latest posting month/year.
- [ ] Owners source labels resolve to latest files.
- [ ] No root template duplicates shadowing `templates/`.
- [ ] No unintended local artifacts staged.
- [ ] No staged non-LFS file > 100MB.
- [ ] Smoke-test routes:
  - `/`
  - `/report`
  - `/provider/<sample_ccn>`
  - `/state/<sample_slug>`
  - `/insights`
  - `/sff/usa`

## Immediate Cleanup Tasks

1. Add `scripts/validate_release.py` and enforce in release flow.
2. Add `scripts/stage_release_files.ps1` to stage only approved release files.
3. Add CI check for staged file size and LFS pointer integrity.
4. Remove/ignore non-canonical duplicate template files from root.
5. Maintain one small `RELEASE_MANIFEST.json` that records:
   - target quarter
   - provider snapshot processing date
   - SFF posting month/year
   - owners source file names

## Naming Convention

Use this name for future reference in chats and releases:

**Quarter Release Playbook**

