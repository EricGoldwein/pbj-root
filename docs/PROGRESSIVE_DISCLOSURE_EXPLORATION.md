# Progressive disclosure exploration — PBJ320 facility / state / chain pages

**Status:** Stage 0 frozen — exploration memo + isolated scaffolding only. No routes, APIs, `app.py`, page output, UI shell, or cache changes.  
**Date:** 2026-06-22 (validation audit added)  
**Verified from:** `app.py` route/builders, `public_metadata.py`, `staffing_screening_registry.py`, `staffing_compliance_bundle.py`, `state_page_aggregates.py`, `public_route_context.py`, `tests/test_public_metadata.py`.

---

## 1. Current architecture findings

### 1.1 Rendering model

All public staffing pages are **inline HTML builders in `app.py`**, wrapped by `get_pbj_site_layout()`. There are no Jinja templates for facility, state, or entity pages. Shared chrome: nav, footer, `pbj-site-universal.js`, `#pbj-route-context` JSON (`public_route_context.py`).

| Surface | Route | Builder | Primary data |
|---------|-------|---------|--------------|
| Facility | `/provider/<ccn>` | `generate_provider_page_html()` | `facility_quarterly` (SQLite index or CSV), provider info, compliance bundle |
| State | `/state/<slug>` | `generate_state_page_html()` | `state_quarterly_metrics.csv`, `state_page_aggregates.json.gz` |
| Chain | `/entity/<id>` | `generate_entity_page_html()` | Facility roster + `facility_quarterly`, chain performance CSV |
| Owner profile | `/owners/<PAC>` | `ownership/owner_profile_html.py` | Ownership indexes |

### 1.2 Facility page hierarchy (today)

Top → bottom in `generate_provider_page_html()`:

1. **H1 + subtitle** — location, HPRD, census, ownership, entity link
2. **SEO intro** — `provider_page_intro_html()`
3. **PBJ Takeaway** (`#pbj-takeaway`) — badges (risk/SFF, HPRD+direct, case-mix, census, CMS stars), narrative paragraph, compliance suffix (NY/CT), AI bar (CT/NY when enabled), HPRD explainer modal
4. **Charts** — Total HPRD (+ MACPAC/NY line), CMS Case-Mix card, RN/LPN/Aide tabs, Census, Contract %
5. **Bottom stack** — custom report CTA, ownership/CHOW (beta states), methodology collapsible, premium bridge, sources footer + hidden CSV export

Cold path still loads facility longitudinal data + provider info + compliance lookup; HTML is cached per worker (`PBJ_PROVIDER_PAGE_CACHE_TTL`).

### 1.3 State page hierarchy (today)

1. H1 + subtitle (provider count, residents, HPRD)
2. PBJ Takeaway — state badges (HPRD+rank, RN, contract, state-min), narrative vs national + YoY, D3 state outline
3. Charts via `/api/state/<code>/chart-data` + `state-page-charts.js`
4. Collapsible staffing comparison table (state vs CMS region vs U.S.)
5. Bottom stack — high-risk lazy table, top owners, CHOW, methodology, custom report CTA

### 1.4 Entity (chain) page hierarchy (today)

1. H1 + intro
2. PBJ Takeaway — portfolio badges + three narrative paragraphs
3. Portfolio block (weighted HPRD)
4. High-risk metrics section
5. Sortable facilities table
6. Cross-links, methodology, custom report CTA, ownership tools

### 1.5 Mapping to Snapshot / Patterns / Evidence

| Depth level | Facility (natural fit) | State | Entity |
|-------------|------------------------|-------|--------|
| **Snapshot** | PBJ Takeaway narrative + 2–4 defensible findings (HPRD vs state avg, case-mix gap, compliance day-counts, CMS screening flags) | Takeaway badges + national comparison sentence | Takeaway paragraphs (scale, HPRD vs national, high-risk %) |
| **Patterns** | Chart block (quarterly trends, role tabs, contract, case-mix bars) | State charts + comparison table ranks | Portfolio metrics + facilities table sort |
| **Evidence** | Methodology block, compliance API, hidden CSV, chart footnotes, `/data-sources` | Methodology, high-risk table (lazy), aggregate sources | Methodology, per-facility row data, sources footer |

**Gap:** Snapshot and Patterns are not separated in the DOM — Takeaway sits above a full chart wall with no progressive affordance. Evidence is scattered (modals, collapsibles, footer CSV).

### 1.6 Duplicate metrics / methodology drift risks

| Risk | Where | Notes |
|------|-------|-------|
| Total vs direct care HPRD | Takeaway badges, charts, NY compliance | NY daily screen uses `direct_care_hprd`; charts often show total + direct series; badge shows both |
| NY 3.50 threshold | `get_macpac_chart_info()`, compliance bundle, `_provider_staffing_compliance_warning()` | Chart line, bundle `state_min_threshold_used`, hardcoded copy in warning sentence for NY |
| State average HPRD | Takeaway narrative, `state_quarterly_metrics.csv` scan, percentile pickle | Same quarter alignment via `get_canonical_latest_quarter()` but two loaders |
| Case-mix / CMI | Provider info quarter row vs facility PBJ row | Census may come from provider info or PBJ |
| MACPAC vs statutory | State charts (estimated standard) vs NY legal minimum | Different `threshold_type` in `public_metadata` |
| CMS “high risk” | Search index, SFF list, provider badges, state lazy table | String reasons in `_pbj320_high_risk_reasons()`, not structured |
| Dead cold-path work | `yoy_line`, `yoy_sentence`, `orientation_summary`, `entity_summary_html` | Computed in `generate_provider_page_html()` but not always rendered |
| Screening vs finding language | `pbj_review_framework.py`, compliance modals | Framework exists; Takeaway still mixes badges + narrative |

### 1.7 Existing infrastructure (reusable, not wired to pages)

- **`public_metadata.py`** — metric/threshold registry, evidence tiers, `page_bootstrap_payload()`, `render_metadata_bootstrap_script()`; **not injected** into live pages; `/api/public/metadata.json` tested but **not registered** in `app.py`
- **`staffing_screening_registry.py`** — composed rules (`StaffingMetricDefinition`, `StateStaffingRule`) → public threshold entries
- **`staffing_compliance_bundle.py`** — precomputed daily screen counts per CCN×quarter
- **`public_route_context.py`** — active; search state boosting only
- **Feature gating** — env vars per domain (`PBJ_OWNERSHIP_PREVIEW`, `PBJ_AI_SUPPORT`, `PBJPEDIA_PUBLIC`); no central feature-flag registry

---

## 2. Recommended information architecture *(hypotheses — not settled)*

Sections 2.1–2.3 describe **candidate** patterns for visual/product testing. Nothing here is committed for implementation at Stage 0.

### 2.1 Three depth levels (facility-first) *(hypothesis)*

Progressive disclosure should **re-group existing modules**, not replace calculations:

```
┌─────────────────────────────────────────────────────────┐
│  SNAPSHOT — "What is the main staffing story?"          │
│  2–4 finding cards (plain language, linked evidence)    │
│  Optional: one-line orientation (existing narrative)    │
└─────────────────────────────────────────────────────────┘
          │ expand / scroll
          ▼
┌─────────────────────────────────────────────────────────┐
│  PATTERNS — "How does this behave over time?"           │
│  Existing charts + role tabs + case-mix card            │
└─────────────────────────────────────────────────────────┘
          │ expand / scroll
          ▼
┌─────────────────────────────────────────────────────────┐
│  EVIDENCE — "What supports this?"                       │
│  Methodology, compliance summary, exports, sources      │
└─────────────────────────────────────────────────────────┘
```

**Principles:**

- Snapshot findings are **observations with comparators**, not diagnoses or composite scores.
- Each finding links to a **Patterns anchor** (chart) and **Evidence anchor** (methodology row or API).
- State and entity pages can adopt the same frame later; facility page is the pilot.

### 2.2 UX pattern recommendation *(hypothesis)*

**Candidate:** anchored sections with a sticky segmented control (not tabs that hide content from crawlers or deep links).

| Pattern | Fit for PBJ320 | Rationale |
|---------|----------------|-----------|
| Tabs | Poor | Hides charts from scroll/search; breaks existing deep links to charts |
| Accordion-only | Partial | Matches methodology collapsibles but hides Patterns by default |
| **Sticky segment + scroll spy** | **Possible fit** | Matches dark slate layout, preserves full page in DOM, mobile-friendly |
| Progressive cards | Good for Snapshot only | 2–4 `finding-row`-style cards (press HTML precedent) |

**Snapshot card shape** (restrained, not badge wall):

- **Label:** metric + period (`Total nurse HPRD · Q4 2025`)
- **Observation:** `3.42 HPRD`
- **Comparator:** `Below New York direct care reference (3.50 HPRD)` or `Near state average (3.38)`
- **One sentence:** payroll-based, quarter-level, non-causal
- **Actions:** `See trend` → `#patterns-total-hprd`; `How calculated` → `#evidence-metric-total_nurse_hprd`

Reuse existing tokens: `.pbj-takeaway` panel chrome, `--pbj-*` from `insights-theme.css`, inline badge palette from `app.py` for severity only (not for Snapshot primary labels).

### 2.3 Snapshot finding priority (facility pilot) *(hypothesis)*

**Candidate ordering** — not implemented in scaffolding; validation below shows gaps.

1. **Quarterly total HPRD vs state average** (existing `_classify()` / orientation logic)
2. **Direct care vs reference** (NY 3.50 or MACPAC screen where configured; label from `staffing_screening_registry`)
3. **Daily threshold shortfall rate** (compliance bundle; NY/CT only when summary exists)
4. **Case-mix comparison** OR **state percentile** OR **CMS screening flag** (single highest-priority CMS flag per `_pbj320_high_risk_reasons` order)

Do not show all badges from Takeaway in Snapshot — migrate narrative into finding cards.

---

## 3. Proposed signal / evidence object shape

Thin adapter over existing registries — **not a scoring engine**.

```python
# provider_snapshot_signals.py (scaffolding)
PublicStaffingSignal = {
    "signal_id": str,           # f"{entity_type}:{entity_id}:{metric_id}:{period}"
    "entity_type": "facility" | "state" | "entity",
    "entity_id": str,           # CCN, state abbr, entity id
    "metric_id": str,           # public_metric_metadata.json
    "observed_value": float | int | None,
    "observed_display": str,    # format_metric_value output
    "period": str,              # CY2025Q4
    "period_display": str,
    "comparator": {
        "kind": "threshold" | "peer_average" | "percentile" | "case_mix",
        "threshold_id": str | None,
        "value": float | None,
        "label": str,
        "threshold_type": str | None,  # legal_minimum | benchmark | ...
    },
    "direction": "above" | "below" | "near" | "at" | "not_applicable",
    "display_label": str,
    "explanation": str,         # plain language; screened by public_metadata banned terms
    "methodology_ref": str,     # metric_id or threshold_id or snippet key
    "source_type": str,         # payroll_based | inspection_based | ...
    "evidence_tier": str,         # from public_independence_guardrails.json
    "data_quality": "complete" | "partial" | "missing" | "insufficient_sample",
    "display_priority": int,    # 1–4 for Snapshot ordering; NOT a composite rank
    "depth_links": {
        "patterns_anchor": str,
        "evidence_anchor": str,
    },
}
```

**Adapter strategy:**

| Signal source | Existing function / data | metric_id |
|---------------|--------------------------|-----------|
| Quarterly HPRD vs state | `facility_df` row + state CSV match | `total_nurse_hprd` |
| Direct care vs NY/CT screen | `staffing_compliance_bundle` summary | `direct_care_hprd` / `threshold_shortfall_rate` |
| Case-mix gap | provider info quarter + reported HPRD | `case_mix_total_nurse_hprd` |
| State percentile | `get_facility_state_percentile()` | `state_percentile` |
| CMS screening | `_pbj320_high_risk_reasons()` | `abuse_icon`, SFF-related metric ids |

`staffing_screening_registry.rule_to_public_threshold_entry()` and `public_metadata.metrics_by_id()` supply labels/caveats. **Do not duplicate threshold numbers in the adapter** — read from bundle or registry.

---

## 4. Best prototype approach and scope

### 4.1 Recommended path: env-gated prototype route (facility only)

| Option | Risk | Verdict |
|--------|------|---------|
| Change `/provider/<ccn>` layout | High — SEO, cache, mobile | **No** |
| Feature-flagged shell wrapping existing HTML | Medium — cache invalidation, duplicate render | Defer |
| **`/prototype/provider/<ccn>` when `PBJ_SNAPSHOT_PROTOTYPE=1`** | **Low** — isolated URL, same data loaders | **Yes (phase 2)** |
| Static HTML from script + real CCN JSON | Low — no server change | Good for design review |
| Scaffolding module only (phase 1) | **Lowest** | **Yes (now)** |

### 4.2 Phase 1 scope (this pass)

- Add `provider_snapshot_signals.py` — signal TypedDict + pure builders from dict inputs
- Add `tests/test_provider_snapshot_signals.py` — shape validation, NY threshold labels from registry
- **No** `app.py` route registration
- **No** changes to `generate_provider_page_html()`

### 4.3 Phase 2 scope (next pass, when approved)

- Register `@app.route('/prototype/provider/<ccn>')` only if `os.environ.get('PBJ_SNAPSHOT_PROTOTYPE') == '1'`
- Reuse `_provider_page_impl` data loading; new `render_progressive_facility_shell(signals, patterns_html, evidence_html)` that **calls existing chart/methodology renderers** (extract fragments, don't fork calculations)
- Representative CCNs: NY facility with compliance data (e.g. `335513`), CT facility, non-screen state
- `X-Robots-Tag: noindex` on prototype routes

### 4.4 Rollback

- Phase 1: delete `provider_snapshot_signals.py` + test file
- Phase 2: unset env var or remove route block; no cache key changes on production `/provider/`

---

## 5. Files likely affected (by phase)

| Phase | File | Role |
|-------|------|------|
| 1 ✅ | `provider_snapshot_signals.py` | Signal adapter (new) |
| 1 ✅ | `tests/test_provider_snapshot_signals.py` | Unit tests (new) |
| 1 | `docs/PROGRESSIVE_DISCLOSURE_EXPLORATION.md` | This memo |
| 2 | `app.py` | Gated `/prototype/provider/<ccn>` only |
| 2 | `prototype_progressive_facility_html.py` (optional extract) | Shell renderer to keep `app.py` diff small |
| 2 | `public_metadata.py` | Wire `render_metadata_bootstrap_script()` into prototype shell |
| 3 | `app.py` `generate_provider_page_html()` | Production re-group behind separate flag (not phase 1–2) |
| 3 | `state-page-charts.js` | Anchor ids for Patterns deep links |
| later | `generate_state_page_html()`, `generate_entity_page_html()` | State/entity Snapshot adapters |

**Low-risk refactors (pre-requisite, any phase):**

- Extract unused YoY/orientation strings into Snapshot signal builders (removes dead cold-path work)
- Register `/api/public/metadata.json` (already tested) — enables client Evidence tooltips without page changes

**Do not touch without explicit approval:**

- `staffing_compliance_thresholds.json`, NY 3.50 logic, `build_state_page_aggregates.py`
- Production Takeaway copy, chart calculations, `state-page-charts.js` data transforms

---

## 6. Risks / unresolved questions

1. **Cache coherency** — Provider HTML cache (`_provider_page_cache_hit_ok`) keys on DOM markers; prototype must use separate cache namespace or bypass cache.
2. **Cold-path cost** — Prototype route must not double cold renders; share loaders with `_provider_page_impl` or accept same cost once.
3. **Finding count vs Takeaway badges** — Product decision: do CMS star badges stay in Snapshot or move to Evidence only?
4. **NY copy hardcoding** — `_provider_staffing_compliance_warning()` hardcodes "3.50 HPRD" in one branch; signal adapter should use `state_min_label` from bundle to avoid drift.
5. **Metadata API** — Bootstrap JSON ready but unwired; prototype should be first consumer.
6. **Mobile** — Sticky segment control must not overlap `.pbj-takeaway-actions` or AI bar; test on 320px width.
7. **AI handoff** — `pbj_ai_support` expects current DOM; prototype should not break `#pbj-takeaway` id if running in parallel on same CCN data.
8. **State/entity parity** — Entity table already dense; Snapshot may be 2 findings max for chains.

---

## 7. Staged implementation plan

| Stage | Deliverable | Production impact |
|-------|-------------|-------------------|
| **0** | This memo + signal scaffolding | None |
| **1** | Register `/api/public/metadata.json`; inject metadata bootstrap on prototype only | None on `/provider/` |
| **2** | `/prototype/provider/<ccn>` shell with Snapshot cards + anchored Patterns/Evidence wrapping **existing** HTML fragments | None (noindex, env-gated) |
| **3** | Extract `build_facility_snapshot_signals(ccn, ...)` call from `generate_provider_page_html` dead paths; reduce duplicate YoY | None visible |
| **4** | A/B or flag `PBJ_PROGRESSIVE_FACILITY=1` on `/provider/<ccn>` | Requires cache version bump + QA |
| **5** | State page Snapshot (2 findings: vs national, rank) | Separate flag |
| **6** | Entity page Snapshot | Separate flag |

**Success criteria for facility pilot:**

- Snapshot ≤ 4 findings, each traceable to metric_id + period + comparator
- Patterns section identical charts/data to current page
- Evidence links resolve to methodology or compliance API fields
- No new thresholds or composite scores
- Lighthouse/mobile parity with current provider page

**Stage 0 stop line:** Do not proceed past Stage 0 without explicit approval. Stages 1–6 remain deferred.

---

## 8. Validation Findings and Decisions Deferred

**Audit method:** Read-only run of `provider_snapshot_signals.build_facility_snapshot_signals()` against local Q4 2025 data (`2025Q4` / `CY2025Q4`). Reproducible via `scripts/_tmp_snapshot_signal_audit.py` (not wired to production).

**Verified from:** `facility_quarterly_metrics.csv`, `state_quarterly_metrics.csv`, `data/compliance/staffing_compliance_summary.csv.gz`, `staffing_compliance_bundle.lookup_public_summary()`, `provider_info/ProviderInfoNorm_2026_05.csv`, `staffing_screening_registry.get_daily_screen_rule()`.

### 8.1 What the current signal model can safely support now

| Builder | Safe when | Authoritative source |
|---------|-----------|----------------------|
| `build_hprd_vs_state_average_signal` | Facility has `Total_Nurse_HPRD` for canonical quarter **and** state aggregate row exists | `facility_quarterly_metrics.csv` + `state_quarterly_metrics.csv` (`Total_Nurse_HPRD`, `CY_Qtr`) |
| `build_compliance_shortfall_signal` | NY/CT only; `below_state_min_days_count > 0`; `total_days_reported > 0` | `staffing_compliance_bundle.lookup_public_summary()` → `direct_care_hprd` screen (NY 3.50) |
| Empty list | Missing quarterly HPRD or missing state average | Caller must pass `None`; builders return `None` |

**Isolated fix applied (Stage 0):** Compliance `explanation` no longer duplicates state prefix (`"NY NY …"`). Test: `tests/test_provider_snapshot_signals.py`.

### 8.2 Scenario audit (representative CCNs)

Canonical quarter: **`2025Q4`** (facility/state CSV) / **`CY2025Q4`** (compliance bundle).

#### Scenario 1 — NY facility, meaningful direct-care shortfall

**CCN 335003** (Emerald Peek Rehab, NY)

| Field | Value |
|-------|-------|
| Quarterly total HPRD | 3.15 (`Total_Nurse_HPRD`) |
| Quarterly direct care HPRD | 2.96 (`Nurse_Care_HPRD`) |
| State average (total) | 3.59 (`state_quarterly_metrics.csv`, NY, 2025Q4) |
| Compliance | 91/92 days below 3.50 direct care (98.9%); `state_min_metric_used=direct_care_hprd` |
| CMS (not in signals) | 1-star staffing (`staffing_rating` in ProviderInfoNorm) |

**Signals produced (2):**

1. `total_nurse_hprd` — below NY state **total** average; period labeled quarterly (`Q4 2025`).
2. `threshold_shortfall_rate` — daily shortfall vs 3.50 **direct care**; same `period_display` but daily denominator.

**Public defensibility:** Compliance signal **defensible** with screening disclaimer (matches production `_provider_staffing_compliance_warning` intent). HPRD-vs-state-average signal **defensible as descriptive** but **not interchangeable** with NY 3.50 rule (different metric and period grain).

**Recommendation:** Surface compliance shortfall in Snapshot when present; treat HPRD-vs-state-average as **optional hypothesis**, not default headline for NY.

---

#### Scenario 2 — NY facility at/above 3.50 direct care for most days

**CCN 335092** (Henry J Carter SNF, NY)

| Field | Value |
|-------|-------|
| Total / direct HPRD | 6.04 / 5.48 |
| Compliance | 0/92 days below 3.50 direct care |
| Case-mix total | 6.76 (reported below case-mix) |

**Signals produced (1):** `total_nurse_hprd` above state average only.

**Public defensibility:** Correct suppression of compliance signal (`n_below == 0`). No positive “meets NY standard” signal exists in scaffolding — **gap** if product wants affirmation, not just silence.

**Note:** CCN **335513** (Seagate, used in playwright audits) has **100%** below-days in Q4 bundle — not an “above standard” example despite high total HPRD relative to state average on quarterly basis.

---

#### Scenario 3 — Non-NY/CT facility (no state daily standard)

**CCN 395001** (PA), **CCN 675595** (TX)

| | PA | TX |
|---|----|----|
| Compliance `below_state_min_*` | `null` | `null` |
| Signals | 1 (`total_nurse_hprd` vs state average) | 1 (same) |
| Bundle fields ignored by scaffolding | — | `rn_0_days_count=12`, `rn_below_8hr_days_count=25` |

**Public defensibility:** Correct — no implied state statutory screen. **Mismatch:** Production bundle exposes RN day-count screens nationally; scaffolding does not. Must not label TX/P A rows as “below state minimum.”

**CCN 395001** has abuse icon + above-average HPRD — CMS flag would dominate Takeaway today but is **absent** from signals.

---

#### Scenario 4 — Incomplete / unavailable PBJ data

**CCN 745057** (TX; in ProviderInfoNorm but **no** `facility_quarterly` row for 2025Q4)

**Signals produced:** none.

**CMS data present but unused:** abuse icon in ProviderInfoNorm.

**Public defensibility:** Correct to emit no payroll-based signals. **Gap:** No explicit `data_quality: missing` placeholder signal for Snapshot UI; caller gets empty list only.

---

#### Scenario 5 — Case-mix / peer comparison changes interpretation

**CCN 305049** (NH; largest \|reported − case-mix\| / case-mix in local join)

| Field | Value |
|-------|-------|
| Reported total HPRD | 11.29 |
| Case-mix total | 3.22 |
| Gap ratio | +251% |
| Avg daily census | **5.4** |
| State average signal | “above NH state average (3.85)” |

**Signals produced:** 1 (state average only). **No case-mix builder exists.**

**Public defensibility:** State-average signal is **misleading without caveats** — tiny census inflates HPRD; case-mix gap is material. Should be **suppressed or downgraded** (`data_quality: insufficient_sample`) until census floor rules exist (production uses analytic gates in `pbj_review_framework`, not in scaffolding).

**Authoritative sources not wired:** `get_provider_info_for_quarter()` case-mix fields, `get_facility_state_percentile()` (percentile would rank within state but not explain case-mix).

---

#### Scenario 6 — CMS screening flag

**CCN 015019** (AL; abuse icon + 1-star overall)

**Signals produced:** 1 (`total_nurse_hprd` below AL state average).

**CMS reasons (unstructured):** Abuse, 1-star overall — from ProviderInfoNorm; mirrors `_pbj320_high_risk_reasons()` partially (no SFF lookup in audit script).

**Public defensibility:** CMS flags are **inspection-based screening**, not payroll findings. Current scaffolding **cannot** emit them (`metric_id` exists in `public_metadata` but no builder). Production shows badges in Takeaway with tooltips — **structured enough for display, not for signal adapter** without new `build_cms_screening_signal()` and explicit “screening, not finding” copy layer.

**Risk:** A Snapshot with only HPRD-vs-state-average **understates** CMS-visible screening (e.g. 335003 has 1-star staffing + compliance shortfall but only 2 payroll-derived signals).

### 8.3 Risk audit summary

| Risk | Finding |
|------|---------|
| **Total vs direct care** | HPRD signal uses `Total_Nurse_HPRD`; NY compliance uses `direct_care_hprd` @ 3.50. Same facility can show both; they measure different things. Direct care quarterly value exists in CSV but is **not** a separate signal. |
| **NY 3.50 rule** | Comparator value 3.5 and `legal_minimum` type align with `staffing_screening_registry` + bundle. Labels should come from `state_min_label` / `public_label` (fixed duplicate-prefix copy bug). |
| **State average vs percentile/threshold** | Scaffolding hard-codes **state mean** (`state_quarterly_metrics.csv`). Production also has percentiles (`get_facility_state_percentile`), case-mix, MACPAC chart lines — **not equivalent**. State average is a weak default comparator for Snapshot. |
| **Quarterly vs daily labeling** | Both signals use `period_display: "Q4 2025"` but compliance counts **days within quarter**. Display label “Days below reference · Q4 2025” conflates grains — needs distinct `period_grain` or copy layer. |
| **Missing / non-applicable states** | Non-NY/CT: compliance correctly skipped. Missing quarterly row: empty signals, no explicit insufficient-data card. |
| **CMS flags as findings** | Reasons are string lists in `app.py`; not in `PublicStaffingSignal`. Need structured `{metric_id, source_type: inspection_based, evidence_tier}` before Snapshot use. Abuse + high HPRD (PA) shows flags are **orthogonal** to staffing comparators. |
| **`explanation` in builder vs copy layer** | Builder currently generates full sentences. Audit suggests **split**: builder returns structured fields (`direction`, `comparator`, `metric_id`, `data_quality`); presentation layer applies `public_metadata` snippets + banned-term validation. Reduces duplication with production narrative and eases quarter/grain wording fixes. |

### 8.4 What must remain undefined until visual/product testing

- Snapshot depth count (0–4) and whether **zero findings** is valid
- Navigation pattern (sticky segment vs anchors-only vs collapsible Snapshot)
- Whether NY facilities should **prefer** compliance shortfall over state-average HPRD for headline finding
- Whether positive compliance (“0 days below reference”) appears or only negative screens
- How CMS screening badges relate to Snapshot cards vs Evidence-only
- Mobile ordering when 2+ signals + existing Takeaway badges coexist

### 8.5 What should not be surfaced publicly without additional methodology work

- Single HPRD-vs-state-average finding when **census &lt; analytic floor** or case-mix gap is large (305049 pattern)
- Composite or ranked “top issues” across signals (`display_priority` is ordering hint only — not validated)
- CMS abuse/SFF/1-star as Snapshot **findings** without inspection-based framing and tooltips matching `pbj_review_framework`
- RN-zero / RN-under-8 day counts outside NY/CT (in bundle, not in registry daily screens for all states)
- Case-mix gap signals without quarter alignment between ProviderInfoNorm and `facility_quarterly` (production aligns via `get_provider_info_for_quarter()`)

### 8.6 Recommended criteria for selecting 0–4 Snapshot findings *(hypothesis)*

Apply in order; **stop when cap reached**; any slot may remain empty:

1. **Data quality gate** — Skip payroll comparators if quarterly HPRD missing, census below floor, or quarter mismatch between PBJ and provider info.
2. **Jurisdiction-specific daily screen** (NY/CT only) — If `below_state_min_days_count > 0` and `total_days_reported` adequate, include `threshold_shortfall_rate` with screening disclaimer.
3. **Material case-mix or percentile** — Only if builder exists and gap/rank passes analytic gate (not implemented).
4. **CMS screening** (optional, Evidence-linked) — At most one inspection-based flag; never mixed into payroll comparator sentence.
5. **Peer comparator (lowest priority)** — State average only if no higher-priority signal fired and census/case-mix gates pass.

**0 findings** is valid (745057) — UI must not force placeholder badges.

---

## Appendix: related docs

- `PROVIDER_PAGE_STRUCTURE.md` (partially stale)
- `docs/PROVIDER_PAGE_PERFORMANCE.md`
- `docs/staffing_minimums_methodology.md`
- `data/public/public_independence_guardrails.json` — evidence tier language
