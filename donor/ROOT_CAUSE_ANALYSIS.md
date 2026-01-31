# Root Cause: False Attribution of $1M Donation

## What Happened

User searched for **CORPORATE INTERFACE SERVICES LLC** (a nursing home owner) and saw a **$1,000,000** donation to **TRUMP VANCE INAUGURAL COMMITTEE** attributed to them.

**Reality:** That $1M donation is from **CAPITAL ONE SERVICES LLC CORPORATE** (and other $1M donors: AT&T, Textron, Lockheed, etc.) — **not** from CORPORATE INTERFACE SERVICES LLC.

---

## Root Cause: Overly Broad Name Variations + FEC Fuzzy Matching

### 1. We generate search variations

When user searches "CORPORATE INTERFACE SERVICES LLC", `normalize_name_for_search()` returns:

```
['CORPORATE INTERFACE SERVICES LLC', 'CORPORATE', 'CORPORATE LLC']
```

### 2. We search FEC with each variation

In `query_fec` (owner_donor_dashboard.py ~1978), we call:

```python
query_donations_by_name(contributor_name="CORPORATE", ...)
query_donations_by_name(contributor_name="CORPORATE LLC", ...)
# etc.
```

### 3. FEC API does fuzzy/partial matching

The FEC `contributor_name` parameter matches **any** contributor whose name **contains** the search term.

- Search: `"CORPORATE"`
- FEC returns: **"CAPITAL ONE SERVICES LLC CORPORATE"** (contains "CORPORATE")
- And many others with "CORPORATE" in the name

### 4. We don't show the actual contributor

The `query_fec` response does **not** include `donor_name` / `contributor_name`:

```python
normalized.append({
    'amount': ...,
    'date': ...,
    'committee': ...,
    'candidate': ...,
    # NO donor_name!
})
```

The UI shows "Political Contributions - **CORPORATE INTERFACE SERVICES LLC**" (the searched owner) as the page header. Each contribution shows amount, date, committee — but **not** who actually gave it. So the user infers "these are Corporate Interface's donations" when some are false positives from other entities.

---

## Result

1. User searches "CORPORATE INTERFACE SERVICES LLC"
2. We search FEC with "CORPORATE" (among other variations)
3. FEC returns "CAPITAL ONE SERVICES LLC CORPORATE" $1M to Trump Vance (and others)
4. We display it under the Corporate Interface header
5. We never show that the actual contributor was CAPITAL ONE
6. User believes Corporate Interface gave $1M → **false attribution**

---

## Recommended Fixes

1. **Include `donor_name` in the API response** — Always pass through `contributor_name` from FEC so the UI can display "From: [actual FEC contributor]" on each donation.

2. **Filter results by name similarity** — Before returning donations, check that FEC `contributor_name` is reasonably similar to the owner we searched for (e.g., normalized edit distance, or require key tokens to match). Exclude clear false positives like "CAPITAL ONE" when searching "CORPORATE INTERFACE".

3. **Restrict name variations** — Avoid single-word variations like "CORPORATE", "SERVICES", "LLC" that match too broadly. Require at least 2–3 significant words (e.g., "CORPORATE INTERFACE") for organization searches.

4. **UI disclaimer** — When displaying FEC results, add a note: "FEC uses fuzzy matching. Verify contributor names on the Source link."
