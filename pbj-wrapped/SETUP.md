# Setup Instructions

## Quick Start

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Copy data files to `public/data/`:**
   - `state_quarterly_metrics.csv`
   - `cms_region_quarterly_metrics.csv`
   - `national_quarterly_metrics.csv`
   - `facility_lite_metrics.csv`
   - `provider_info_combined.csv`
   - `cms_region_state_mapping.csv` (already copied)

3. **Copy Phoebe logo:**
   - Ensure `phoebe-wrapped-wide.png` is in `public/images/` (already copied)

4. **Run development server:**
   ```bash
   npm run dev
   ```

5. **Access the app:**
   - Open http://localhost:5173
   - Navigate to routes like:
     - http://localhost:5173/wrapped/2025/usa
     - http://localhost:5173/wrapped/2025/pa
     - http://localhost:5173/wrapped/2025/region1

## Data File Locations

The app will try to load CSV files from these paths (in order):
1. `/data/{filename}.csv` (public/data/)
2. `../data/{filename}.csv` (parent directory)
3. `/{filename}.csv` (root)

Place your CSV files in `public/data/` for best results.

## Building for Production

```bash
npm run build
```

The built files will be in the `dist/` directory.

## Notes

- The app automatically filters data for Q2 2025 (primary) and Q1 2025 (for comparisons)
- All routes are case-insensitive and normalized to lowercase
- State full names (e.g., "pennsylvania") automatically redirect to 2-letter codes (e.g., "pa")
- The app includes touch navigation, keyboard navigation (arrow keys), and auto-advancing slides









