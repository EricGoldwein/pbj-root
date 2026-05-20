# Owner portfolio summary metrics

Headline **Staffing (HPRD)** and **Overall rating** on `/owners/<pac>` profiles are computed in `owner_portfolio_metrics.build_portfolio_summary()`.

## What is included

- **Facilities in the table:** All rows linked from CMS SNF All Owners for the party (verified and tentative name matches).
- **Facilities in portfolio means:** Only **PBJ-verified** rows (`legal_exact` CCN match: enrollment legal name equals provider-info legal name). Tentative name matches appear in the table but do not affect snapshot means.

## Missing data (N/A)

| Situation | Effect |
|-----------|--------|
| No HPRD in provider info | Facility omitted from HPRD means; still listed in table |
| No overall star rating | Facility omitted from overall-rating mean |
| No census and no certified beds | Included in **simple facility average**; omitted from **census-weighted** mean |
| Not PBJ-verified | No PBJ columns; excluded from portfolio means |

Previously, missing census/beds fell back to weight `1.0`, which could overweight small facilities with bad data. Weighted means now require census or beds.

## Outlier exclusion

Portfolio means exclude implausible values so a single bad provider-info row does not dominate a chain summary.

### Total nurse HPRD

Aligned with **CMS PBJ public-use file quarterly rules** ([PBJ methodology](/pbjpedia/methodology)):

- **Exclude** HPRD **&lt; 1.5** or **&gt; 12.0** hours per resident day
- Values such as **0.5 HPRD** are always excluded (below the CMS aberrant-staffing floor)

Constants: `PORTFOLIO_HPRD_MIN = 1.5`, `PORTFOLIO_HPRD_MAX = 12.0`.

CMS applies these limits to **quarterly facility aggregates** before publishing PUFs. Provider-info reported HPRD can still occasionally fall outside this range; we apply the same bounds at portfolio rollup time.

### Overall star rating

- **Exclude** ratings outside **1–5** (invalid or corrupt CMS fields)
- Half-star CMS ratings are not used for overall stars (integer 1–5 only)

## Weighted vs simple average

| Metric | Weighted (shown on profile) | Simple average (internal) |
|--------|----------------------------|---------------------------|
| HPRD | Σ(HPRD × weight) / Σ(weight) | Mean of facility HPRDs |
| Overall rating | Σ(rating × weight) / Σ(weight) | Mean of facility ratings |

**Weight** = average daily census when published, else certified beds.

## Quality counters

`portfolio_summary` exposes counts for UI footnotes:

- `n_missing_hprd`, `n_missing_overall_rating`
- `n_hprd_outlier_excluded`, `n_rating_outlier_excluded`
- `n_missing_resident_weight` (verified facility with no census/beds for weighting)

## References

- CMS PBJ inclusion/exclusion: [PBJpedia methodology](/pbjpedia/methodology) (1.5–12 HPRD quarterly rule)
- HPRD definition: [PBJpedia metrics](/pbjpedia/metrics)
