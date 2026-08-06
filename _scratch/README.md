# `_scratch/` — local agent / QA only

**Layer:** Local / Scratch (not for release). Gitignored via `/_scratch/` in `.gitignore`.

## Put here

- Smoke HTML / JSON captures (`fac_*.html`, curl dumps)
- One-off parse/patch probe scripts
- `app.py` WIP backups before clean-hotfix checkout
- Playwright / screenshot probes

## Do not put here

- Anything Render must see
- Canonical templates (use `templates/`)
- Source CSVs that belong in `provider_info/` or `ownership/`

## Naming

Prefer dated or task-prefixed names, e.g. `_scratch/smoke_fac_335513.html`, `_scratch/app.py.wip_backup_hotfix`.

Root-level `_smoke_*` / `_patch_*` remain gitignored for legacy files; **new** probes should land in this folder.
