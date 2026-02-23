# Ownership / Provider Search: Process and Fixes

This document records the exact process and issues corrected to get provider search (and related ownership/FEC display) working on both local and the public website (Render).

---

## 1. Initial Problem: Provider Search Broken

**Symptom:** Provider search (e.g. "Seagate Rehabilitation and Nursing Center" or CCN 335513) returned **500** with:

```
KeyError: 'ORGANIZATION NAME'
  File donor/owner_donor_dashboard.py, line 2497, in search_by_provider
    ownership_data_to_search['ORGANIZATION NAME'].astype(str)...
```

**Root cause:** The code assumed the ownership DataFrame always had a column named `'ORGANIZATION NAME'`. In reality:

- **Raw ownership file** (`ownership/SNF_All_Owners_Jan_2026.csv`) has `ORGANIZATION NAME`.
- **Normalized ownership file** (`donor/output/ownership_normalized.csv`) does **not**; it has `facility_name` (and other normalized columns).
- On **Render**, the raw file is **never loaded** (skipped to save memory: `if os.environ.get("RENDER") == "true": ownership_raw_df = pd.DataFrame()`). So `ownership_data_to_search` falls back to `ownership_df` (normalized), which has no `'ORGANIZATION NAME'`.

**Fix 1a – Support both schemas:** After setting `ownership_data_to_search`, determine the facility/org name column:

- If `'ORGANIZATION NAME'` exists → use it (raw).
- Else if `'facility_name'` exists → use it (normalized).
- Else → `org_name_col = None` and guard all uses.

All logic that matched Legal Business Name to ownership data now uses `org_name_col` (and only runs when `org_name_col` is set). Same for CCN-based lookup: use `org_name_col` when reading org names from ownership matches.

**Fix 1b – CCN → ENROLLMENT ID matching:** When finding organization names from ownership data by CCN, the code was comparing the **full** ENROLLMENT ID (e.g. `O20020801000000`, 14 digits) to the 6-digit CCN. They never matched. **Fix:** Match on the **last 6 digits** of ENROLLMENT ID to the CCN (same rule as in the raw-ownership block):

```python
ccn_6 = ccn.zfill(6)
enroll_clean = ownership_data_to_search[enroll_col].astype(str).str.replace('O', '').str.replace(' ', '').str.replace('-', '').str.strip()
ownership_matches = ownership_data_to_search[enroll_clean.str[-6:] == ccn_6]
```

**Fix 1c – Direct-ownership block:** The block that reads `ownership_raw_df['ORGANIZATION NAME']` for direct owners now only runs when `'ORGANIZATION NAME' in ownership_raw_df.columns`, so it never assumes that column exists.

---

## 2. "Invalid Server Response" on Provider Search

**Symptom:** Provider search returned **200** but the frontend showed "Invalid server response." (from `response.json()` failing).

**Root cause:** The response body contained values that are not JSON-serializable (e.g. `numpy.int64`, `numpy.bool_`, `pd.NA`, or NaN from pandas). Flask’s `jsonify()` can fail or produce invalid JSON when such values are present in the payload.

**Fix:** Run the provider-search response through the existing `sanitize_for_json()` helper before `jsonify()`. That helper recursively replaces NaN/Inf/pd.NA with `None` and converts numpy scalars (e.g. from DataFrame rows) to native Python via `.item()`. So the payload is always JSON-serializable and parseable in the browser.

```python
payload = {'results': formatted, 'count': len(formatted), 'provider_info': provider_info}
return jsonify(sanitize_for_json(payload))
```

---

## 3. Slower Site / First Render (or First Request) Failing

**Symptom:** Website felt slower; "the first render thing even failed" (first request to `/owners/` could time out).

**Root cause:** `load_data()` loaded the heaviest CSVs **sequentially** (owners_db, donations_db, ownership_norm, then committee_master, raw ownership, provider info, etc.). The first request to the owner dashboard triggers this load; on Render, request timeouts could kill the request.

**Fix:** Load the three heaviest **independent** files in **parallel** at the start of `load_data()` using `ThreadPoolExecutor(max_workers=3)`:

- Owners database (`owners_database.csv`)
- Donations database (`owner_donations_database.csv`)
- Normalized ownership (`ownership_normalized.csv`)

A small inner helper `_read_csv(path)` does utf-8 / utf-8-sig / latin-1 fallback. After the executor completes, we assign globals and run the same post-processing (e.g. owners `fillna`, warnings) as before. The rest of `load_data()` (committee_master, raw ownership, provider info, facility mapping, etc.) is unchanged. This shortens the first-request time and reduces the chance of timeouts.

---

## 4. Committee Name Display: MAGA, RNC, DNC, DSCC etc.

**Symptom:** FEC search showed "Maga Inc." instead of "MAGA Inc.", and similar for RNC, DNC, DSCC, etc.

**Root cause:** `title_case_committee` (backend) and `toTitleCaseCommittee` (frontend) only uppercased these when the **entire** string was the acronym (e.g. `"RNC"`). When the string was multi-word (e.g. `"Maga Inc."`), the word "Maga" was title-cased to "Maga", not "MAGA".

**Fix:** Treat these as **words** that should always display in all caps:

- **Backend (`donor/display_utils.py`):** Added `ACRONYM_WORDS = frozenset("maga rnc dnc dscc nrcc dccc nrsc hmp pac".split())`. When building the title-cased string word-by-word, if the cleaned word is in `ACRONYM_WORDS`, append `word.upper()`. Whole-string check: if the entire name is one of these, return `s.upper()`.
- **Frontend (`donor/templates/owner_donor_dashboard.html`):** Added `committeeAcronymWords` and, after `toTitleCase(s)`, replace each acronym **as a word** (word-boundary regex) with its uppercase form. Whole-string: if the trimmed lowercased string is in that list, return `s.toUpperCase()`.

---

## 5. State Codes (NY), USA, and Other 2–3 Letter Nonwords

**Symptom:** User wanted state codes (e.g. NY), USA, US, and other 2–3 letter nonwords to display in all caps where appropriate.

**What was already there:** Backend had `state_abbrevs` (all 2-letter US state + DC) and `acronym_words = {"usa"}`. Frontend had `stateAbbrevs` and `\busa\b` → USA.

**Fix:** Centralize and extend 2–3 letter all-caps handling:

- **Backend:** Added `CAPS_2_3_LETTER = frozenset("usa us fec cms irs fda cdc gop dhs doj hhs osha".split())`. In the word loop, if the cleaned word is in `CAPS_2_3_LETTER`, append `word.upper()`. Whole-string: if the entire name is in `CAPS_2_3_LETTER`, return `s.upper()`. State codes remain handled via existing `state_abbrevs` (2-letter).
- **Frontend:** Added `caps23Letter = ['usa','us','fec','cms','irs','fda','cdc','gop','dhs','doj','hhs','osha']`. After title-case, replace each of these as a word with uppercase; also `\bus\b` → US. Whole-string: if the string is in `caps23Letter`, return `s.toUpperCase()`. State abbrevs already applied via `stateAbbrevs`.

---

## 6. Provider Search on Public Site: No Owner List

**Symptom:** On the **public website** (Render), provider search (e.g. Seagate) showed the header ("Ownership of Seagate Rehabilitation and Nursing Center (Shorefront Operating Llc)", CCN, Dashboard, CMS link) but **no list of owners/managers**. Locally, the list appeared.

**Root cause:** The template’s `displayResults()` for provider search only rendered:

1. The **header** (provider name, CCN, state, Dashboard link, CMS link).
2. The **"All Owners and Managers"** block, which is built **only** from `provider_info.direct_owners`.

On Render, the raw ownership file is not loaded, so `direct_owners` is always `[]`. The API **does** return `results` (owners from `owners_df` matched by facility name, e.g. Shorefront Operating LLC), but the template **did not** use `results` for provider search—it returned after rendering the header, so no owner cards were shown.

**Fix:** In `displayResults()`, when `searchType === 'provider'`:

- If `direct_owners.length === 0` **and** `results.length > 0`, render an **"Owners and Managers"** section using `results`: each owner as a card with name, facilities snippet, and **Contributions** / **Providers** buttons (same actions as owner-search result cards).
- If `direct_owners.length > 0` (e.g. local with raw file), keep existing behavior: show the header’s detailed list with percentages and dates; do not duplicate with result cards.

So on the public site, provider search now shows the same header **plus** the owner(s) from the API (e.g. Shorefront Operating LLC) with Contributions and Providers, instead of only the header and no owner list.

---

## Summary of Files Touched

| File | Changes |
|------|--------|
| `donor/owner_donor_dashboard.py` | `org_name_col` / `facility_name` support; CCN match last 6 of ENROLLMENT ID; guard direct_ownership on raw columns; `sanitize_for_json(payload)` for provider search response; parallel load of owners/donations/ownership_norm in `load_data()`; direct_ownership block only if `'ORGANIZATION NAME' in ownership_raw_df.columns`. |
| `donor/display_utils.py` | `ACRONYM_WORDS`; `CAPS_2_3_LETTER`; word-loop and whole-string handling for acronyms and 2–3 letter abbrevs; state codes already present. |
| `donor/templates/owner_donor_dashboard.html` | `toTitleCaseCommittee`: acronym words + `caps23Letter` + state abbrevs; provider search: when `direct_owners` empty, render "Owners and Managers" from `results` (owner cards with Contributions/Providers). |

---

## Testing Suggestions

- **Provider by name:** Search "Seagate" (or full "Seagate Rehabilitation and Nursing Center") on both local and public site; expect owner list (e.g. Shorefront Operating LLC) and no 500 / invalid response.
- **Provider by CCN:** Search "335513" on both; same expectations.
- **Committee names:** Search a committee (e.g. MAGA Inc.); expect "MAGA Inc." and RNC/DNC/DSCC etc. in all caps where used.
- **State / USA / abbrevs:** Check any display that includes state codes, USA, US, FEC, CMS, etc.; expect consistent all-caps for those tokens.
