# Donor dashboard: FEC data and hyperlinks

## Committee master (cm26, cm24, …)

- **Location:** `donor/data/fec_committee_master/cm26_2025_2026.csv`, etc., or fallback `donor/cm26.csv`, `donor/cm24.csv`.
- **Columns:** `CMTE_ID`, `CMTE_NM`, `TRES_NM`, … (see `donor/fec_committee_master_columns.csv`).
- **Designation:** `cm26` = 2025–2026, `cm24` = 2023–2024, `cm22` = 2021–2022 (see `donor/data/fec_committee_master/README.md`).
- **Incorporation:** The donor dashboard **loads committee master at startup** (in `load_data()`). It builds an in-memory map `CMTE_ID` → `CMTE_NM` from available CSVs (newer cycles override older). Committee names shown on the site use this map for **display and verification**: we resolve the name from the master when we have `committee_id`, so names are consistent and fast (no extra API calls). If no master file is present, names fall back to the API/CSV value.

## Form type and docquery path (single place, not random)

All F13 → f132 / other → sa/ALL logic lives in **`donor/fec_api_client.py`**: `FORM_TYPES_USE_SCHEDULE_13A` = `{"F13"}`, `docquery_path_for_form_type()`, `correct_docquery_url_for_form_type()`. Used by `build_schedule_a_docquery_link()`, `_build_docquery_url()`, and `owner_donor_dashboard.py` wherever we set `fec_link`. Other form types (F3, F3P, F3X, F3L) all use Schedule A → sa/ALL; only F13 (inaugural) → Schedule 13-A → f132.

- **How we know F13 → f132:** FEC’s own docquery site uses path `f132` for Form 13 Schedule 13-A. Example: `https://docquery.fec.gov/cgi-bin/forms/C00894162/1889684/f132` shows “SCHEDULE 13-A”. So the mapping is from FEC’s URL convention, not guesswork.
- **No fuzzy matching:** The rule is a basic formula: if `form_type` (from OpenFEC) is exactly `"F13"` (case-normalized), path = `f132`; otherwise path = `sa/ALL`. No similarity or partial matching.
- **What else besides F13?** For **itemized contributions (receipts)** we use: F13 → `f132`, everything else → `sa/ALL`. Form 13 is the only one we know of that uses a different docquery path for receipts (Schedule 13-A → f132); we confirmed that sa/ALL fails for Form 13 (“Invalid Page Number”) and f132 works.
- **Why we’re confident non-F13 use sa/ALL:** (1) **Verified live:** `https://docquery.fec.gov/cgi-bin/forms/C00892471/1930534/sa/ALL` (MAGA Inc., Form 3X) returns “SCHEDULE A - ITEMIZED RECEIPTS”. (2) Other committees’ Schedule A pages use the same `.../sa/ALL` pattern and load (e.g. C00828541/1700115/sa/ALL). (3) FEC docquery uses “sa” for Schedule A; only Form 13 has a differently named schedule (13-A) and path (f132). We don’t have an official FEC document that lists docquery paths by form type; this is based on observed docquery behavior. If you ever see a non-F13 filing where sa/ALL fails, add that form type in `fec_api_client.py`.

## Hyperlinking each donation (View on FEC)

- **Ready:** Each donation can have a **FEC docquery link** when we have `committee_id` and `file_number`. Path: F13 → `.../f132`, else → `.../sa/ALL` (see above).
- **URL pattern:** `https://docquery.fec.gov/cgi-bin/forms/{committee_id}/{image_number}/sa/ALL`
- **Backend:**
  - **Pre-processed donations** (from `owner_donations_database.csv`): We pass `fec_docquery_url` from the CSV as `fec_link`. If the CSV has `committee_id` and `fec_record_id`/`sub_id` but no URL, we build the link with `build_schedule_a_docquery_link(committee_id, image_number=...)`.
  - **Live API** (`/api/query-fec`): Each normalized donation includes `fec_link` from `normalize_fec_donation()` (which uses `fec_docquery_url`).
  - **Entity view** (combined contribution list): Same as pre-processed: `fec_link` from CSV or built from `committee_id` + `fec_record_id`/`sub_id`.
- **Frontend:** The template uses `d.fec_link`; when set, it shows the amount and a “View on FEC” link. No change needed if the backend sends `fec_link`.

## Testing Form 13 (f132) link

- **Concrete example:** Benjamin **Landa**’s $250,000 to **Trump Vance Inaugural Committee** (C00894162). Filing 1910509 is Form 13; the correct link is `https://docquery.fec.gov/cgi-bin/forms/C00894162/1910509/f132`. A stored link of `.../1910509/sa/ALL` is wrong (FEC shows “Invalid Page Number”) and is fixed by `correct_docquery_url_for_form_type()`.
- **Run:** `python donor/build_schedule_a_docquery.py` — includes a Form 13 test (C00894162, 1910509 → f132) and the sa/ALL → f132 corrector test.

## Summary

| Question | Answer |
|----------|--------|
| Are we incorporating cm26 (and cm24, etc.)? | **Yes.** Committee master is loaded at startup from `donor/data/fec_committee_master/*.csv` (or `donor/cm*.csv`). Committee names are resolved by `CMTE_ID` for display/verification; O(1) lookup, no extra API calls. |
| How are cm26/cm24 designated? | **cm26** = 2025–2026, **cm24** = 2023–2024 (see README in `donor/data/fec_committee_master/`). |
| Can we hyperlink each donation? | **Yes.** Each donation includes `fec_link` when we have committee_id + image_number; the UI renders “View on FEC” when `fec_link` is present. |
