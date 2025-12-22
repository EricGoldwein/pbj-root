# PBJ Wrapped Q2 2025

A "Spotify Wrapped" style experience for Q2 2025 nursing home staffing data using CMS PBJ data.

## Overview

PBJ Wrapped provides a quarterly wrap-up of nursing home staffing metrics for:
- United States (national aggregate)
- All 50 states + DC
- All 10 CMS regions

Each page displays 7 sections of data-driven insights in a clean, factual, editorial style.

## Routes

- `/wrapped/2025/usa` - National data
- `/wrapped/2025/{state}` - State data (2-letter code, e.g., `pa`, `ny`)
- `/wrapped/2025/{state-name}` - State data (full name, e.g., `pennsylvania`) - redirects to 2-letter code
- `/wrapped/2025/region{1-10}` - CMS region data (e.g., `region1`, `region2`)

## Setup

1. Install dependencies:
```bash
npm install
```

2. Place CSV data files in the `public/data/` directory:
   - `state_quarterly_metrics.csv`
   - `cms_region_quarterly_metrics.csv`
   - `national_quarterly_metrics.csv`
   - `facility_lite_metrics.csv`
   - `provider_info_combined.csv`
   - `cms_region_state_mapping.csv`

3. Place the Phoebe logo in `public/images/phoebe-wrapped-wide.png`

4. Run the development server:
```bash
npm run dev
```

5. Build for production:
```bash
npm run build
```

## Data Requirements

The application expects Q2 2025 (and Q1 2025 for comparisons) data in the CSV files. Data is filtered automatically for these quarters.

## Features

- 7 standardized data sections per page
- Auto-advancing slides with touch/keyboard navigation
- Mobile-responsive design
- Links to pbjdashboard.com for facilities and states
- Clear, factual presentation without editorializing

## Sections

1. **Header** - Title, subtitle, Phoebe logo, link to pbj320.com
2. **The Basics** - Facility count, average residents, HPRD metrics
3. **Rankings** - Rank and percentile against all states/regions
4. **Staffing Extremes** - Lowest/highest facilities by HPRD and % of expected
5. **Special Focus Facilities** - SFF counts, candidates, new this quarter
6. **Quarter-over-Quarter Trends** - Q1→Q2 changes in staffing metrics
7. **Biggest Movers** - Facilities with largest increases/decreases

## Technology Stack

- React 18 + TypeScript
- React Router v6
- Vite
- Tailwind CSS
- Papa Parse (CSV parsing)



