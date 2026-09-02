# CMS ownership source discovery — audit + ops

**Authority:** detection/archive only. Never auto-promotes `ownership_release_policy.json`.

## Verdict (2026-08-20 Jul-31 releases)

**Would PBJ320 have detected `SNF_All_Owners_2026.07.31.csv` / `SNF_Enrollments_2026.07.31.csv` without a human asking?**

**No.**

| Stage | All Owners 2026.07.31 | Enrollments 2026.07.31 |
|-------|----------------------|-------------------------|
| Configured for discovery | Yes (in `cms_discover.TRACKED_DATASETS` since 2026-08-19) | **No** until 2026-08-20 registry work |
| Detected by discovery (registry first_seen) | **First recorded 2026-08-20 ~18:37Z** (this conversation) | Same |
| Downloaded/archived by discovery | No prior auto-archive | No prior auto-archive |
| Validated | Manual RC work after user handoff | Manual after CMS catalog lookup in-session |
| Activated in production policy | No (active remained / remains behind) | No |

Configured ≠ detected. `cms_discover.py` existed but **no scheduler, cron, Render job, or GitHub Action** invoked it. No `registry.json` / `latest_summary.json` existed before 2026-08-20 18:37Z.

### Timeline (factual)

| Event | When (UTC unless noted) | Evidence |
|-------|-------------------------|----------|
| CMS catalog folder / modified | Path `…/2026-08/…`; catalog `modified` ≈ `2026-08-17` | Live `data.cms.gov/data.json` via registry |
| Physical filename date | `2026.07.31` | CMS distribution filenames |
| User supplied Downloads All Owners (+ ADP/CHOW/chain) | 2026-08-20 ~12:27 EDT | User message with Downloads paths |
| Downloads All Owners file create | 2026-08-20 16:08Z | Local Downloads mtime (manual browser download) |
| Copies into Aug RC ownership/ | 2026-08-20 18:10Z | Aug worktree file create times |
| `cms_source_registry.py` created | 2026-08-20 18:37Z | File create; git `??` untracked |
| First `registry.json` / `latest_summary.json` | 2026-08-20 18:37:42Z | File create times |
| Enrollments added to TRACKED_DATASETS | 2026-08-20 (uncommitted edit) | git status `M scripts/cms_discover.py` |

**How All Owners entered the tree:** manual Downloads handoff after the user noticed August data — **not** proactive discovery.

**How Enrollments 07.31 became known:** live CMS catalog query during the ownership RC conversation after local tree only had `2026.07.17`.

### Infrastructure that existed

| Piece | Role | Auto-run? |
|-------|------|-----------|
| `PBJapp/scripts/cms_discover.py` | Catalog match / print | Manual CLI only |
| `PBJapp/scripts/cms_download.py` | Stage downloads | Manual CLI only |
| `PBJapp/scripts/cms_source_registry.py` | Registry + candidates | Added 2026-08-20; manual until task installed |
| `sync_to_pbj_root.py` | Copy already-local artifacts | Not discovery |
| `manage_cms_sources.py` | ProviderInfo / PBJ quarters | Not ownership catalog discovery |
| Render / GitHub Actions / schtasks | — | **None** for cms_discover/registry |

## Lifecycle vocabulary

1. **configured** — listed in `TRACKED_DATASETS` / stubs  
2. **detected** — seen in live `data.json` and recorded (`detection_history.json` `first_seen_at`)  
3. **downloaded_archived** — staged under `ownership/_sources/cms_discovery/staging/`  
4. **validated** — human/pipeline only (never set by discovery)  
5. **activated** — `ownership_release_policy.json` active only (never set by discovery)

## How to run automatically (required for future releases)

```powershell
cd C:\Users\egold\PycharmProjects\PBJapp
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_cms_discovery_scheduled_task.ps1
# optional smoke:
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_cms_ownership_discovery.ps1
```

Artifacts:

- `PBJapp/ownership/_sources/cms_discovery/registry.json`
- `…/detection_history.json` (first_seen vs last_seen)
- `…/open_candidates.json` + `CANDIDATES.md`
- Mirror: `pbj-root/ownership/_derived/cms_source_discovery/`

Catalog fetch failures are logged to `run_log.jsonl` and exit nonzero (not swallowed).

### ADP note

`SNF_Owners_ADP_Association_*.csv` is **not** in `data.cms.gov/data.json` (verified 2026-08-20). Discovery records `adp_supplemental: not_found_in_data_json`. ADP still requires package/manual ingest until CMS publishes it as a catalog distribution.
