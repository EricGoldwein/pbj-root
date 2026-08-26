# CMS release watcher (read-only)

**Tier:** living how-to (observe only). Does not change production data.

## Purpose

Detect when CMS publishes a new distribution for registered nursing-home datasets, compare that to **what PBJ320 is actually serving**, and list which downstream systems/artifacts would need a human refresh.

It does **not** download, normalize, rebuild indexes, clear caches, mutate `ownership_release_policy.json`, commit to git, push, or deploy.

## Surfaces (kept separate)

| Surface | Host / path | Notes |
|---------|-------------|-------|
| Public staffing | `www.pbj320.com` `/`, `/state`, `/report`, search | Flask on Render (`pbj-root`) |
| Dynamic provider | `/provider/<ccn>` | Same app; uses facility metrics + ProviderInfoNorm + ownership indexes |
| Ownership | `/owners`, `/owners/<PAC>/...` | Policy-pinned SNF All Owners / Enrollments |
| Premium | `/premium/<ccn>` → Vercel | PBJapp bundles; EIN / daily / non-nurse — vintage **UNPROVEN** from pbj-root alone |
| Legacy | `pbj-dashboard.onrender.com` | Streamlit; not authoritative for public PBJ320 |

## Commands

```bash
# Dependency map
python -m cms_watcher --print-dependency-graph

# Live observe (no issues, no repo writes)
python -m cms_watcher

# Dry-run issue payloads (still no git writes)
python -m cms_watcher --dry-run-notify --json

# CI / Actions (issues:write only; never commits)
python -m cms_watcher --notify --json
```

## Durable state (not on `master`)

| What | Where |
|------|--------|
| Release dedup | GitHub issues labeled `cms-release-watcher` (open **and** closed) |
| Fingerprint marker | `<!-- cms-release-watcher:{source_id}:{fingerprint} -->` in issue body |
| `last_checked_at` | Runtime JSON / stdout only — **never** committed |

There is **no** committed `watcher_state.json`. Pushing mutable state to `master` would auto-deploy Render (`pbj`) and violate the watcher safety bar.

## Workflow permissions

```yaml
permissions:
  contents: read
  issues: write
```

## Statuses

| Status | Meaning |
|--------|---------|
| `CURRENT` | Production vintage matches CMS current distribution vintage |
| `NEW_RELEASE` | Alertable CMS fingerprint with **no** prior open/closed watcher issue (annotated at notify time) |
| `METADATA_CHANGED` | Reserved for explicit annotation (not driven by a git state file) |
| `PRODUCTION_BEHIND` | CMS vintage ahead of PBJ320 production vintage |
| `DOWNSTREAM_STALE` | Source refresh would invalidate listed derived artifacts |
| `DOWNSTREAM_UNKNOWN` | Cannot prove derived freshness from repo alone |
| `CHECK_FAILED` | Metadata fetch/parse failed |

## What is rebuilt when

| Trigger | Rebuilt |
|---------|---------|
| Every Render deploy (`render.yaml` buildCommand) | decompress facility gz; state aggregates; provider indexes; SNF owner indexes/DB; compliance runtime index; sitemap; wrapped build |
| Manual release scripts / playbook | Norm CSV, combined_latest, quarter JSON, national/state CSVs, chow_index, compliance gz, ownership policy pin |
| Runtime only | provider HTML TTL cache, CSV load caches, canonical quarter cache (process memory; die with worker) |
| Survives deploys | committed CSVs/JSON/policy; **not** in-memory caches |

Runtime caches are **not** independent dataset vintages; they refresh from underlying files after TTL / process restart. Indexes rebuilt on Render will pick up newly committed sources on the next deploy after a human commit.

## Safety boundary

Never: download CMS CSV/ZIP payloads, normalize, build SQLite/JSON indexes, change policy, change quarter metadata, commit datasets, commit watcher state, push to `master`, or trigger Render/Vercel.
