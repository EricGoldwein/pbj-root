# PBJ320 public MCP

Architecture, endpoints, and operational notes for the read-only MCP research API on pbj320.com.

## Architecture

```text
CMS PBJ daily + quarterly + SNF All Owners + Provider Info
        ↓
PBJapp ingestion, normalization, day_evidence_lib (authoritative calculations)
        ↓
Approved deploy artifacts (quarterly CSVs, ownership release policy, evidence bundle)
        ↓
pbj-root canonical query layer (pbj_public_query/, ownership/, facility_provider_indexes/)
        ├── HTML pages
        ├── /api/public/*.json
        └── /mcp (thin transport → pbj_public_query)
```

**MCP handlers must not reproduce PBJ staffing or ownership calculations.** They serialize and expose canonical PBJ data/query services.

## Evidence handoff (daily)

| Stage | Location |
|-------|----------|
| Build | `PBJapp/scripts/build_public_staffing_day_evidence.py` |
| Export | `PBJapp/scripts/export_staffing_evidence_bundle_to_pbj_root.py` |
| Runtime loader | `pbj-root/staffing_evidence_bundle.py` |
| Deploy ensure | `pbj-root/scripts/ensure_staffing_evidence_bundle.py` |

Bundle layout (under data/evidence/):
- staffing_day_evidence_manifest.json  (committed — pointer + sha256)
- staffing_day_evidence.sqlite.gz      (GitHub Release asset — not in git)
- staffing_day_evidence.sqlite         (materialized at deploy)

Schema **`day_fact` (v2)**: one row per `(ccn, work_date)` with CMS hour/census inputs plus five PBJapp-precomputed HPRD floats. pbj-root looks up by `(ccn, work_date)` and **assembles** the evidence JSON for a requested metric from stored fields — it does **not** recalculate HPRD.

Employee Detail is **out of scope** for MCP v0.

Build (latest quarter example):

```powershell
cd C:\Users\egold\PycharmProjects\PBJapp
python scripts/build_public_staffing_day_evidence.py --quarters CY2026Q1
python scripts/export_staffing_evidence_bundle_to_pbj_root.py
```

## Endpoints

| Path | Purpose |
|------|---------|
| `/mcp` | MCP Streamable HTTP (GET discovery, POST JSON-RPC) |
| `/agents` | Human-facing agent overview |
| `/llms.txt` | Machine-readable site guide |
| `/api/public/provider/{ccn}.json` | Facility JSON twin |
| `/api/public/owners/{pac}.json` | Owner portfolio JSON twin |

## MCP tools

| Tool | Backing path |
|------|----------------|
| `search_facilities` | `search_index.json` + `tests/test_public_search_ranking.py` scoring + optional `facility_provider_indexes.load_latest_hprd_by_ccn` |
| `get_facility` | `load_facility_quarterly_for_provider`, `get_latest_provider_info_for_ccn`, `lookup_cms_ownership_for_provider`, `get_facility_state_percentile` |
| `compare_facilities` | `get_facility_record` × N (explicit CCNs; state percentiles when available) |
| `search_owners` | `search_public_owner_profiles` + `ownership_release_policy.active_release_date` |
| `get_owner_portfolio` | `load_owner_profile_resolved` + ownership release policy |
| `get_staffing_evidence` | `staffing_evidence_bundle.lookup_day_evidence` |

## Provenance contract

Normal tool responses are **citation-ready** (CMS source, period, canonical URL, methodology link).

`get_staffing_evidence` responses are **audit-ready** (precomputed numerator/denominator locators, source file SHA256, row ordinal when present).

## Rate limits

Environment variables:

- `PBJ_MCP_RATE_LIMIT` (default `120` requests per window per IP)
- `PBJ_MCP_RATE_WINDOW_SEC` (default `60`)
- Set `PBJ_MCP_RATE_LIMIT=0` to disable (local dev only)

## Local build & test

```powershell
# 1. Build evidence bundle (single facility dev CSV or full PBJ dir)
cd C:\Users\egold\PycharmProjects\PBJapp
python scripts/build_public_staffing_day_evidence.py `
  --facility-csv deployments/pbj320-366395/facility_366395_complete_data.csv
python scripts/export_staffing_evidence_bundle_to_pbj_root.py

cd C:\Users\egold\PycharmProjects\pbj-root
python scripts/ensure_staffing_evidence_bundle.py
python -m pytest tests/test_mcp_protocol.py tests/test_staffing_evidence_bundle.py -q
```

## Production artifact distribution (explicit)

**Strategy: GitHub Release asset + manifest pointer in git** (lowest complexity for EricGoldwein/pbj-root + Render; avoids ~68 MB in ordinary git history).

| Piece | Location |
|-------|----------|
| Pointer + integrity | `data/evidence/staffing_day_evidence_manifest.json` in git |
| Binary | GitHub Release tag `staffing-evidence-cy2026q1-v1`, asset `staffing_day_evidence_CY2026Q1.sqlite.gz` |
| Runtime | `scripts/download_staffing_evidence_bundle.py` → `ensure_staffing_evidence_bundle.py` |

**Versioning:** `artifact_id` + `distribution.release_tag` + `quarters_in_bundle` (e.g. `CY2026Q1`).

**SHA-256:** `distribution.sqlite_gz_sha256` in manifest; download verifies size + hash before gunzip; ensure verifies `COUNT(*)` vs `row_count`.

**Failure behavior:** With `PBJ_REQUIRE_STAFFING_EVIDENCE=1` (Render build), missing release, HTTP error, hash mismatch, or row-count mismatch → **build fails** (no partial substitute dataset). Without require flag, local dev skips when artifact absent.

**Rollback:** Revert manifest to prior `release_tag` + `sqlite_gz_sha256` in git; redeploy. Prior release asset remains on GitHub.

**First-time publish (manual, once per artifact version):**
```powershell
gh release create staffing-evidence-cy2026q1-v1 `
  data/evidence/staffing_day_evidence_CY2026Q1.sqlite.gz `
  --repo EricGoldwein/pbj-root --title "Staffing day evidence CY2026Q1 v1"
```
(Rename local gzip to asset name before upload if needed.)

Wire into Render `buildCommand` (when deploying): `python scripts/ensure_staffing_evidence_bundle.py` with `PBJ_REQUIRE_STAFFING_EVIDENCE=1`.

## Public extraction boundary

`get_staffing_evidence` is **not** a bulk daily-data API. Allowed inputs:

- `ccn` (required)
- `date` ISO `YYYY-MM-DD` (required)
- `metric` (optional; default `RN_HPRD`)
- `period` / `quarter` (optional; e.g. `CY2026Q1`)

Rejected (error `extraction_not_allowed`): date ranges, `all_days`, pagination (`limit`/`offset`/`page`/`cursor`), multi-facility extraction.

Optional `period`: if requested and not loaded, or row quarter differs → `evidence_unavailable_for_period`. **Never** silently substitutes another quarter. Omit `period` to return the stored day for that CCN+date when present. Schema/lookup are quarter-agnostic; future quarters are additive in the same `day_fact` table.

## Duplicate CCN/date policy

Build uses `PRIMARY KEY (ccn, work_date)` and **fails closed** on a second census>0 row for the same key (`duplicate_policy: fail_build`). Do not use last-write-wins. Resolve CMS/source duplicates upstream before shipping the public artifact.

## CCN identity

`PROVNUM` is read as string end-to-end. Float/scientific inference (e.g. `21E009` → `2.1e10`) is rejected. Valid CCNs are six-character `[0-9A-Z]{6}` after zfill.

## Production artifact handoff

See **Production artifact distribution** above. The evidence SQLite is private implementation infrastructure — not exposed via HTTP; MCP only allows single `(ccn, date, metric)` lookup.

## Deployment checklist (later — not part of this task)

1. Export approved gzip+manifest from PBJapp into pbj-root `data/evidence/`.
2. Wire `ensure_staffing_evidence_bundle.py` into Render `buildCommand` with `PBJ_REQUIRE_STAFFING_EVIDENCE=1`.
3. Smoke: `curl.exe -s -X POST http://127.0.0.1:10000/mcp -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}"`
