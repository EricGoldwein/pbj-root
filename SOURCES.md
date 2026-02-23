# PBJ320 — Canonical sources, contact & link structure

Use this file as the single reference for official external URLs, contact details, and site link structure. Keep all in-product links and copy consistent with these.

---

## External data sources (canonical URLs)

Use these exact URLs everywhere (About, index, PBJPedia, etc.):

| Label | Canonical URL |
|-------|----------------|
| **CMS Payroll-Based Journal (PBJ)** | https://data.cms.gov/quality-of-care/payroll-based-journal-daily-nurse-staffing |
| **Provider Information** | https://data.cms.gov/provider-data/dataset/4pq5-n9py |
| **Affiliated Entity / Chain performance** | https://data.cms.gov/quality-of-care/nursing-home-chain-performance-measures/data |
| **MACPAC State Staffing Standards** | https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/ |

---

## PBJ320 contact

- **Email:** eric@320insight.com  
- **Phone / SMS:** (929) 804-4996 (text preferred)  
- **320 Consulting:** https://www.320insight.com  
- **Newsletter:** https://320insight.substack.com  

---

## Site link structure (pbj320.com)

Use these patterns for internal links. Do **not** use `pbjdashboard.com` or `/test/` paths in public copy or links.

| Page type | Canonical pattern | Example |
|-----------|-------------------|--------|
| **Home** | `https://pbj320.com/` | — |
| **Provider (facility)** | `https://pbj320.com/provider/{CCN}` | https://pbj320.com/provider/335513 |
| **Entity (chain)** | `https://pbj320.com/entity/{id}` | https://pbj320.com/entity/237 |
| **State** | `https://pbj320.com/state/{slug}` | https://pbj320.com/state/pa, https://pbj320.com/state/new-york |
| **Phoebe / PBJ Explained** | `https://pbj320.com/phoebe` | — |
| **About** | `https://pbj320.com/about` | — |
| **Report** | `https://pbj320.com/report` | — |
| **SFF** | `https://pbj320.com/sff` | — |
| **Owners** | `https://pbj320.com/owners` | — |
| **Wrapped** | `https://pbj320.com/wrapped` | — |

Legacy `/test/provider/...`, `/test/state/...`, `/test/entity/...` URLs redirect 301 to the canonical paths above.

---

## Related docs

- **DATA_SOURCES.md** — Where data files live (CSVs, JSON, gitignored vs in-repo).  
- **AUDIT_DATA_ACCURACY.md** — Data accuracy and rounding conventions.
