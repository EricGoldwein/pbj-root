# Prompt preamble pack — 320 portfolio

Copy the block for the workspace you are in. Full detail lives in that repo’s `AGENTS.md`.

## pbj-root (public PBJ320)

```
Env: pbj-root (public PBJ320 site)
Runtime: app.py, templates/, root served CSVs/JSON; pbj-wrapped/public still live for SFF (Wrapped slides parked)
Upstream: provider_info/, ownership/, data/geo/, data_sources/
Derived: data/provider_indexes/, generated metrics JSON; pbj-wrapped/dist legacy
Scratch: _scratch/ only
Authority: pbj-contract/ + docs/AUTHORITY_LADDER.md
Ship: selective git add; no push/delete unless asked; Verified from: for schema/route claims
```

## PBJapp (premium / dashboard)

```
Env: PBJapp (premium dashboard / v2)
Runtime: app serving templates/static, ownership live-serving CSVs, release_source as used by deploy
Upstream: ownership/_sources/, PBJcsv (local), provider_info trees (often cursorignored)
Derived: ownership/_derived/, indexes, audit exports per PRIVATE_DATA paths
Scratch: _scratch/ or audit_artifacts policy in docs — never private_facility_data in git
Authority: .cursor/rules/* + docs; HPRD language per pbj-case-mix / facility display rules
Ship: selective git add; no push/delete unless asked; Verified from: required
```

## 320website (320insight.com)

```
Env: 320website (320 Consulting / 320insight site)
Runtime: app.py, templates/, static/, ops/ when enabled, NobodySpokeUp/ as mounted product
Upstream: content/, brand assets under static/
Derived: build/cache only as documented
Scratch: _scratch/, _verify/
Authority: AGENTS.md + docs/; do not treat playground experiments as production
Ship: selective git add; no push/delete unless asked
```

## Dog-of-the-day

```
Env: Dog-of-the-day (Expo / Dog of Day)
Runtime: app/ routes, lib/, assets serving the Expo app
Upstream: supabase/ migrations & functions as source of backend truth
Derived: EAS/build artifacts (not hand-edited)
Scratch: _scratch/ for QA captures
Authority: docs/product-and-ui.md + docs/* gates; branding in lib/branding.ts
Ship: selective git add; no push/delete unless asked; respect privacy/storage rules in docs
```
