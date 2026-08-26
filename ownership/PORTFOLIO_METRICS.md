# Owner portfolio summary metrics

Headline **Portfolio HPRD** on `/owners/<pac>` profiles is computed in
`owner_portfolio_metrics.build_portfolio_summary()`.

## What is included

- **Facilities in the table:** All rows linked from CMS SNF All Owners for the party (verified and tentative name matches).
- **Facilities in Portfolio HPRD:** PBJ-verified rows whose CMS relationship to the profile began on or before the PBJ quarter start (**any role category**). Each CCN counts once. This is a descriptive linked-facility statistic, not owner-attributable staffing responsibility.

## Missing data (N/A)

| Situation | Effect |
|-----------|--------|
| No HPRD in provider info | Facility omitted from HPRD means; still listed in table |
| No overall star rating | Facility omitted from overall-rating mean |
| No census and no certified beds | Omitted from census-weighted Portfolio HPRD |
| Not PBJ-verified | No PBJ columns; excluded from portfolio means |
| Timing uncertain / after quarter start | Excluded from Portfolio HPRD |

## Total nurse HPRD validity

Aligned with **current** CMS Five-Star / Care Compare Technical Users’ Guide full-quarter total-nurse exclusions (July 2026):

- **Exclude** HPRD **≤ 0**
- **Exclude** HPRD **> 12.0**
- **Do not** exclude valid values merely because they are below 1.5 (the `<1.5` floor applied only before January 2022)
- Source null/unavailable values are treated as missing (CMS already suppresses some invalid cells upstream)

Constant: `PORTFOLIO_HPRD_EXCLUDE_AT_OR_BELOW = 0.0`, `PORTFOLIO_HPRD_MAX = 12.0`. Weekend / nurse-aide component exclusions are **not** reproduced here unless those component fields are loaded and evaluated.

## Mutually exclusive terminal buckets

Every linked CCN is assigned exactly one of:

1. `timing_excluded_or_uncertain`
2. `pbj_match_excluded`
3. `missing_hprd`
4. `hprd_le_zero`
5. `hprd_gt_12`
6. `missing_invalid_weight`
7. `included`

Helpers: `classify_portfolio_hprd_terminal_bucket`, `reconcile_portfolio_hprd_buckets`.

## Weighted vs simple average

| Metric | Weighted (shown on profile) | Simple average (internal) |
|--------|----------------------------|---------------------------|
| HPRD | Σ(HPRD × weight) / Σ(weight) | Mean of contributing facility HPRDs |

**Weight** = average daily census when published, else certified beds. `n` equals the number of CCNs in the weighted mean.

## Quality counters

`portfolio_summary` exposes:

- `n_missing_hprd`, `n_hprd_le_zero_excluded`, `n_hprd_gt_12_excluded`
- `n_missing_resident_weight`, `n_timing_excluded`, `n_timing_uncertain`
- `hprd_terminal_buckets`, `n_obsolete_below_1_5_included`
- `n_hprd_portfolio_facilities`, `hprd_numerator`, `hprd_weight_denominator`

## References

- CMS Five-Star Technical Users’ Guide (July 2026) — current full-quarter total-nurse exclusions
- HPRD definition: [What is HPRD?](https://www.pbj320.com/what-is-hprd)
