# Speed Up Instructions

## The Problem
Loading and parsing 363MB+ of CSV files on every page load is **very slow**.

## The Solution
Pre-process CSV files to JSON format once. JSON loads **10-100x faster** than parsing CSV.

## Quick Fix (Run Once)

1. **Double-click `preprocess-data.bat`**
   - This converts all CSV files to JSON
   - Takes 1-2 minutes the first time
   - Creates files in `public/data/json/`

2. **Restart your dev server**
   - The app will automatically use JSON files if available
   - Falls back to CSV if JSON not found

## Result
- **Before**: 30-60+ seconds to load
- **After**: 2-5 seconds to load

## Manual Method

If the batch file doesn't work:

```bash
cd pbj-wrapped
npm install papaparse
npm run preprocess
```

## Note
You only need to run this once (or when data files change). The JSON files are much smaller and load instantly.












