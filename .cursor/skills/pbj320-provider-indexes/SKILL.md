---
name: pbj320-provider-indexes
description: >-
  Deploy-built provider SQLite/pickle indexes: schema contract, build validation,
  prod vs local CSV fallback, and pre-deploy audits for /provider cold path.
---

# PBJ320 provider indexes

Use when changing `facility_provider_indexes.py`, `build_facility_provider_indexes.py`, provider cold path in `app.py`, or Render `buildCommand`.

## Schema contract

- **One map:** `facility_provider_indexes.CSV_TO_SQLITE_COLUMNS` / `SQLITE_TO_CSV_COLUMNS`.
- **Build** renames CSV → sqlite (`csv_rename_map_for_build()`).
- **Load** must restore **`Total_Nurse_HPRD`**, `RN_HPRD`, `CY_Qtr`, etc. via `_restore_csv_column_names` before any `generate_provider_page_html` use.
- **`load_latest_hprd_by_ccn`** already emits dict keys in CSV shape — do not regress.

## Failure mode (2026-05)

SQLite had `total_nurse_hprd` but page read `Total_Nurse_HPRD` → N/A HPRD, empty charts on Render. Local worked via CSV fallback without artifacts.

## Required commands

```powershell
cd c:\Users\egold\PycharmProjects\pbj-root
python scripts/build_facility_provider_indexes.py
python scripts/validate_provider_index_schema.py
python scripts/check_provider_indexes.py
python scripts/verify_provider_fast_path.py
```

Optional broader gate: `python scripts/audit_provider_index_safety.py` (strict fast-path columns).

## Pass criteria

| Check | Pass |
|-------|------|
| Build log | `schema_validation PASS` |
| `check_provider_indexes.py` | `"ok": true`, `schema_validation_errors: []` |
| Sample CCNs (676230, 035297, 335513) | HPRD matches CSV at canonical quarter |
| `verify_provider_fast_path.py` | numeric reported HPRD in HTML; no `N/A HPRD` narrative |
| Runtime logs (Render) | `facility_quarterly_lookup` + `source=sqlite`; no `provider_df_schema_error` |

## Audits must assert values, not markers

- Wrong: `'HPRD' in html` only.
- Right: `reported <strong>\d+\.\d+ HPRD</strong>`, forbid `N/A HPRD` when data exists.
- Parity: fast path uses `strict_csv_columns=True` (see `audit_provider_index_safety.py`).

## Render

`buildCommand`: `ensure_deploy_csvs.py` → `build_facility_provider_indexes.py` → `validate_provider_index_schema.py` → pip/npm.

Artifacts are gitignored; built on every deploy (~100MB sqlite).

## Related

- Performance / Gunicorn: `.cursor/skills/pbj320-web-performance/SKILL.md`
- Agent protocol: `.cursor/rules/pbj320-agent-rules.mdc`
- Schema rule: `.cursor/rules/pbj320-provider-artifact-schema.mdc`
