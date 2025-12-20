# Quick Start Guide

## Testing the Application

### Option 1: Use the Batch File (Easiest)

1. **Double-click `start-dev.bat`**
   - This will install dependencies if needed
   - Start the development server
   - Open your browser automatically

2. **Choose what to view:**
   - Click "United States" for national data
   - Click any state code (e.g., "PA", "NY") for state data
   - Click any region (e.g., "Region 1") for CMS region data

### Option 2: Manual Start

1. **Open terminal in the `pbj-wrapped` folder**

2. **Install dependencies (first time only):**
   ```bash
   npm install
   ```

3. **Start the server:**
   ```bash
   npm run dev
   ```

4. **Open browser to:**
   - http://localhost:5173 (index page with choices)
   - Or directly to:
     - http://localhost:5173/wrapped/2025/usa
     - http://localhost:5173/wrapped/2025/pa
     - http://localhost:5173/wrapped/2025/region1

## Data Files Required

Make sure these CSV files are in `public/data/`:
- `state_quarterly_metrics.csv`
- `cms_region_quarterly_metrics.csv`
- `national_quarterly_metrics.csv`
- `facility_lite_metrics.csv`
- `provider_info_combined.csv`
- `cms_region_state_mapping.csv` (already included)

## Navigation

- **Auto-advance**: Slides advance automatically after 5 seconds
- **Touch/Swipe**: Swipe left/right on mobile
- **Keyboard**: Use arrow keys to navigate
- **Click dots**: Click the progress dots at the bottom to jump to a slide

## Troubleshooting

- **"Failed to load data"**: Make sure CSV files are in `public/data/`
- **Server won't start**: Run `npm install` first
- **Port already in use**: Change port in `vite.config.ts` or close other dev servers

