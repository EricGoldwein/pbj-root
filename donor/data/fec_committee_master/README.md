# FEC Committee Master (local, no API)

Committee master files are **uploaded beforehand** and stored here. They are **not** fetched by API at runtime.

**Source:** [FEC bulk data – Committee master](https://www.fec.gov/data/browse-data/?tab=bulk-data)  
**Format:** Pipe-delimited `.txt` inside `cmNN.zip` (e.g. cm26.zip, cm24.zip). Convert to CSV with `donor/fec_committee_master_to_csv.py`.

## File naming (by cycle)

**Designation:** The `cmNN` number is the **election cycle** (two years).  
- **cm26** = 2025–2026  
- **cm24** = 2023–2024  
- **cm22** = 2021–2022  
- (cm20 = 2019–2020, etc.)

| Zip / cycle | Label | CSV filename (use this) |
|-------------|--------|---------------------------|
| cm26.zip    | 2025–2026 | `cm26_2025_2026.csv` |
| cm24.zip    | 2023–2024 | `cm24_2023_2024.csv` |
| cm22.zip    | 2021–2022 | `cm22_2021_2022.csv` |

## How to add files

1. Download `cm26.zip` / `cm24.zip` from FEC bulk data.
2. From project root:
   ```bash
   python donor/fec_committee_master_to_csv.py path/to/cm26.zip -o donor/data/fec_committee_master/cm26_2025_2026.csv
   python donor/fec_committee_master_to_csv.py path/to/cm24.zip -o donor/data/fec_committee_master/cm24_2023_2024.csv
   ```
3. Commit the CSVs (they are **not** gitignored). The app loads them at startup and uses them to enrich donation data (committee names, etc.) without extra API calls.

## Columns (reference)

See `donor/fec_committee_master_columns.csv` and [Committee master file description](https://www.fec.gov/campaign-finance-data/committee-master-file-description/). Key column: `CMTE_ID` (committee identification).
