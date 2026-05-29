# NY/CT ownership + compliance — production Playwright QA

Internal QA only. Does not change production logic, layout, routes, copy, or data.

**Artifacts:** `scripts/audit_ny_ct_playwright.py`, `scripts/_ny_ct_playwright_report.json` (regenerated each run).

**Last production pass:** 2026-05-29 — 13/13 checks on `https://www.pbj320.com` (see report JSON timestamp).

---

## When to run

Rerun before major **ownership** or **staffing compliance** deployments (after Render deploy or before promoting a release), in addition to the data/script audits in `docs/staffing_minimums_methodology.md` and `docs/ownership_methodology_audit.md`.

```powershell
# Production (default base)
python scripts/audit_ny_ct_playwright.py --out scripts/_ny_ct_playwright_report.json

# Local app review (server must be running)
python scripts/audit_ny_ct_playwright.py --base http://127.0.0.1:10000 --out scripts/_ny_ct_playwright_report.json
```

Exit code `0` = all checks passed; non-zero = inspect `failures` in the JSON report.

---

## Pass criteria (production sanity)

Treat the audit as **passing** when all of the following hold:

| Area | Expectation |
|------|-------------|
| Owners hub | `/owners/` loads (200), NY + CT entry points present |
| State indexes | `/owners/ny`, `/owners/ct` load (200), owner list populated |
| Owner profiles | Sample PAC profiles load (200), no “profile not found” |
| Provider pages | Sample NY/CT providers load (200), HPRD narrative present |
| Compliance vs API | Visible takeaway warnings align with `/api/provider/<ccn>/staffing-compliance-summary.json` for the same quarter (`available: true` → `summary` fields) |
| NY threshold | **3.56** total nursing HPRD in API `summary.state_min_threshold_used` and on-page minimum copy |
| CT threshold | **3.06** total nursing HPRD in API `summary.state_min_threshold_used` and on-page minimum copy |

API shape: `{ "available": true, "ccn": "...", "quarter": "...", "summary": { ... } }`. A top-level `404` with `available: false` means no bundle row for that facility × quarter (not necessarily a broken page).

---

## CT Q4 sample CCN

**Do not** use CCN `075001` as the CT **CY2025Q4** example: the provider page may show a **prior-quarter** warning while `?quarter=CY2025Q4` correctly returns `available: false`.

Use **`075011`** or another facility with a Q4 row in `data/compliance/staffing_compliance_index.sqlite` (the audit script defaults to `075011` for CT Q4).

---

## Not failures (known scope)

- **State index vs profile facility counts** — different methodology (in-state distinct CCNs on index vs national name-linked facilities on profile). Documented in `docs/ownership_methodology_audit.md` §4. Do not fail Playwright on count mismatch alone.

- **“Reported HPRD not available” in page source** — may appear only in a JS fallback string; audit checks **visible** body text for provider pages.

---

## Performance monitoring (no fix required now)

Watch **cold provider TTFB** on cache miss (`X-PBJ-Provider-Cache: MISS`): first-hit provider pages can reach ~1–3s networkidle / high TTFB while warm hits are often sub-500ms. Log this in deploy smoke notes; no production change from this QA pass.

Owners hub/index/profile routes in this audit typically stay under ~1.5s networkidle and do not load `facility_quarterly_metrics.csv` on the checked paths.

---

## Related audits (data layer, pre-deploy)

```powershell
python scripts/audit_pbj_compliance_data_quality.py
python scripts/audit_staffing_thresholds.py --quarter CY2025Q4
python scripts/audit_ownership_data.py
python scripts/validate_ownership_linkage.py
```
