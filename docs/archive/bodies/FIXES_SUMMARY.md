# Calculation Fixes Summary

## Changes Made

### 1. Fixed Nurse_Care_HPRD Median Calculation ✅

**Problem**: The median for `Nurse_Care_HPRD` was using `reported_total_nurse_hrs_per_resident_per_day` instead of direct care values.

**Solution**: 
- Now estimates direct care values using state-level ratios
- For each facility: `estimated_direct_care_hprd = total_nurse_hprd × (state_direct_care / state_total)`
- This provides a better approximation than using total nurse values

**Location**: Lines 2992-3067 in `report.html`

### 2. Implemented Weighted Medians by Facility Census ✅

**Problem**: Medians were calculated as simple medians, treating all facilities equally regardless of size.

**Solution**: 
- Created `calculateWeightedMedian()` function that weights by facility census (`avg_residents_per_day`)
- Larger facilities (e.g., 500 beds) now count more than smaller facilities (e.g., 5 beds)
- Uses cumulative weight approach to find the true weighted median

**How it works**:
1. Each facility's HPRD value is weighted by its average resident census
2. Facilities are sorted by HPRD value
3. Cumulative weights are calculated
4. Median is found at the point where cumulative weight reaches 50% of total weight

**Location**: Lines 2991-3027 in `report.html`

### 3. Updated USA Medians ✅

**Previous**: Median of state averages (50 values)

**New**: Weighted median of all facilities nationwide (15,000+ facilities)
- Aggregates all facilities from all states
- Calculates weighted median using facility census
- Provides true national facility-level median

**Location**: New function `calculateUSAMedians()` at lines 3357-3409

### 4. Updated Region Medians ✅

**Previous**: Median of state medians within region (median of medians)

**New**: Weighted median of all facilities in the region
- Aggregates all facilities from all states in the region
- Calculates weighted median using facility census
- Provides true region-level facility median

**Location**: Lines 3687-3720 in `report.html`

### 5. Updated Exclude Admin/DON Medians ✅

**Previous**: Simple median of state-level values

**New**: Weighted median from facility-level data
- Uses facility-level data with estimated direct care values
- Weights by facility census
- More accurate representation of the median facility

**Location**: Lines 3453-3485 in `report.html` (USA medians)

### 6. Added UI Clarifications ✅

**Updated help text** to explain:
- Medians are weighted by facility census (larger facilities count more)
- Averages are weighted by facility census via total resident days
- USA and region medians are calculated from all facilities, not state aggregates

**Location**: Lines 2296-2300 and 2336-2340 in `report.html`

## Weighting Explanation

### How Weighting Works

**For Averages (Exclude Admin/DON)**:
- Uses `total_resident_days` which is the sum of `(avg_residents_per_day × days_reported)` for all facilities
- Example: 
  - 500-bed facility × 90 days = 45,000 resident days
  - 5-bed facility × 90 days = 450 resident days
  - The 500-bed facility contributes 100× more to the average
- This is already correctly implemented and now has clarifying comments

**For Medians**:
- Uses `avg_residents_per_day` (facility census) as the weight
- Example:
  - 500-bed facility's HPRD value counts as 500 units
  - 5-bed facility's HPRD value counts as 5 units
  - The median is found at the point where cumulative census reaches 50% of total census
- This ensures larger facilities have more influence on the median

### Why This Matters

Without weighting:
- A 5-bed facility counts the same as a 500-bed facility
- Small facilities can skew the median
- Doesn't reflect the experience of most residents

With weighting:
- Larger facilities (where most residents live) count more
- Median reflects the typical resident's experience
- More accurate representation of staffing levels

## Technical Details

### Direct Care Estimation

Since provider data doesn't have direct care fields at the facility level, we estimate using state-level ratios:

```javascript
directCareRatio = state.Nurse_Care_HPRD / state.Total_Nurse_HPRD
facilityDirectCare = facilityTotalNurse × directCareRatio
```

This assumes facilities within a state have similar admin/DON percentages, which is a reasonable approximation.

### Weighted Median Algorithm

1. Create array of `{value, weight}` pairs from facilities
2. Sort by value (HPRD)
3. Calculate total weight (sum of all census values)
4. Find median weight (50% of total)
5. Calculate cumulative weights
6. Find value where cumulative weight reaches median weight
7. If exactly at median, average with next value

## Verification

All calculations have been verified:
- ✅ USA exclude admin/DON matches CSV exactly (difference: 0.000000)
- ✅ Weighted medians correctly weight by facility census
- ✅ Direct care estimation uses state ratios appropriately
- ✅ Region calculations aggregate correctly

## Files Modified

- `report.html`: Main calculation logic and UI clarifications
- `CALCULATION_ANALYSIS.md`: Detailed analysis document
- `verify_calculations.py`: Verification script
- `FIXES_SUMMARY.md`: This document


