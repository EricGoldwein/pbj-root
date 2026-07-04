# Facility page hierarchy — design specimens (Stage 0)

Isolated visual explorations. **Not imported by `app.py` or any production route.**

## Open locally

```powershell
# From repo root — opens default browser
Start-Process (Resolve-Path "docs\specimens\facility-progressive-335003.html")

# Or serve for browser tools (optional)
cd docs\specimens
python -m http.server 8765
# http://127.0.0.1:8765/facility-progressive-335003.html
```

## Current specimen

| File | Purpose |
|------|---------|
| `facility-progressive-335003.html` | Two hierarchy treatments (toggle at top) for CCN 335003 |
| `facility-progressive-335003.css` | Specimen-only styles (PBJ320 tokens) |

## Facility and evidence sources

**CCN 335003** — The Emerald Peek Rehabilitation and Nursing Center, Peekskill, NY.

| Finding | Observed | Comparator | Period / grain | Source types |
|---------|----------|------------|----------------|--------------|
| Direct-care days below NY reference | 91/92 days (98.9%) | 3.50 direct-care HPRD (§ 2895-b screen) | Q4 2025 · **daily** PBJ days | PBJ320-derived screen + payroll PBJ |
| Direct care vs case-mix | 2.96 HPRD | 4.76 HPRD case-mix expected total | Q4 2025 · **quarterly** | Payroll PBJ + facility-reported case-mix |
| RN vs case-mix RN | 0.48 HPRD | 0.84 HPRD case-mix expected RN | Q4 2025 · **quarterly** | Payroll PBJ + facility-reported case-mix |

**Authoritative files (local, 2026-06-22):**

- `facility_quarterly_metrics.csv` — `Total_Nurse_HPRD`, `Nurse_Care_HPRD`, `RN_HPRD`, `avg_daily_census`, `CY_Qtr=2025Q4`
- `data/compliance/staffing_compliance_summary.csv.gz` — `below_state_min_days_count`, `state_min_threshold_used`, `state_min_metric_used=direct_care_hprd`
- `provider_info/ProviderInfoNorm_2026_05.csv` — case-mix fields, star ratings (evidence band only)
- `data/compliance/staffing_compliance_thresholds.json` — NY `direct_care_hprd` @ 3.50
- `data/public/public_methodology_snippets.json` — public-safe methodology phrases

**Deliberately excluded from snapshot:** state-average HPRD as lead (validation audit); CMS 1-star staffing as payroll finding; composite rankings.

## Hierarchy options (in specimen)

Use the toggle buttons at the top of the HTML file.

### Option A — sectioned scroll *(recommended)*

Explicit section eyebrows: Staffing at a glance → Staffing over time → Records & methodology → Premium.

**Pros:** Clear mental model for progressive depth; evidence destination is obvious; works without JS chrome.  
**Cons:** Slightly longer scroll; more copy in section headers.

### Option B — takeaway-first

Keeps `#pbj-takeaway`-style panel; lighter section titles; inline “view trends / methodology” links.

**Pros:** Closer to current provider page; smaller diff from production Takeaway.  
**Cons:** Weaker separation between “orientation” and “evidence”; patterns may feel like today’s chart wall below the fold.

### Recommendation

**Option A** for a future pilot: it makes the evidence destination legible without inventing tabs or sticky controls, and it keeps inspection-based CMS context in the methodology band where validation placed it.

## Screenshots (2026-06-22)

| File | View |
|------|------|
| `facility-progressive-335003-option-a.png` | Option A — sectioned scroll |
| `facility-progressive-335003-option-b.png` | Option B — takeaway-first |

Preview live: open the HTML file locally or `http://127.0.0.1:8765/facility-progressive-335003.html` when serving `docs/specimens/`.
