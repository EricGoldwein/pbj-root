# Calculation Analysis: Medians and Exclude Admin/DON

## Overview

This document walks through the exact calculation process for medians and exclude admin/DON functionality for **USA**, **Regions**, and **States** in `report.html`.

---

## 1. STATE-LEVEL CALCULATIONS

### Standard Values (No Toggles)

**Source**: `state_quarterly_metrics.csv`

Values come directly from the CSV:
- `Total_Nurse_HPRD`: Total nurse hours per resident day (includes admin/DON)
- `RN_HPRD`: RN hours per resident day (includes admin/DON)
- `Nurse_Care_HPRD`: Direct care hours per resident day (**already excludes admin/DON**)
- `RN_Care_HPRD`: RN direct care hours per resident day (**already excludes admin/DON**)

**Location in code**: Lines 2473-2501, loaded directly from CSV

### State Medians

**Function**: `calculateStateMedians()` (lines 2992-3067)

**Process**:
1. Loads facility-level data from `provider_info_combined.csv`
2. Groups facilities by state
3. For each state, extracts facility-level HPRD values:
   - `Total_Nurse_HPRD`: Uses `reported_total_nurse_hrs_per_resident_per_day`
   - `RN_HPRD`: Uses `reported_rn_hrs_per_resident_per_day`
   - `Nurse_Care_HPRD`: **ISSUE** - Uses `reported_total_nurse_hrs_per_resident_per_day` (should use direct care!)
   - `RN_Care_HPRD`: Uses `reported_rn_hrs_per_resident_per_day`
4. Calculates median using `calculateMedian()` function (lines 2984-2990)

**Median Calculation**:
```javascript
function calculateMedian(values) {
  const sorted = values.filter(v => !isNaN(v)).sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 
    ? (sorted[mid - 1] + sorted[mid]) / 2 
    : sorted[mid];
}
```

**⚠️ ISSUE FOUND**: 
- Line 3017-3019: `Nurse_Care_HPRD` median uses `reported_total_nurse_hrs_per_resident_per_day` instead of actual direct care values
- Comment says: "For direct care, we'd need admin/DON breakdown which isn't in provider_info"
- This is an **approximation**, not the true direct care median

### Exclude Admin/DON for States

**Functions**: 
- `calculateDirectCareExclAdmin()` (lines 3238-3245)
- `calculateRNCareExclAdmin()` (lines 3250-3257)

**Process**:
- Simply returns `state.Nurse_Care_HPRD` and `state.RN_Care_HPRD`
- These values from the CSV **already exclude admin/DON**
- No additional calculation needed

**✅ CORRECT**: The exclude admin/DON toggle correctly uses these pre-calculated values

**⚠️ LIMITATION**: 
- Medians are pre-calculated and **don't account for excludeAdminDON toggle**
- When excludeAdminDON is enabled, medians are disabled (line 3267: `if (mapDisplayMode === 'median' && !excludeAdminDON)`)

---

## 2. USA-LEVEL CALCULATIONS

### Standard Values (No Toggles)

**Source**: `national_quarterly_metrics.csv`

Values come directly from the CSV:
- `Total_Nurse_HPRD`: National average
- `RN_HPRD`: National average

**Location in code**: Line 3396-3397

### USA Medians

**Function**: `renderUSSummary()` (lines 3319-3420)

**Process** (lines 3322-3329):
1. Gets all state-level values from `stateData`
2. Calculates median of state-level `Total_Nurse_HPRD` values
3. Calculates median of state-level `RN_HPRD` values

**⚠️ IMPORTANT NOTE**: 
- These are **medians of STATE AVERAGES**, not medians of all facilities nationwide
- This is a different metric than a true facility-level median
- Example: If 50 states have averages [3.0, 3.1, 3.2, ...], the median is the middle state average

**Location in code**: Lines 3324-3328

### Exclude Admin/DON for USA

**Process** (lines 3370-3393):

**Weighted Average Calculation**:
1. For each state:
   - Get `total_resident_days`
   - Get `Nurse_Care_HPRD` (already excludes admin/DON)
   - Get `RN_Care_HPRD` (already excludes admin/DON)
2. Calculate weighted totals:
   ```javascript
   totalDirectCareHours += directCare * residentDays;
   totalRNCareHours += rnCare * residentDays;
   totalResidentDays += residentDays;
   ```
3. Calculate weighted average:
   ```javascript
   totalHPRD = totalDirectCareHours / totalResidentDays;
   rnHPRD = totalRNCareHours / totalResidentDays;
   ```

**✅ VERIFIED**: This matches the CSV values exactly (difference: 0.000000)

**Median Calculation** (lines 3389-3393):
- Calculates median of state-level `Nurse_Care_HPRD` values
- Calculates median of state-level `RN_Care_HPRD` values
- Again, this is median of state averages, not facility medians

---

## 3. REGION-LEVEL CALCULATIONS

### Standard Values (No Toggles)

**Function**: `aggregateRegionData()` (lines 3072-3176)

**Process**:
1. Groups states by CMS region using `cms_region_state_mapping.csv`
2. For each region, aggregates state data:
   - Sums `facility_count`
   - Sums `total_resident_days`
   - Aggregates hours (weighted by resident days):
     ```javascript
     region.total_nurse_hours += (state.Total_Nurse_HPRD || 0) * residentDays;
     region.total_rn_hours += (state.RN_HPRD || 0) * residentDays;
     region.total_nurse_care_hours += (state.Nurse_Care_HPRD || 0) * residentDays;
     region.total_rn_care_hours += (state.RN_Care_HPRD || 0) * residentDays;
     ```
3. Calculates weighted averages (lines 3151-3158):
   ```javascript
   region.Total_Nurse_HPRD = region.total_nurse_hours / totalResidentDays;
   region.RN_HPRD = region.total_rn_hours / totalResidentDays;
   region.Nurse_Care_HPRD = region.total_nurse_care_hours / totalResidentDays;
   region.RN_Care_HPRD = region.total_rn_care_hours / totalResidentDays;
   ```

**✅ CORRECT**: Weighted averages properly account for state sizes

### Region Medians

**Process** (lines 3567-3575):

When `showMedians` is true:
1. Gets state medians for all states in the region
2. Calculates median of those state medians:
   ```javascript
   reportedTotal = calculateMedian(regionStateMedians.map(m => m.Total_Nurse_HPRD || 0));
   reportedRN = calculateMedian(regionStateMedians.map(m => m.RN_HPRD || 0));
   ```

**⚠️ IMPORTANT NOTE**:
- This is a **median of medians** (median of state medians)
- Not a true facility-level median for the region
- Example: If region has 4 states with medians [3.5, 3.6, 3.7, 3.8], the region median is 3.65

### Exclude Admin/DON for Regions

**Process** (lines 3548-3565):

**Weighted Average Calculation**:
1. For each state in the region:
   - Get `total_resident_days`
   - Get `Nurse_Care_HPRD` (already excludes admin/DON)
   - Get `RN_Care_HPRD` (already excludes admin/DON)
2. Calculate weighted totals:
   ```javascript
   totalDirectCareHours += (stateDataItem.Nurse_Care_HPRD || 0) * residentDays;
   totalRNCareHours += (stateDataItem.RN_Care_HPRD || 0) * residentDays;
   totalResidentDays += residentDays;
   ```
3. Calculate weighted average:
   ```javascript
   reportedTotal = totalDirectCareHours / totalResidentDays;
   reportedRN = totalRNCareHours / totalResidentDays;
   ```

**✅ CORRECT**: Properly weighted by resident days

---

## 4. SUMMARY OF ISSUES

### ❌ Critical Issue

1. **State Medians - Nurse_Care_HPRD**:
   - **Location**: Lines 3017-3019
   - **Problem**: Uses `reported_total_nurse_hrs_per_resident_per_day` instead of direct care values
   - **Impact**: The median shown is an approximation, not the true direct care median
   - **Reason**: Provider info CSV doesn't have admin/DON breakdown at facility level

### ⚠️ Design Decisions (Not Bugs, But Important to Understand)

2. **USA Medians**:
   - Calculated as median of **state averages**, not median of all facilities
   - This is a different metric than a true national facility median
   - Example: Median of 50 state averages vs. median of 15,000+ facilities

3. **Region Medians**:
   - Calculated as median of **state medians** within the region
   - This is a "median of medians", not a true facility-level median
   - Example: If region has 4 states, it's the median of 4 state medians

4. **Medians Don't Account for Exclude Admin/DON**:
   - Medians are pre-calculated once when data loads
   - When excludeAdminDON toggle is enabled, medians are disabled
   - This is by design (line 3267: `if (mapDisplayMode === 'median' && !excludeAdminDON)`)

### ✅ Verified Correct

5. **Exclude Admin/DON Calculations**:
   - **State level**: Uses pre-calculated `Nurse_Care_HPRD` and `RN_Care_HPRD` (correct)
   - **USA level**: Weighted average by resident days (verified: matches CSV exactly)
   - **Region level**: Weighted average by resident days (correct)

---

## 5. VERIFICATION RESULTS

### USA Exclude Admin/DON
- **Calculated**: 3.5090
- **Expected (CSV)**: 3.5090
- **Difference**: 0.000000 ✅

### USA RN Care Exclude Admin/DON
- **Calculated**: 0.4312
- **Expected (CSV)**: 0.4312
- **Difference**: 0.000000 ✅

### Sample Region (Region 10 - Seattle)
- **States**: AK, ID, OR, WA
- **Total resident days**: 2,356,061
- **Weighted averages calculated correctly** ✅

---

## 6. RECOMMENDATIONS

1. **Fix State Median - Nurse_Care_HPRD**:
   - If possible, add direct care fields to provider_info_combined.csv
   - Or document that this is an approximation
   - Consider calculating from raw PBJ data if available

2. **Clarify Median Definitions**:
   - Add tooltips/help text explaining:
     - USA medians = median of state averages
     - Region medians = median of state medians
     - State medians = median of facilities

3. **Document Exclude Admin/DON Behavior**:
   - Explain that medians are disabled when excludeAdminDON is enabled
   - This is because medians are pre-calculated

4. **Consider Adding True Facility-Level Medians**:
   - For USA: Calculate median of all facilities nationwide
   - For Regions: Calculate median of all facilities in region
   - This would require processing all facility data, not just state aggregates

---

## 7. CODE REFERENCES

- **Median calculation**: Lines 2984-2990
- **State medians**: Lines 2992-3067
- **USA summary**: Lines 3319-3420
- **Region aggregation**: Lines 3072-3176
- **Exclude admin/DON helpers**: Lines 3235-3257
- **Table rendering with toggles**: Lines 3540-3602


