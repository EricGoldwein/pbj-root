# FEC docquery URL examples by form type (from OpenFEC API)

These URLs are **derived from the actual FEC API** (OpenFEC `/filings` with `form_type`). We build them with `committee_id` + `file_number` from the API and path `sa/ALL`. Manual check results below show that **the API’s `file_number` is not always a valid docquery report id** — docquery can return “Invalid Report Id” even when the path (sa/ALL) is correct.

**Regenerate candidate URLs:** `python donor/examples_fec_docquery_by_form_type.py`

---

## Manual check results (user-verified)

| Form | committee_id | file_number | URL | Result |
|------|--------------|-------------|-----|--------|
| **F3**  | C00541474 | 948970  | …/C00541474/948970/sa/ALL | **Invalid** — Error #2.1 Invalid Report Id =948970. Committee page …/C00541474/ lists filings but this id not accepted. |
| **F3P** | C00890079 | 1945805 | …/C00890079/1945805/sa/ALL | **Invalid** — …/1945805/ (no sa/ALL) loads Form 3P summary; …/1945805/sa/ALL was invalid. |
| **F3X**  | C00465294 | 758677  | …/C00465294/758677/sa/ALL | **Invalid** — Error #2.1 Invalid Report Id =758677. |
| **F3X**  | C00892471 | 1930534 | …/C00892471/1930534/sa/ALL | **Works** — MAGA Inc., Schedule A itemized receipts. |
| **F3L**  | C00573949 | 1943222 | …/C00573949/1943222/sa/ALL | **Works** — Josh Gottheimer for Congress, Schedule A. |

**Takeaways:**

- **Path sa/ALL is correct** for F3, F3P, F3X, F3L when the report id is valid (F3L and MAGA F3X work with sa/ALL). The failures are due to **report id**, not path.
- **OpenFEC `file_number` ≠ docquery report id in all cases.** The API sometimes returns a value (e.g. 948970, 758677) that docquery rejects as “Invalid Report Id”. We should use the same id we use for the form summary (e.g. from docquery’s own listing or from a field that docquery accepts).
- **F3P:** The form page …/C00890079/1945805/ loads; sa/ALL for that report was invalid — could be that this report has no Schedule A, or Schedule A is under a different path for 3P; needs follow-up if we need 3P links.

---

## Verified working (use for manual checks)

- **F3X (PAC):** https://docquery.fec.gov/cgi-bin/forms/C00892471/1930534/sa/ALL (MAGA Inc.)
- **F3L:** https://docquery.fec.gov/cgi-bin/forms/C00573949/1943222/sa/ALL (Josh Gottheimer for Congress)

---

## F3 (House/Senate) — API example failed docquery

- **committee_id:** C00541474 (Committee to Elect Shawn Pinkston)
- **file_number from API:** 948970 → **Invalid Report Id** on docquery.

---

## F3P (Presidential) — base form loads, sa/ALL invalid

- **committee_id:** C00890079 (Conservative American Middle Eastern PAC)
- **file_number:** 1945805 — …/C00890079/1945805/ shows Form 3P summary; …/1945805/sa/ALL was invalid.

---

## F3X (PAC/party)

- **Works:** C00892471 / 1930534 (MAGA Inc.) — https://docquery.fec.gov/cgi-bin/forms/C00892471/1930534/sa/ALL  
- **Invalid:** C00465294 / 758677 — Error #2.1 Invalid Report Id.

---

## F3L (Lobbyist bundling)

- **Works:** C00573949 / 1943222 — https://docquery.fec.gov/cgi-bin/forms/C00573949/1943222/sa/ALL  

---

**For link logic:** We keep F13 → f132, all others → sa/ALL. When a link fails with “Invalid Report Id”, the cause is the **id** (file_number) we got from the API, not the path. Improving id source (e.g. prefer docquery-compatible id from filings or schedule_a) would be a separate change.
