# Provider Info field semantics

Which temporal semantic a Provider Info field means. A caller resolves Provider
Info under one of two explicit contracts -- `resolve_provider_info_current()` or
`resolve_provider_info_for_period()` (app.py, near `get_provider_info_for_quarter`)
-- and should pick the semantic the field actually needs, not whichever happens
to be loaded on the page already.

## PERIOD-SENSITIVE

Describes one PBJ quarter; must resolve independently per quarter
(`resolve_provider_info_for_period`). Never broadcast a current value backward,
never borrow a later quarter's value.

- `certified_beds`
- `avg_residents_per_day`
- `nursing_case_mix_index`, `nursing_case_mix_index_ratio`
- `case_mix_total_nurse_hrs_per_resident_per_day`, `case_mix_rn_hrs_per_resident_per_day`,
  `case_mix_lpn_hrs_per_resident_per_day`, `case_mix_na_hrs_per_resident_per_day`,
  `case_mix_weekend_total_nurse_hrs_per_resident_per_day`
- `adjusted_total_nurse_hrs_per_resident_per_day` (and role-level adjusted variants)
- `overall_rating`, `staffing_rating`, `qm_rating`, `health_inspection_rating`
- `sff_status`
- `abuse_icon`
- `provider_changed_ownership_in_last_12_months`

These are exactly the columns carried in `data/derived/provider_info_history.parquet`
(see `scripts/build_provider_info_history.py`) -- the historical artifact only
stores fields that need this semantic.

## CURRENT IDENTITY

Describes the facility as CMS reports it *today*; Provider Info does not version
these, so there is nothing to period-match. Use `resolve_provider_info_current()`.

- `provider_name`, `legal_business_name`
- `provider_address`, `city`, `county`, `zip_code`, `telephone`
- `provider_type`, `resides_in_hospital`, `ccrc`

## SPECIAL TEMPORAL SEMANTICS (native clock differs from Provider Info processing date)

Not period-matched to a PBJ quarter by this contract. Each has its own effective-date
system, out of scope for this pass (see `ARCHITECTURE.md` / Part I of the temporal-
alignment work) -- do not force these onto PBJ-quarter timing:

- `affiliated_entity_name`/`affiliated_entity_id`, `chain_name`/`chain_id` -- ownership
  /chain membership has its own as-of/effective-date system (`ownership/ownership_release_policy.json`);
  a Provider Info processing date is not that system's clock.
- `date_first_approved`, `cycle1_survey_date`, `cycle2_survey_date` -- survey-cycle
  dates, not publication vintages.
- `latitude`/`longitude`/`location` -- current geocoded location; no historical
  geography layer exists yet.

## Why this file exists

Before this pass, "Provider Info" calls in app.py did not distinguish these
semantics by name -- a caller could read `_provider_info_row_for_ccn` (current)
where it meant a specific quarter, or vice versa, and nothing in the function
name would catch it. `resolve_provider_info_current` /
`resolve_provider_info_for_period` make the choice explicit at the call site.
