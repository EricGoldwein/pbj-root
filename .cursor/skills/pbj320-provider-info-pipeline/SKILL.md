---
name: pbj320-provider-info-pipeline
description: >-
  CMS NH_ProviderInfo → ProviderInfoNorm pipeline in PBJapp and pbj-root: normalize,
  copy, backfill, validate CMI/urban parity, and sign off provider snapshot deploys.
---

# PBJ320 provider info pipeline

Use when adding a new CMS provider snapshot, debugging missing CMI/urban/state percentiles,
or signing off `ProviderInfoNorm_*` / `provider_info_combined` deploys.

## Repos and paths

| Repo | NH raw | Norm output | Site consumes |
|------|--------|-------------|---------------|
| **PBJapp** | `provider_info/NH_ProviderInfo_*.csv` | `provider_info_normalized/ProviderInfoNorm_YYYY_MM.csv` | builds combined |
| **pbj-root** | `provider_info/NH_ProviderInfo_*.csv` (copy) | `provider_info/ProviderInfoNorm_YYYY_MM.csv` | `app.py`, reports, indexes |

**Normalizer:** `PBJapp/normalize_provider_info.py` (must exist — `run_pipeline_update.py` calls it).

**Column map:** `PBJapp/nh_provider_column_map.py` (`NH_TO_NORM`). Includes:
- `nursing_case_mix_index` ← `Nursing Case-Mix Index`
- `nursing_case_mix_index_ratio` ← `Nursing Case-Mix Index Ratio`
- `urban` ← `Urban`

## Release workflow (in order)

```powershell
cd c:\Users\egold\PycharmProjects\PBJapp
python normalize_provider_info.py --force --file May2026   # or omit --file for all new
# Copy newest Norm + NH to pbj-root (copy_to_pbj_root.ps1 or manual)
cd c:\Users\egold\PycharmProjects\pbj-root
python scripts/backfill_provider_norm_urban.py
python scripts/validate_provider_norm_snapshot.py
python scripts/simulate_render_deploy_gates.py
```

**Do not commit or deploy** a new `ProviderInfoNorm_*` until all three exit 0.

### Local vs Render (common agent mistake)

- **Local:** `NH_ProviderInfo_May2026.csv` may exist on disk but is **gitignored** → NH parity validate passes locally.
- **Render:** only **tracked** files exist → gates must pass with Norm **self-check** (or NH must be whitelisted in `.gitignore` and committed).
- **`simulate_render_deploy_gates.py`** hides untracked `provider_info/*` and re-runs backfill + validate — run this before push, not only local validate.

## Mandatory parity checks (before any UI/runtime fix)

When user reports “CMI shows on page but percentile missing” or similar **contradictory symptoms**:

1. **Stop** — do not add runtime fallbacks until upstream data is inspected.
2. Count non-null per source for the **same quarter**:

```powershell
cd c:\Users\egold\PycharmProjects\pbj-root
python -c "
import pandas as pd
for p in ['provider_info/ProviderInfoNorm_2026_05.csv','provider_info/NH_ProviderInfo_May2026.csv','provider_info_combined_latest.csv']:
 df=pd.read_csv(p, low_memory=False, nrows=0); print(p, 'has CMI col', 'nursing_case_mix_index' in df.columns or 'Nursing Case-Mix Index' in df.columns)
"
python scripts/validate_provider_norm_snapshot.py
```

3. Record fill counts in the response (`Verified from:` path + counts).
4. Fix **pipeline/data first**; runtime fallback is a safety net only.

## Critical columns (must match NH ≥90%)

- `nursing_case_mix_index`
- `nursing_case_mix_index_ratio`
- `urban`

Case-mix **HPRD** columns can be populated while CMI is null — that pattern means the Norm file was built without `NH_TO_NORM` CMI mapping, not that CMS dropped CMI.

## Spot checks

| CCN | Expect |
|-----|--------|
| `015009` (Burns, AL) | `nursing_case_mix_index` ≈ 1.38 when NH May has CMI |

State percentile needs ≥15 in-state and ≥30 national non-null CMI values for the target quarter in the **reference** snapshot (`app.py` `_pick_cmi_reference_source_path`).

## Gates

| Gate | Command | Blocks |
|------|---------|--------|
| Backfill | `python scripts/backfill_provider_norm_urban.py` | empty urban/CMI on newest Norm |
| Validate | `python scripts/validate_provider_norm_snapshot.py` | under-filled Norm vs NH |
| Deploy sim | `python scripts/simulate_render_deploy_gates.py` | push would fail Render build |
| Deploy | `ensure_deploy_csvs.py` runs backfill + validate | Render build |

## Common failure modes

1. **`normalize_provider_info.py` missing** — Norm copied manually; partial columns only.
2. **Backfill scoped to one field** — e.g. urban-only fix left CMI at 0%.
3. **Two data paths** — facility CMI from `provider_info_combined`; percentiles from `ProviderInfoNorm_*` — fixes one path mask the other.
4. **Newest-first without fallback** — code read May Norm, got 0 peers, stopped (fixed in `app.py` but data fix still required).
5. **Agent skipped verification** — assumed “data not there” without counting NH vs Norm rows.
6. **Local-only NH masked deploy** — validate passed with May NH on disk; Render had no NH → build failed. Always run `simulate_render_deploy_gates.py` before push when adding deploy gates.

## PBJapp normalizer hard-fail

`normalize_provider_info.py` exits non-zero when Norm CMI fill &lt; 90% of NH. Re-run with `--force` after fixing `nh_provider_column_map.py`.
