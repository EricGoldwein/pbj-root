# PBJ Wrapped: Data and Build Layout

## Public vs dist

- **`public/`** is the **source of truth** for:
  - **SFF data**: `sff-facilities.json`, `sff_table_a.csv`–`sff_table_d.csv`, `sff-candidate-months.json`, and the CMS SFF PDF. Update these in `public/`; then run `npm run build` so `dist/` gets a copy.
  - Static assets (images, favicon, etc.) and the **quarterly JSON** tree under `public/data/json/` (see below).
- **`dist/`** is **build output**. Vite copies `public/` into `dist/` on `npm run build`. Flask serves:
  - `/data/<path>` from `pbj-wrapped/dist/data`
  - `/wrapped/<path>` and `/sff/<path>` from `pbj-wrapped/dist`
- For **SFF JSON**, Flask will serve from `dist/` first; if the file is missing there (e.g. you updated `public/` but haven’t rebuilt), it falls back to `public/` so the latest SFF data is still used.

**After updating SFF:** Run `convert-sff-csvs-to-json.py` (writes `public/sff-facilities.json`), then `npm run build` so `dist/sff-facilities.json` is updated. Optionally rely on the fallback to serve from `public/` until you rebuild.

---

## Quarterly staffing data (state, facility, regional)

- **Location:** Under `public/data/json/quarterly/` (and mirrored in `dist/data/json/quarterly/` after build):
  - **`quarterly/national/`** – `national_q1.json`, `national_q2.json`
  - **`quarterly/state/`** – `state_q1.json`, `state_q2.json`, `state_standards.json`
  - **`quarterly/region/`** – `region_q1.json`, `region_q2.json`, `region_state_mapping.json`
  - **`quarterly/facility/`** – `facility_q1.json`, `facility_q2.json`, `facility_XX_q1.json`, `facility_regionN_q1.json`, etc.
  - **`quarterly/provider/`** – `provider_q1.json`, `provider_q2.json`, `provider_XX_q1.json`, `provider_regionN_q1.json`, etc.
- **Source CSVs** (state, region, national, facility, provider) live in the repo root or `public/data/`. The script **`scripts/preprocess-data.js`** reads those CSVs and writes the JSON into both:
  - the **flat** layout `dist/data/json/*.json` (legacy, kept for now), and
  - the **organized** layout `dist/data/json/quarterly/{national,state,region,facility,provider}/`.
- The **app loads from the organized paths** (`/data/json/quarterly/...`). Old flat files in `dist/data/json/` are not deleted but are no longer used by the loader.

**Regenerating quarterly data:** From repo root, ensure CSVs are present, then run `node pbj-wrapped/scripts/preprocess-data.js`. It writes to both `dist/data/json/` (flat + `quarterly/`) and `public/data/json/quarterly/`. The app loads only from `/data/json/quarterly/...`, so preprocess must be run at least once. Then run `npm run build` in `pbj-wrapped` to refresh the app bundle; the quarterly tree in `public` is copied into `dist` so data is preserved.
