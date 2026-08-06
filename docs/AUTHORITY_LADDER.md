# Authority ladder — pbj-root

**NON-PROCESS.** This file ranks what agents and humans may treat as truth.

When documents conflict, prefer the **higher** tier. Do not “average” conflicting markdown.

## Tier 1 — Machine / contract truth

| Source | Owns |
|--------|------|
| `pbj-contract/*.yaml` | Metric definitions, formatting, quarter rules, disclaimers |
| Code + schemas (`app.py` routes, `facility_provider_indexes.*`, validate scripts) | Runtime behavior |
| `.cursor/rules/*.mdc` (alwaysApply / globs) | Agent operating constraints |
| Env flags (e.g. `PBJ_AUDIENCE_*`) | Feature gates — see `audience/prompt_config.py` |

Record **Verified from:** path or command when changing Tier-1-dependent behavior.

## Tier 2 — Living how-to (keep current)

| Source | Owns |
|--------|------|
| `AGENTS.md` | Env preamble, ship bar, cross-env |
| `FOLDER_STRUCTURE_CANON.md` | Four-layer folder map |
| `ARCHITECTURE.md` | Deploy, health, routing index |
| `docs/DATA_DEPLOY.md` | CSV/index deploy gates |
| `docs/audience-system-*.md` | Audience system design |
| `DEPLOY_AND_RUN.md` | Local run + Render basics |
| `RENDER_DEPLOY.md` | Memory / cache / Render tuning |
| `PBJPedia/*.md` | Public methodology pages (served; do not merge away) |
| `insights_posts/_quick-post-template.md` | Insight draft pattern |
| `pbj-wrapped/SLIDE_ORDER_AND_STYLE.md` | Slide order / durations |
| `CALCULATION_DOCUMENTATION.md` | report.html calculation rules (if present) |

## Tier 3 — Process / discovery (non-authoritative)

Treat as history unless promoted into Tier 1–2.

Bodies: `docs/archive/bodies/`. Index: `docs/archive/README.md`. Root stubs point there.

Examples (now under `docs/archive/bodies/` unless noted):

- `MOBILE_PBJPEDIA_PROMPT.md`, update checklists, restart notes, LinkedIn video instructions
- `FIXES_SUMMARY.md`, `CALCULATION_ANALYSIS.md`, SFF/memory debug summaries
- `CONSOLIDATION_PLAN.md` (root — execution log; Tier-3 class)

**Do not** change product behavior solely because a Tier-3 note says so. Re-verify in code/data.

## Promotion rule

To make a rule durable: put it in `pbj-contract/`, a validate script, or an alwaysApply `.cursor/rules` file — then point Tier-2 docs at it. Do not leave critical rules only in chat or Tier-3 markdown.
