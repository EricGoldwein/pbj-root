# Donor dashboard: FEC data and hyperlinks

## Committee master (cm26, cm24, …)

- **Location:** `donor/data/fec_committee_master/cm26_2025_2026.csv`, etc., or fallback `donor/cm26.csv`, `donor/cm24.csv`.
- **Columns:** `CMTE_ID`, `CMTE_NM`, `TRES_NM`, … (see `donor/fec_committee_master_columns.csv`).
- **Designation:** `cm26` = 2025–2026, `cm24` = 2023–2024, `cm22` = 2021–2022 (see `donor/data/fec_committee_master/README.md`).
- **Incorporation:** The donor dashboard **loads committee master at startup** (in `load_data()`). It builds an in-memory map `CMTE_ID` → `CMTE_NM` from available CSVs (newer cycles override older). Committee names shown on the site use this map for **display and verification**: we resolve the name from the master when we have `committee_id`, so names are consistent and fast (no extra API calls). If no master file is present, names fall back to the API/CSV value.

## Hyperlinking each donation (View on FEC)

- **Ready:** Each donation in the contributor/contribution list can now have a **FEC docquery link** when we have `committee_id` and `image_number` (or `sub_id` / `fec_record_id`).
- **URL pattern:** `https://docquery.fec.gov/cgi-bin/forms/{committee_id}/{image_number}/sa/ALL`
- **Backend:**
  - **Pre-processed donations** (from `owner_donations_database.csv`): We pass `fec_docquery_url` from the CSV as `fec_link`. If the CSV has `committee_id` and `fec_record_id`/`sub_id` but no URL, we build the link with `build_schedule_a_docquery_link(committee_id, image_number=...)`.
  - **Live API** (`/api/query-fec`): Each normalized donation includes `fec_link` from `normalize_fec_donation()` (which uses `fec_docquery_url`).
  - **Entity view** (combined contribution list): Same as pre-processed: `fec_link` from CSV or built from `committee_id` + `fec_record_id`/`sub_id`.
- **Frontend:** The template uses `d.fec_link`; when set, it shows the amount and a “View on FEC” link. No change needed if the backend sends `fec_link`.

## Summary

| Question | Answer |
|----------|--------|
| Are we incorporating cm26 (and cm24, etc.)? | **Yes.** Committee master is loaded at startup from `donor/data/fec_committee_master/*.csv` (or `donor/cm*.csv`). Committee names are resolved by `CMTE_ID` for display/verification; O(1) lookup, no extra API calls. |
| How are cm26/cm24 designated? | **cm26** = 2025–2026, **cm24** = 2023–2024 (see README in `donor/data/fec_committee_master/`). |
| Can we hyperlink each donation? | **Yes.** Each donation includes `fec_link` when we have committee_id + image_number; the UI renders “View on FEC” when `fec_link` is present. |
