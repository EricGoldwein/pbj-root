# PBJ320 review modes (audience + geography)

The Staffing Review Framework uses **one shared core** (shows / suggests / cannot prove, interpretation checks, limitation language) plus **audience modifiers**. Default mode: **analyst**.

## Audience categories

| Key | Label | Emphasis |
|-----|-------|----------|
| `analyst` | Analyst | methodology, distribution, data quality, next analyses |
| `journalist` | Journalist | story angle, safe claims, sources, records requests |
| `advocate` | Advocate | screening flags, regulator questions, public caution |
| `family_resident` | Family / Resident | plain language, facility questions, visit observations |
| `attorney` | Attorney | incident window, discovery targets, evidentiary limits |
| `legislator` | Legislator | policy relevance, oversight, workforce, budget implications |
| `operator` | Operator | benchmarking, data QA, documentation readiness |

## Geographic / jurisdiction context

`national` · `state` · `region` · `county` · `city` · `facility` · `ownership_group`

If geography is omitted, infer scope from the material (state dashboard → state; facility page → facility).

Optional free-text context (examples): city name, “Florida statewide publication,” “plaintiff attorney reviewing an incident,” “daughter of a resident with dementia.”

## Implementation

- Python: `pbj_review_framework.py` (`ReviewConfig`, `compose_review_prompt_*`)
- Web: `window.__PBJ_REVIEW_FRAMEWORK__` + `PBJReviewFramework` in `pbj-review-framework.js`

All modes inherit the **same** SHARED DATA‑VISUAL RULE (canonical copy: skill `references/pbj320_visual_requirement.md`; runtime text in Python `PBJ_VISUAL_SELECTION_RULE`). Audience tweaks are **labels and emphasis only**.

Do not duplicate full prompts per audience in SKILL.md — use shared core + mode block from this reference.
