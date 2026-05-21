# Git LFS bandwidth — pbj-root (May 2026)

## What hit the 10 GB limit

From GitHub usage export (`usageReport_*.csv`), **bandwidth** (not storage) for **pbj-root**:

| Source | GB | Share |
|--------|-----|-------|
| **render[bot]** (Render deploy clones) | **~9.87** | **99%** |
| Other / unknown | ~0.05 | 1% |
| EricGoldwein (local) | ~0.004 | 0% |
| **Total** | **~9.93** | 100% |

**Recent perf commits (`53c6698`, `2f3ac7d`) did not add or change LFS files.** They only triggered more **deploy attempts** (each clone re-downloads LFS blobs).

## LFS files in this repo (`.gitattributes`)

| File | ~size | Needed on Render? |
|------|-------|------------------|
| `facility_quarterly_metrics.csv` | **~190 MB** | **Yes** — core app data |
| `provider_info_combined_latest.csv` | large | Yes — provider/report paths |
| `provider_info_combined.csv` | (tracked in attributes) | fallback paths |

Every successful or **failed** Render `git clone` + LFS smudge re-pulls these objects → ~3 GB bandwidth per full fetch (observed: 3.65 + 3.10 + 2.91 GB spikes ≈ **4 deploys** in a few days).

Failed deploy **retries** (LFS budget exceeded → smudge error → retry clone) burn quota without shipping code.

## Definite waste (actionable)

1. **Auto-deploy on every small push** — batch commits; deploy only when you need production live.
2. **Retry storms** — fix LFS budget before pushing again; pause Render auto-deploy while blocked.
3. **Re-committing LFS CSVs** — never `git add facility_quarterly_metrics.csv` unless the file actually changed; local edits to `facility_quarterly_metrics_latest.csv` are **not** LFS (safe) but don’t commit multi‑hundred‑MB files without intent.
4. **Other repos on the same org** (PBJsearch, pbj, sample-pbj) — storage charges add up; bandwidth for **pbj-root** is almost entirely Render.

## Not the problem

- Phoebe WebP, GPT rate limit, report.html, `app.py` UI fixes — **no LFS**.
- SNF owners SQLite/CSV in `ownership/` — normal git, not LFS.

## Unblock production now

### Real fix (May 2026): stop tracking LFS files at `HEAD`

Render runs **git checkout before** build env vars apply, so `GIT_LFS_SKIP_SMUDGE` in `render.yaml` does **not** stop the smudge error.

| Change | Why |
|--------|-----|
| **`git rm` LFS paths** | `facility_quarterly_metrics.csv`, `provider_info_combined_latest.csv` removed from the tree so checkout never downloads them. |
| **Commit `facility_quarterly_metrics_latest.csv` only** | Normal git (~5 MB, current quarter). |
| **`python scripts/ensure_deploy_csvs.py`** | Build copies `_latest` → `facility_quarterly_metrics.csv` for app paths that expect that filename. |
| **Provider data** | **`provider_info/ProviderInfoNorm_2026_04.csv`** in normal git; app prefers Norm over combined CSVs. |

`GIT_LFS_SKIP_SMUDGE` in `render.yaml` is harmless extra insurance; the checkout fix is **not having LFS paths in HEAD**.

**Data caveat:** Deploy uses `_latest` (currently **2025Q4** on `master`) + pinned Norm, not the 190 MB full-history LFS file. Provider trend charts that read multi-quarter history from `facility_quarterly_metrics.csv` will only have the quarters present in `_latest` until LFS is available again or you host the full file elsewhere.

### Deploy checklist (auto-deploy OFF)

1. **Pause auto-deploy** on Render (you already did).
2. **Push** only the LFS deploy commit (`render.yaml`, `scripts/ensure_deploy_csvs.py`, this doc).
3. **Render → Environment:** add `GIT_LFS_SKIP_SMUDGE` = `1` if not already present.
4. **Render → Settings → Build Command** must start with `python scripts/ensure_deploy_csvs.py` (match `render.yaml` if Blueprint-managed).
5. **Manual Deploy** once. In build logs, expect:
   - `ensure_deploy_csvs: copied facility_quarterly_metrics_latest.csv -> facility_quarterly_metrics.csv`
   - `ensure_deploy_csvs: OK provider_info/ProviderInfoNorm_2026_04.csv`
6. Smoke-test `/health`, `/provider/075263`, `/report`. Re-enable auto-deploy only after one green deploy.

### Other options

| Option | Safe? | Effect |
|--------|-------|--------|
| **Wait for LFS reset** (Jun 1) | Yes | Deploy with LFS again; no code change |
| **Buy LFS bandwidth** | Yes | Immediate |
| **Pause auto-deploy** | Yes | Stops retry burn |
| **`$0` LFS budget** | Yes for $ | Blocks overage; **does not** deploy by itself |
| **`git lfs migrate export`** | **Risky** | History rewrite; huge files become normal git blobs; team coordination |

## Suggestion checklist (from advisory)

| Suggestion | Verdict |
|------------|---------|
| `git lfs install --skip-smudge` / `GIT_LFS_SKIP_SMUDGE=1` on Render | **Yes, with `ensure_deploy_csvs.py`** |
| Audit LFS; stop tracking new huge files | **Yes, always** |
| `$0` LFS budget until reset | **Optional** — stops overage, not a deploy fix |
| `git lfs migrate export` | **Not first choice** — do after skip-smudge deploy is stable |

## Longer-term

Host `facility_quarterly_metrics.csv` on S3/R2 and `curl` in build if you need the full 190 MB file without LFS meter.

## Local dev

```bash
git lfs install
git lfs pull   # only when you need real CSVs
```

Do not run `git lfs push` unless you intentionally updated LFS objects.
