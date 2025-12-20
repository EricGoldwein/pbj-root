# Data Files Setup

## Required Files

The following CSV files need to be in `pbj-wrapped/public/data/`:

1. ✅ `state_quarterly_metrics.csv` - Already copied
2. ✅ `cms_region_quarterly_metrics.csv` - Already copied  
3. ✅ `national_quarterly_metrics.csv` - Already copied
4. ✅ `facility_lite_metrics.csv` - Already copied
5. ✅ `cms_region_state_mapping.csv` - Already copied
6. ⚠️ `provider_info_combined.csv` - **TOO LARGE - Must copy manually**
7. ⚠️ `macpac_state_standards_clean.csv` - **Must copy manually** (for state minimum staffing requirements)

## Manual Copy Required

The `provider_info_combined.csv` file is too large (>200MB) to copy automatically. 

**To copy it manually:**

1. Open File Explorer
2. Navigate to: `C:\Users\egold\PycharmProjects\pbj-root\`
3. Find `provider_info_combined.csv`
4. Copy it to: `C:\Users\egold\PycharmProjects\pbj-root\pbj-wrapped\public\data\`

**OR use PowerShell:**
```powershell
Copy-Item "C:\Users\egold\PycharmProjects\pbj-root\provider_info_combined.csv" "C:\Users\egold\PycharmProjects\pbj-root\pbj-wrapped\public\data\"
```

## Note About Main Site

**IMPORTANT:** All files are copied to `pbj-wrapped/` directory only. The main site files in the root directory (`index.html`, etc.) are **NOT modified** and will continue to function normally.

