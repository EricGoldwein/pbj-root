# Staffing minimums & daily threshold flags (internal)

Last reviewed: 2026-05-28 (copy pass). Public surfaces: provider PBJ Takeaway warning bar, `/data-sources#pbj-daily-staffing`, `/api/provider/<ccn>/staffing-compliance-summary.json`.

**Build source of truth:** `PBJapp/pbj_staffing_compliance_summary.py` + `PBJapp/config/staffing_compliance_thresholds.json`.  
**Shipped copy in pbj-root:** `data/compliance/staffing_compliance_thresholds.json` (must stay in sync on export).  
**Runtime loader:** `staffing_compliance_bundle.py` → `app._provider_staffing_compliance_warning()`.

---

## Three kinds of “minimum” language (do not conflate)

| Kind | What it means | Examples on PBJ320 |
|------|----------------|-------------------|
| **Statutory / direct-care minimum** | State law or rule text describing required direct-care hours per resident per day | NY narrative ~3.50 HPRD in `about.html` / Seagate press; CT PA Sec. 10 (~3.0 direct care) cited in config notes |
| **MACPAC total estimated staffing requirement** | MACPAC state compendium summary of total nursing HPRD equivalent | NY **3.56**; CT **3.06** — see [MACPAC state staffing standards](https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/) |
| **PBJ320 operational threshold** | Configured daily screen: total nursing HPRD (all PBJ nursing roles incl. admin/DON) ÷ census, days with census > 0 | NY **3.56**; CT **3.06** in `staffing_compliance_thresholds.json` |

**PBJ total nursing HPRD may not equal statutory direct-care staffing.** PBJ320 reports **days below threshold** from CMS PBJ; it does **not** make legal findings of violation or noncompliance.

---

## Operational thresholds (configured)

| State | Threshold | Metric | Label type |
|-------|-----------|--------|------------|
| **NY** | **3.56** | `total_nurse_hprd` | MACPAC total estimated staffing requirement applied as PBJ daily total nursing HPRD threshold |
| **CT** | **3.06** | `total_nurse_hprd` | Same; **not 3.56** |

**Verified from:** `data/compliance/staffing_compliance_thresholds.json`, `data/compliance/staffing_compliance_manifest.json` (`states_with_thresholds`: CT, NY).

---

## Valid day criteria (daily PBJ rows)

**Verified from:** `PBJapp/pbj_staffing_compliance_summary.py` `build_quarter_compliance_duckdb()`:

- Include row only if `MDScensus > 0`.
- No explicit filter on negative hours, implausible HPRD, or duplicate `(PROVNUM, WorkDate)` in SQL (P2).
- Quarter = `PBJ_dailynursestaffing_CY{YYYY}Q{n}.csv`.

---

## Daily formulas

```
total_nurse_hours = sum(8 PBJ role columns, COALESCE→0 in SQL)
total_nurse_hprd = total_nurse_hours / MDScensus
flag if total_nurse_hprd < threshold AND state matches NY or CT
```

Global RN rules (all states in bundle): `total_rn_hours == 0`; `total_rn_hours < 8` (absolute hours).

---

## Public copy (2026-05-28)

| Surface | Wording |
|---------|---------|
| Provider warning bar | `{N} of {M} reported PBJ days below {State}'s {threshold} total nursing HPRD threshold.` |
| Methodology (`data-sources.html`) | NY 3.56, CT 3.06 MACPAC total estimated staffing; no legal findings |
| Seagate (`about.html` / `press.html`) | **3.50** preserved for statutory/narrative context; note clarifies **3.56** operational screen |

**Avoid:** violation, illegal, noncompliant, compliance failure, failed the law.

**Acceptable:** minimum staffing threshold, state minimum requirement (when tied to state/MACPAC context), days below threshold.

---

## Known limitations (P2 — not implemented)

1. **COALESCE(hours, 0)** — missing hour fields would count as zero and can inflate `rn_0` / below-threshold flags. **Latent in SQL; no impact on NY/CT 2025 bundle** (audited — see `docs/data_quality_and_fallbacks_audit.md` § Staffing compliance bundle QA).
2. **No HPRD upper bound** in compliance build (unlike portfolio rollup 1.5–12). Extreme HPRD days exist (low census) but did not inflate below-threshold counts in 2025 NY/CT audit.
3. **Duplicate daily rows** — not deduped in SQL. **None found** in NY/CT 2025 standardized inputs.
4. **Quarter coverage** — bundle ships configured quarters only; older quarters show no warning.

---

## QA before publish

```powershell
# Data quality on PBJ source files (COALESCE, dupes, extreme HPRD, source vs bundle)
python scripts/audit_pbj_compliance_data_quality.py

# Threshold consistency and sample CCN
python scripts/audit_staffing_thresholds.py --ccn 335513 --quarter CY2025Q4
```

Compare to `/api/provider/<ccn>/staffing-compliance-summary.json?quarter=CY2025Q4`.

Rerun `audit_pbj_compliance_data_quality.py` before each new bundle export or new state rollout. Details: `docs/data_quality_and_fallbacks_audit.md` (pre-export guardrail).

---

## Unresolved

- [ ] Vendor full NY/CT statute/reg text in repo and map direct-care vs total nursing.
- [ ] Confirm CT DPH adopted rule vs 3.06 total nursing MACPAC line.
