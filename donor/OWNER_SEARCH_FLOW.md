# Owner Search & Owner Page Flow (Step-by-Step)

## Scenario: User types "benjamin landa" (Search by Owner)

---

### 1. User is on the owners dashboard

- **Page:** `/owners` (or `/owners/` with search section visible).
- **Shown:** Search box, "Search by Owner" (or Individual/Organization) dropdown, optional autocomplete dropdown (hidden until typing).

---

### 2. User types "benjamin landa" in the search input

- **Frontend:** Input fires debounced handler (200 ms).
- **Request:** `GET /owners/api/autocomplete?q=benjamin%20landa&type=all` (or `individual` / `organization` if user changed dropdown).
- **Backend:** Uses **internal data only** — `owners_df` (CSV or Parquet, e.g. `owners_database.csv` / `owners_database.parquet`). No FEC API.
  - Filters by name: `owner_name_original`, `owner_name` (contains/collapsed middle initials).
  - Sorts by rows that have `associate_id_owner` (PAC 10-digit) first.
  - Returns up to 10 **suggestions**: `{ name, type, facilities (count), id }`.  
  - `id` = normalized 10-digit `associate_id_owner` when present; otherwise `null`.
- **Frontend:** Renders autocomplete dropdown with those suggestions.

---

### 3a. User **clicks** an autocomplete suggestion **that has an ID**

- **Action:** `selectAutocompleteOwnerId(ownerId)` (e.g. `7810804515`).
- **Frontend:** `window.location.href = '/owners/7810804515'`.
- **Result:** Browser navigates **directly to the owner page**. No results card. No search API call.

---

### 3b. User **clicks** an autocomplete suggestion **without an ID**

- **Action:** `selectAutocomplete(name)` → fills input → `performSearch()`.
- **Request:** `GET /owners/api/search?q=benjamin%20landa&type=all`.
- **Backend:** Same **internal** `owners_df`. Name search (exact, first+last, all-words, etc.). Returns `{ results: [...], count }`. Each result includes `associate_id_owner` when available (10-digit).
- **Frontend:** If `count === 1` and `results[0].associate_id_owner` is 9–11 digits → **redirect** to `/owners/<id>`. No card.
- **Frontend:** If multiple results or no ID → **results card(s)** show. Each card either: link to `/owners/<id>` (if ID present) or card with "Political Contributions" and "Providers" buttons (if no ID).

---

### 3c. User **does not** pick autocomplete; presses Enter or clicks Search

- **Request:** `GET /owners/api/search?q=benjamin%20landa&type=all`.
- **Backend:** Same as 3b — internal `owners_df` only.
- **Frontend:** Same as 3b — either redirect if 1 result with ID, or show results card(s).

---

### 4. User is now on the **owner page** `/owners/7810804515`

- **Page load:** `<body data-initial-owner-id="7810804515">` → script calls `showOwnerDetails('7810804515')` (ID, not name).
- **Request:** `GET /owners/api/owner/7810804515` (path param = **ID**).
- **Backend:** `get_owner_details(owner_name="7810804515")`:
  - Treats path as ID: `_normalize_associate_id("7810804515")` → `"7810804515"`.
  - Finds row in **internal** `owners_df` where `associate_id_owner` matches.
  - Sets `matched_by_id = True` and **never** uses the path param as the display name.
  - Display name from row: `_safe_owner_name_from_row(owner_row, exclude_id=...)` → e.g. `"BENJAMIN LANDA"` (from `owner_name_original` / `owner_name`).
  - Response: `owner_name`, `owner_name_original`, `owner_type`, `facilities`, `associate_id_owner`, etc. **All name fields are the real name, not the ID.**
- **Frontend:** `currentOwner = response`. Renders title and "Political Contributions" button with **name**:  
  `queryFecApiForOwner('BENJAMIN LANDA', 'INDIVIDUAL')`.

---

### 5. User clicks **"Political Contributions"** on the owner page

- **Action:** `queryFecApiForOwner('BENJAMIN LANDA', 'INDIVIDUAL')`.
- **Request:** `POST /owners/api/query-fec`  
  Body: `{ "owner_name": "BENJAMIN LANDA", "owner_type": "INDIVIDUAL" }`.  
  **Uses name only; no ID.**
- **Backend:**  
  - Validates `owner_name` non-empty → if empty, returns **400 Bad Request** "Owner name required".  
  - Uses **name only**: `normalize_name_for_search(owner_name, owner_type)` (middle-name variants, "First Last", "Last, First", etc.), then `query_donations_by_name(...)` → **FEC API** by contributor name.  
  - Returns 200 + donations (or empty list).
- **Frontend:** Shows loading, then donations in `donationsContainer`. No 400 if name was sent correctly.

---

### 6. When **400 Bad Request** used to happen (before fix)

- If the **owner page** API had returned `owner_name` or `owner_name_original` as the **ID** (`7810804515`) or empty (e.g. row had no name in CSV/parquet):
  - The button would be `queryFecApiForOwner('7810804515', 'INDIVIDUAL')` or `queryFecApiForOwner('', 'INDIVIDUAL')`.
  - POST body would have `owner_name: '7810804515'` or `owner_name: ''`.
  - Backend would either reject empty name → **400 Bad Request** "Owner name required", or treat the ID as a name and query FEC by that string (wrong).
- **Fix:** Owner lookup by ID now always uses `_safe_owner_name_from_row` and `matched_by_id` so the API response never sends the ID as the name and never sends empty name when a row exists. Frontend also falls back to `currentOwner.owner_name_original` / `currentOwner.owner_name` when the passed value is empty or looks like an ID.

---

## Data sources summary

| Step                    | Data source              | Uses name vs ID                    |
|-------------------------|--------------------------|------------------------------------|
| Autocomplete            | Internal: `owners_df`    | Search by **name**; return **id** when present for redirect. |
| Search (single/multiple)| Internal: `owners_df`    | Search by **name**; return **associate_id_owner** for redirect/card link. |
| Owner page load         | Internal: `owners_df`    | Lookup by **ID** (path); response uses **name** from row. |
| Political Contributions | FEC API (on-demand)      | **Name only** (with name variants). No ID. |

---

## One-line summary

**User types "benjamin landa"** → autocomplete/search use **internal CSV/parquet** by **name**; if a suggestion or single result has an **ID**, user goes **directly to `/owners/<id>`**; on that page, data is loaded by **ID** but the **Political Contributions** button sends only the **name** to the FEC API. A **400 Bad Request** happened when the owner-page API mistakenly returned the ID (or empty) as the owner name; that is now fixed so the button always sends the real name.
