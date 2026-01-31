# Donation Source Traceback — $1M to TRUMP VANCE INAUGURAL COMMITTEE

## Summary

**Committee:** TRUMP VANCE INAUGURAL COMMITTEE, INC. (C00894162)  
**Date range:** 2025-01-01 to 2025-01-31  
**Target:** Contributions >= $900,000  

---

## Direct Source (authoritative FEC filing)

**Schedule A Docquery URL:**
```
https://docquery.fec.gov/cgi-bin/forms/C00894162/1910509/sa/ALL
```

This URL points to the filed Schedule A form. Open it in a browser to see the exact contributor names as reported to the FEC.

---

## Data Flow (traceback)

| Step | Source | Field | Our display |
|------|--------|-------|-------------|
| 1 | FEC API | `https://api.open.fec.gov/v1/schedules/schedule_a` | — |
| 2 | API params | `committee_id=C00894162`, `min_date=2025-01-01`, `max_date=2025-01-31` | — |
| 3 | Raw record | `contributor_name` | `donor_name` |
| 4 | Raw record | `contribution_receipt_amount` | `donation_amount` |
| 5 | Raw record | `contribution_receipt_date` | `donation_date` |
| 6 | Raw record | `file_number` | Docquery URL path segment |
| 7 | Our code | `fec_api_client.normalize_fec_donation()` | Normalized record |
| 8 | Our code | `_build_docquery_url(committee_id, file_number)` | `fec_link` / `fec_docquery_url` |
| 9 | Display | `owner_donor_dashboard` passes `fec_link` in `raw_contributions` | "Source" / FEC link in UI |

---

## FEC API Results (Jan 2025, >= $900k)

The FEC API returned **10 contributions** of $1,000,000 each:

| # | contributor_name (from FEC) | Date | file_number |
|---|-----------------------------|------|-------------|
| 1 | AT&T SERVICES, INC | 2025-01-28 | 1910509 |
| 2 | TEXTRON, INC. | 2025-01-17 | 1910509 |
| 3 | LOCKHEED MARTIN CORPORATION | — | 1910509 |
| 4 | X CORP | — | 1910509 |
| 5 | TANG FAMILY TRUST DTD | — | 1910509 |
| 6 | HIMS, INC. | — | 1910509 |
| 7 | EMED LLC | — | 1910509 |
| 8 | NVIDIA CORPORATION | — | 1910509 |
| 9 | ASHBRITT, INC. | — | 1910509 |
| 10 | ANHEUSER BUSCH COMPANIES | 2025-01-13 | 1910509 |

---

## Finding: CORPORATE INTERFACE and CAPITAL ONE

**Neither CORPORATE INTERFACE SERVICES LLC nor CAPITAL ONE SERVICES LLC CORPORATE** appears in the FEC API results for $1M contributions to TRUMP VANCE INAUGURAL COMMITTEE in January 2025.

If the dashboard showed CORPORATE INTERFACE SERVICES LLC for a $1M donation to this committee, the source of that display would be different from the FEC Schedule A data queried above (e.g., different committee, date range, or view such as owner search).

---

## How to Re-run the Traceback

```bash
cd donor
python trace_donation_source.py
```

Requires `FEC_API_KEY` in `donor/.env` or environment.
