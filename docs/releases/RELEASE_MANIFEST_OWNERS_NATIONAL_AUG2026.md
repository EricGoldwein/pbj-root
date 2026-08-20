# Release manifest — Nationwide Owners (Aug 2026)

**Status at authoring:** pre-deploy gate (clean-build verified)  
**Date:** 2026-08-20  
**Product:** pbj320.com public site (`pbj-root`)

## SHAs

| Role | SHA | Notes |
|------|-----|--------|
| Production-before | `5ff48807bf7c50dfb04c992324514e5973035fde` | `origin/master` at gate |
| Approved RC | `597b532cb28250a7885936f15e223c425bb242d1` | `release-candidate/owners-national-aug2026` |
| Rollback tag | `pre-national-owners-20260820` → `5ff4880` | Restore production by resetting/deploying this SHA |
| Deployed (fill after) | _TBD_ | Record actual Render-serving commit after deploy |

## Deployment mechanism

| Item | Value |
|------|--------|
| Trigger branch | `master` |
| Auto-deploy | Yes — push to `origin/master` deploys Render web service `pbj` (`render.yaml`) |
| Build | `render.yaml` `buildCommand` rebuilds ownership indexes (`build_snf_owners_index.py`, `build_snf_owners_ccn_index.py`, `validate_ownership_linkage.py`, `build_owners_database.py`) and `build_sitemap_xml.py` |
| Start | `python scripts/render_start.py` |
| Health | `/healthz` |
| CHOW index | Committed `chow_index.json` (not rebuilt in Render buildCommand) |
| Ownership CSVs | Committed; indexes regenerated on Render from those CSVs |

## Clean-build verification

| Check | Result |
|-------|--------|
| Clean worktree | `pbj-root-deploy-owners-aug2026-597b532` detached at `597b532` |
| Active release | `2026-07-31` (`ownership_release_policy.json`) |
| Source content | July-31 All Owners + Enrollments **byte-identical** to approved set after LF normalization |
| Policy SHA note | Policy hashes are **CRLF** (Windows download). Git/Render store **LF**. `sha256(CRLF)==policy`; `sha256(LF)==git blob`. Content equal. |
| All Owners | `SNF_All_Owners_2026.07.31.csv` — policy `4346a8d4…` (CRLF); deploy LF `42fb23d3…` |
| Enrollments | `SNF_Enrollments_2026.07.31.csv` — policy `387e0caf…` (CRLF); deploy LF `2cb98bee…` |
| Bridge | `ownership/_derived/cms_snf_ownership_ccn_bridge/release_2026-07-31_lookup.json` — `exact_release_date_match` |
| ProviderInfo | `provider_info/ProviderInfoNorm_2026_07.csv` |
| CHOW | `chow_index.json` — **Q2 2026**, 5,227 events, `date_max=2026-02-01`, zip SHA `92e1cd6b…` |
| ADP | Quarantined stub only (`ownership/_quarantine/`) — not ingested |
| Rebuild | `build_snf_owners_index.py` + state index + ccn/validate/owners_db — OK |
| Tests | `pytest ownership` — **109 passed** (15.20s) |

## Indexability / search / sitemap (clean rebuild)

| Metric | Count |
|--------|------:|
| Indexable PACs | 26,195 |
| noindex_follow | 47,527 |
| suppress (incl. Unknown) | 25,450 |
| `owner_search_lite` / catalog rows | 73,722 |
| Committed sitemap `/owners/{pac}` URL matches (pre-Render rebuild) | ~12,392 |

Render will regenerate sitemap during deploy; re-check production after ship.

## Production diff review (`5ff4880..597b532`)

**Scope:** 67 files — ownership canonical store, publication taxonomy, HPRD attribution, national `/owners` hub, nav/homepage Owners, state rankings, CHOW meta, July-31 sources + indexes, tests, SEO helpers.

**Explicit hygiene:**

| Concern | Finding |
|---------|---------|
| Unrelated WIP | None in commit range |
| `_scratch` | Not in diff |
| Temp QA scripts | Not in diff (local untracked only in RC tree) |
| Failed ADP | Quarantined with README; not ingested |
| Localhost / hard ports | None in code diff |
| Duplicate nav/search | Owners restored via `SITE_NAV_ITEMS` + homepage tab; national hub is search (not Indexes) |
| Accidental source clutter | July-31 CSVs + raw provenance copies intentional |

**Do not merge:** local untracked `tests/_qa_aug2026_*`, sqlite `-wal`/`-shm`, `subscribers.db`.

## Rollback

1. Tag: `pre-national-owners-20260820` = `5ff48807bf7c50dfb04c992324514e5973035fde`
2. To roll back production: reset `master` to that tag (or push that SHA to `master`) so Render redeploys prior build.
3. Rollback triggers: major owner pages fail; sitemap/canonical break; counts disagree with RC; Unknown reappears indexably; HPRD denominator missing; Life Care → 1 facility; Owners nav/homepage missing; widespread 5xx; raw CSV scan storms; taxonomy/SEO regression.

## Post-deploy checklist (fill)

- [ ] Deployed SHA recorded
- [ ] Production hubs `/owners`, `/owners/{fl,ny,tx,ca}`
- [ ] Mitchell `0648429498` — 274 / HPRD 4.39 / 2 qualifying
- [ ] Life Care `6608783543` — 141 facilities
- [ ] Soon Burnam `9739195553` — control framing, no owner HPRD mean
- [ ] Navbar + homepage Owners search
- [ ] SEO / sitemap sample 25–50 URLs
- [ ] Mobile 375 / 390 / 430
- [ ] Perf / logs stabilization
- [ ] Final: `DEPLOYED AND VERIFIED` or `ROLLED BACK`
