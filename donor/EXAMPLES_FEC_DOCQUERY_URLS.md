# FEC docquery URL examples by form type (from OpenFEC API)

**Fix applied (from your manual check):** The example script now gets **file_number from schedule_a** (same as production when we have a schedule_a record), not from `/filings` alone. See “Is the fix actually better?” below for caveats.

**Regenerate URLs:** `python donor/examples_fec_docquery_by_form_type.py`

---

## Is the fix actually better, or could the failures have been one-off?

**What we know:**

- **Theory:** schedule_a’s `file_number` is the filing that contains that Schedule A line. Docquery’s report id is that filing. So when we have a schedule_a record, using its `file_number` is the right id. Using `/filings` we pick “a filing” for the committee (or form type); that filing’s id might not match what docquery expects.
- **Evidence:** We saw 3 failures from ids that came from `/filings` (form_type only, any committee) and 2 successes from schedule_a-derived ids. So there’s a pattern, but the sample is small. We did **not** test production’s actual fallback: when we have no schedule_a record, we call `/filings` for **that committee + date range**. That’s a different use than “one filing per form_type across all committees,” so we don’t know if production’s /filings fallback would have failed for the same committees or if those failures were specific to how the example script called the API.
- **What we changed:** Only the **example script** and docs. **Production was not changed.** Production already prefers schedule_a when present (step 2 in `build_schedule_a_docquery_link`) and falls back to `/filings` (committee + period) when we don’t have schedule_a (step 3). We did not remove or alter that fallback. So we didn’t break anything.
- **Conclusion:** Preferring schedule_a for the report id is **theoretically correct** and **consistent** with what we saw. We can’t be 100% sure the /filings failures weren’t one-off or due to the example script’s different use of /filings (form_type vs committee+period). For accuracy/consistency: when we have a schedule_a record we should use its file_number (we already do). When we don’t, the /filings fallback is best-effort; if you see Invalid Report Id in production, it’s likely in that “no schedule_a, only committee+date” path.

---

## New URLs (from schedule_a — please verify)

These use file_number from schedule_a (docquery-compatible report id):

| Form | committee_id | file_number | URL |
|------|--------------|-------------|-----|
| **F3**  | C00461426 | 788875  | https://docquery.fec.gov/cgi-bin/forms/C00461426/788875/sa/ALL |
| **F3P** | C00890079 | 1858667 | https://docquery.fec.gov/cgi-bin/forms/C00890079/1858667/sa/ALL |
| **F3X**  | C00892471 | 1930534 | https://docquery.fec.gov/cgi-bin/forms/C00892471/1930534/sa/ALL |
| **F3L**  | C00573949 | 1921470 | https://docquery.fec.gov/cgi-bin/forms/C00573949/1921470/sa/ALL |

---

## Manual check results (user-verified, before fix)

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

**Fix:** In production we already prefer file_number from the schedule_a record when building links. The example script was updated to do the same so it outputs URLs that docquery accepts. Link logic unchanged: F13 → f132, all others → sa/ALL.
