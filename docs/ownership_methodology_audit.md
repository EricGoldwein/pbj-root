# Ownership layer — methodology & audit reference (internal)

Last reviewed: 2026-05-28. Public surfaces: `/owners/`, `/owners/ny`, `/owners/ct`, `/owners/<10-digit-pac>`, provider/state ownership blocks. Public states: **CT + NY** (`ownership/beta_gate.py`).

This document is for developers and QA. It does not change user-facing copy.

---

## 1. Data sources

| Source | Path / artifact | CMS product | Used for |
|--------|-----------------|-------------|----------|
| SNF All Owners | `ownership/SNF_All_Owners*.csv` (newest filename wins) | [SNF All Owners](https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/skilled-nursing-facility-all-owners) | Owner names, PACs, roles, % ownership, association dates, facility org names |
| SNF owners SQLite | `ownership/snf_owners_lookup.sqlite` | Same (deploy build) | Fast PAC / enrollment lookups |
| Org name index | `ownership/snf_owners_org_index.json.gz` | Derived | Normalized org name → enrollment PAC |
| CCN index | `ownership/snf_owners_ccn_index.json.gz` | Derived | CCN → enrollment PAC + match method |
| State owner index | `ownership/state_owner_index.json.gz` | Derived | Full ranked list per NY/CT (owner PAC, in-state CCN counts) |
| State top owners | `ownership/state_top_owners.json.gz` | Derived | Top 8 per state (state pages / integrations fallback) |
| CHOW | `chow_index.json` (repo root) | [SNF CHOW](https://data.cms.gov/) + zip `ownership/Skilled Nursing Facility Change of Ownership.zip`, optional `data/chow/*.csv` | Change-of-ownership transactions |
| Provider info | `provider_info_combined_latest.csv` (+ fallbacks in `owner_portfolio_metrics.py`) | CMS Provider Info | Legal name ↔ CCN, HPRD, star ratings, beds, census, SFF/abuse |
| Facility search | `search_index.json` | PBJ320 deploy index | DBA/name ↔ CCN, CCN → state |
| State PBJ context | `state_quarterly_metrics.csv`, `latest_quarter_data.json` | PBJ quarterly aggregates | State index stats strip only |
| FEC | FEC API via `/owners/api/*` (donor sub-app) | FEC.gov | **Separate** from CMS ownership; name match only |

**Not wired in ownership Python:** `ownership/Nursing_Home_Chain_Performance_Measures_*.csv`, `ownership/entity_lookup.csv` (FEC donor DB only).

**Release labeling:** `snf_owners_source_citation()` parses month/year from active CSV filename → e.g. `CMS SNF All Owners (April 2026 snapshot)`.

---

## 2. CMS field mapping (PAC / profile kinds)

| CMS column | Meaning on PBJ320 | Profile kind when URL PAC equals |
|------------|-------------------|----------------------------------|
| `ASSOCIATE ID` | Enrollment / facility PAC | `enrollment` |
| `ASSOCIATE ID - OWNER` | Owner / control party PAC | `owner_control` |
| Both in file | — | `both` (enrollment section + nested owner section) |
| CHOW buyer/seller PAC only | — | `chow_only` |

**PAC normalization** (`normalize_associate_id`): digits only; 9 → zfill(10); 11 → last 10; legacy `O`+digits strip.

**Organization vs person:** `TYPE - OWNER` + name columns → `owner_type` display string (not a rigorous legal entity classifier).

---

## 3. Join keys and CCN resolution

### Facility ↔ CCN (`_resolve_ccn_with_method`)

1. **`legal_exact`** — `ORGANIZATION NAME` (SNF row) = `legal_business_name` in provider_info.
2. **`name_exact`** — DBA / `search_index.json` facility name.
3. **`fuzzy`** — token overlap on search_index (+ county hints).

Rank stored on facility row as `ccn_match_method`. Portfolio **means** use only `legal_exact` (`pbj_matched`).

### Owner ↔ facility (SNF file)

- Direct: each SNF row ties `ORGANIZATION NAME` (facility) to `ASSOCIATE ID - OWNER` (control party).
- No end-date filter: all rows in snapshot are treated as current unless CMS removed them in the source file.

### CHOW ↔ facility / PAC

- **CCN:** `CCN - BUYER` (normalized 6-digit).
- **State:** `ENROLLMENT STATE - BUYER` (or aliases in `build_chow_index.COL_MAP`).
- **PAC:** `ASSOCIATE ID - BUYER` / `ASSOCIATE ID - SELLER` → `by_associate_id` index.
- **Sort:** `effective_date` ISO descending (parsed from CMS effective date columns — **not** posting date unless source uses that field).
- **Party labels:** Buyer/seller org names from CHOW; may be enrollment entities, not SNF “owner” roles.

### Provider page ownership block

`lookup_cms_ownership_for_provider`: legal name → enrollment PAC; else DBA; else CCN → SQLite token match.

---

## 4. Counting rules (critical for QA)

| Metric | Where | Method | Includes tentative CCN? | Dedup key |
|--------|-------|--------|-------------------------|-----------|
| State index `facility_count` | `/owners/ny`, `/owners/ct`, search | Build: owner PAC rows → CCN → facility state ∈ {NY,CT} from **search_index** | No (no CCN → dropped) | **Distinct CCN** per owner PAC |
| Largest portfolios panel | Same artifact, top 5 | Same as state index | No | Distinct CCN |
| `state_top_owners.json.gz` | State staffing integrations | Same logic, top 8 | No | Distinct CCN |
| Profile `facility_count` | `/owners/<pac>` | All SNF rows for that PAC profile kind | **Yes** (listed even if CCN empty) | **Distinct ORGANIZATION NAME** (uppercase) |
| Portfolio means `n_pbj_matched` | Profile snapshot | Subset of facilities | Only `legal_exact` | Per facility row |
| CHOW-only profile facilities | `chow_only` | CHOW records for PAC | N/A | Distinct CCN in CHOW set |
| Control parties | Enrollment profile | Same enrollment rows | N/A | Distinct owner PAC |

### Scope: state index vs owner profile (public counts)

| Surface | Scope | Canonical definition (intended) | UI scope hint (2026-05-28) |
|---------|-------|--------------------------------|----------------------------|
| State index / Largest portfolios / in-state search | **In-state** (NY or CT) | Distinct **resolved CCNs** per owner PAC in that state | `title` / `aria-label` on ranked count: “Distinct CMS-linked facilities in {State}” |
| Owner profile snapshot “Facilities” | **Nationwide** | CMS-linked facilities for that PAC (table row count / `portfolio_summary.n_facilities` today) | `title` / `aria-label` on value: “Distinct CMS-linked facilities nationwide” |
| Owner profile `?` help | — | Explains PAC types + metrics | One line: state index counts are state-specific; profile counts are nationwide |

**Index vs profile differences are expected** for multistate owners (e.g. CT index shows in-state CCNs only; profile snapshot can be higher when the PAC has facilities in other states). This is a **scope** difference, not necessarily a data bug.

### TODO: Canonical public facility count (logic not implemented)

- **State portfolio counts** (ranked lists, search `facility_count`): distinct **resolved CCNs** per owner PAC in-state; rows without a CCN are omitted. **Already matches this in build.**
- **Profile `facility_count` / snapshot** (current code): distinct **facility names** (`ORGANIZATION NAME`) on the PAC profile; includes rows even when CCN resolution fails. **Differs from state index dedupe.**
- **Recommended future fix:** Use **distinct resolved CCNs** as the canonical profile count and expose `facility_counts_by_state: {NY: n, CT: m, …}` on the profile dict so UI can show “24 in Connecticut · 41 nationwide” without changing ranking logic. Do **not** change `owner_profile.py` count logic until product sign-off.
- **QA:** `scripts/audit_ownership_data.py` — compare index to in-state CCN subset on profile for top owners.

Enrollment PAC profiles are not ranked on state indexes (owner PAC only).

**Inactive/historical:** No filter on `ASSOCIATION DATE - OWNER`; snapshot is point-in-time from CMS file.

---

## 5. Portfolio / staffing / ratings on profiles

- **HPRD & stars:** `provider_info_combined_latest.csv` (latest row per CCN), not live PBJ quarter files on the profile path.
- **Weighted means:** Census, else certified beds; facilities without both contribute to simple mean only.
- **HPRD bounds:** 1.5–12.0 excluded from means (`PORTFOLIO_HPRD_MIN/MAX`).
- **Overall stars:** Integer 1–5 only for means; staffing star distribution separate.
- **Causation:** UI must not imply ownership causes staffing outcomes; FEC block is separate (`owner_fec_section.py`).

Spec mirror: `ownership/PORTFOLIO_METRICS.md`.

---

## 6. UI labels → meaning

| User-facing label | Supported? | Underlying data |
|-------------------|------------|-----------------|
| Largest NY/CT portfolios | Partial | Top owner **control** PACs by in-state **distinct CCN**; label does not say “CMS-reported” or “control party” |
| N facilities (ranked list) | Yes (in-state scope) | Same as state index count; tooltip states in-state CCNs |
| Facilities (profile snapshot) | Yes (national scope) | `portfolio_summary.n_facilities`; tooltip states nationwide |
| Recent ownership changes | Broad | CMS **CHOW** records; sorted by **effective date** |
| Reported buyer: (CHOW subline) | OK | CHOW **buyer** org name; may be licensee/enrollment entity |
| Linked / affiliated facilities | OK with caveat | CMS-reported associations, not beneficial ownership |
| Portfolio (section title) | OK | Facility list for PAC; means are PBJ-verified subset |
| CMS-reported owner (hub copy) | Yes | Aligned with SNF All Owners |
| FEC political contributions | Yes | Name match; disclaimers in section |

---

## 7. Known limitations

1. **Beneficial / operational control** not provable from CMS ownership files alone.
2. **Name matching** false positives/negatives on `name_exact` / `fuzzy` rows.
3. **Same org, multiple PACs** intentionally separate identities.
4. **CHOW buyer ≠ SNF owner role** vocabulary mismatch.
5. **Provider-info HPRD** may differ slightly from quarterly PBJ rollups on facility pages.
6. **State assignment:** Build uses `search_index`; runtime fallback `top_owner_organizations_for_state` prefers provider_info state — rare rank/count drift if artifacts stale.
7. **CHOW facility name** may be transaction-time; provider page may show current name.
8. **National profiles** outside CT/NY: `noindex, follow` or suppressed per `owner_indexability.py`.

---

## 8. Recommended QA checks

Run after deploy build:

```powershell
python scripts/audit_ownership_data.py
python scripts/validate_ownership_linkage.py
pytest ownership/test_owner_portfolio_metrics.py ownership/test_state_owner_index_seo.py -q
```

**Production browser QA** (after deploy): `docs/ny_ct_production_playwright_qa.md` — `python scripts/audit_ny_ct_playwright.py --out scripts/_ny_ct_playwright_report.json`. Pass = hub, `/owners/ny`, `/owners/ct`, and sample profiles load. State index vs profile **count differences are not Playwright failures** (see §4).

Manual spot checks:

- Top 3 NY/CT owners: compare state index count vs `/owners/<pac>` facility table rows (methodology check only, not a deploy blocker).
- CHOW row: buyer PAC opens profile; CCN opens `/provider/<ccn>`.
- Profile with fuzzy facilities: means unchanged when tentative rows added.
- FEC panel: confirm disclaimer visible; no implied CMS linkage.

---

## 9. Unresolved questions

- Implement canonical **distinct CCN** `facility_count` on profiles (see §4 TODO)?
- Should state index label clarify “CMS-linked facilities (distinct CCN)”?
- Filter SNF rows by association end date if CMS adds/expands field?
- Join CHOW post-close PBJ staffing (noted TODO in `build_chow_index.py`)?
- Add CHOW to `/data-sources.html` list (currently SNF All Owners only under ownership)?

---

## 10. File map (ownership code)

| Area | Files |
|------|-------|
| Core profile | `ownership/owner_profile.py` |
| Metrics | `ownership/owner_portfolio_metrics.py`, `ownership/PORTFOLIO_METRICS.md` |
| HTML | `ownership/owner_profile_html.py`, `ownership/state_owner_index_html.py` |
| CHOW | `ownership/chow_lookup.py`, `ownership/chow_display.py`, `scripts/build_chow_index.py` |
| Integrations | `ownership/page_integrations.py` |
| Build | `scripts/build_snf_owners_index.py`, `scripts/build_snf_owners_ccn_index.py` |
| Routes | `app.py` (`owners_*`, `cms_owner_profile_page`) |
| Tests | `ownership/test_owner_portfolio_metrics.py`, `ownership/test_state_owner_index_seo.py` |
