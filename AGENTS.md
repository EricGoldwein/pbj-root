# AGENTS.md — pbj-root (PBJ320 public site)

**Product:** Public Flask site for pbj320.com (staffing data, insights, owners, premium surfaces).  
**Sibling envs:** `PBJapp` (premium/dashboard), `320website` (320insight.com), `Dog-of-the-day`.

Read this before editing. Full folder map: `FOLDER_STRUCTURE_CANON.md`. Authority: `docs/AUTHORITY_LADDER.md`. Ops protocol: `.cursor/rules/320-shared-agent-ops.mdc`.

## Prompt preamble (paste or assume)

```
Env: pbj-root (public PBJ320 site)
Runtime: app.py, templates/, root served CSVs/JSON; pbj-wrapped/public/ still hosts live SFF + some JSON (Wrapped slides product is parked)
Upstream: provider_info/, ownership/, data/geo/, data_sources/
Derived: data/provider_indexes/, generated metrics JSON; pbj-wrapped/dist is legacy build output
Scratch: _scratch/ only (never commit smoke/patch/tmp at root)
Authority: pbj-contract/ + AUTHORITY_LADDER.md — do not treat process MD as law
Ship: selective git add; no push/delete unless asked; Verified from: required for schema/route claims
```

## Four layers (quick)

| Layer | Put here | Do not put here |
|-------|----------|-----------------|
| Runtime | Served routes, templates, live-serving CSVs | Agent QA dumps, one-off probes |
| Upstream | Immutable CMS/source inputs | Generated indexes |
| Derived | Build outputs consumed by runtime | Raw unprocessed zips |
| Scratch | `_scratch/`, gitignored smoke/audit | Anything required on Render |

## Cross-env

- Do **not** invent paths in `PBJapp`, `320website`, or `Dog-of-the-day` from memory. Open that workspace or say you cannot see it.
- Shared metric definitions: prefer `pbj-contract/` over ad-hoc markdown.
- Brand/marketing site assets live primarily in `320website`; do not duplicate without a pointer.

## Ship bar

- No commit/push unless explicitly asked.
- Never `git add -A`. Follow `.cursor/rules/pbj320-clean-hotfix.mdc`.
- No deletes/moves of tracked files without explicit ask.
