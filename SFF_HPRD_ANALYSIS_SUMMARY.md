# SFF HPRD Metrics Analysis Summary

**Analysis Date:** December 2025  
**Data Sources:** CMS SFF Posting (Dec. 2025), CMS PBJ (Q2 2025)  
**Total Facilities Analyzed:** 634 (627 with HPRD data, 620 with case-mix data)

## Executive Summary

This analysis examines Hours Per Resident Day (HPRD) metrics for facilities in the Special Focus Facilities (SFF) program, including current SFFs, Candidates, Graduates, and Terminated facilities. The analysis incorporates months as SFF and case-mix adjusted staffing percentages.

## Key Findings

### 1. HPRD by SFF Type

| SFF Type | Count | Mean Total HPRD | Median Total HPRD | Mean % Case-Mix | Median % Case-Mix |
|----------|-------|-----------------|-------------------|-----------------|-------------------|
| **Overall** | 634 | 3.66 | 3.54 | 97.7% | 94.1% |
| **SFF** | 86 | 3.68 | 3.63 | 98.8% | 98.1% |
| **Candidate** | 435 | 3.62 | 3.51 | 96.8% | 93.4% |
| **Graduate** | 105 | 3.66 | 3.57 | 97.4% | 94.5% |
| **Terminated** | 8 | 6.51* | 4.20* | 379.4%* | 379.4%* |

*Note: Terminated facilities have very limited data (only 4 with HPRD), so these metrics should be interpreted with caution.

### 2. HPRD by Months as SFF (SFFs and Candidates Only)

| Months as SFF | Count | Mean Total HPRD | Median Total HPRD | Mean % Case-Mix | Median % Case-Mix |
|---------------|-------|-----------------|-------------------|-----------------|-------------------|
| **0-6 months** | 282 | 3.69 | 3.52 | 98.6% | 93.7% |
| **7-12 months** | 100 | 3.56 | 3.47 | 96.3% | 93.8% |
| **13-18 months** | 50 | 3.67 | 3.59 | 98.0% | 95.9% |
| **19-24 months** | 37 | 3.57 | 3.56 | 93.9% | 96.3% |
| **25+ months** | 48 | 3.48 | 3.52 | 91.2% | 91.6% |

### 3. RN HPRD by SFF Type

| SFF Type | Mean RN HPRD | Median RN HPRD |
|----------|-------------|----------------|
| **SFF** | 0.56 | 0.49 |
| **Candidate** | 0.56 | 0.50 |
| **Graduate** | 0.55 | 0.48 |
| **Overall** | 0.57 | 0.49 |

### 4. Direct Care HPRD by SFF Type

| SFF Type | Mean Direct Care HPRD | Median Direct Care HPRD |
|----------|----------------------|------------------------|
| **SFF** | 3.41 | 3.33 |
| **Candidate** | 3.37 | 3.25 |
| **Graduate** | 3.39 | 3.30 |

## Key Insights

### 1. Minimal Difference Between SFFs and Candidates
- Current SFFs have slightly higher total HPRD (3.68) than SFF Candidates (3.62), though the difference is minimal (0.06 hours, 1.6% higher).
- This suggests that staffing levels are similar between facilities that have been designated as SFFs and those that are candidates.

### 2. Systemic Understaffing Relative to Case-Mix
- **Current SFFs** are providing 98.8% of their case-mix expected staffing, indicating they are understaffed by 1.2 percentage points relative to their resident acuity.
- **Candidates** are providing 96.8% of case-mix expected staffing (3.2 percentage points below expected).
- **Overall**, all SFF program facilities are providing 97.7% of their case-mix expected staffing, indicating systemic understaffing across the SFF program.

### 3. Extended Time in Program Associated with Lower Staffing
- Facilities that have been in the SFF program longer (19+ months) have:
  - **Lower HPRD** (3.53) than newer SFFs (0-12 months: 3.62), a difference of 0.10 hours (2.7% lower).
  - **Worse case-mix performance**: 92.5% of case-mix expected staffing, compared to 97.4% for newer facilities (0-12 months), a 4.9 percentage point gap.
- This suggests that extended time in the program may be associated with persistent staffing challenges.

### 4. Graduates Show Similar Staffing to Current SFFs
- Facilities that graduated from the SFF program have similar total HPRD (3.66) to current SFFs (3.68), suggesting that graduation may not necessarily correlate with significantly improved staffing levels.

## Phoebe J Takeaway

**Main Finding:** Facilities in the Special Focus Facilities program are systemically understaffed relative to their resident acuity, with facilities that have been in the program longer showing worse staffing outcomes.

**Key Points:**
1. Current SFFs are providing 98.8% of their case-mix expected staffing, indicating understaffing by 1.2 percentage points.
2. Facilities in the program 19+ months are providing only 92.5% of case-mix expected staffing, compared to 97.4% for newer facilities (0-12 months), a 4.9 percentage point gap.
3. Extended time in the SFF program is associated with lower HPRD (3.53 vs 3.62 for newer facilities) and worse case-mix performance, suggesting persistent staffing challenges.
4. Across all SFF program facilities, the average total HPRD is 3.66 hours per resident day, with facilities providing 97.7% of their case-mix expected staffing, indicating systemic understaffing across the program.

## Methodology Notes

- **Data Matching:** Facilities were matched by normalized 6-digit CCN (provider number).
- **HPRD Data:** From `facility_lite_metrics.csv` (Q2 2025).
- **Case-Mix Data:** From `provider_info_combined_latest.csv` (Q2 2025).
- **SFF Status:** From `sff-facilities.json` (December 2025 CMS posting).
- **Months as SFF:** Only available for current SFFs and Candidates from the CMS posting.
- **Percent Case-Mix:** Calculated as (Total HPRD / Case-Mix Expected HPRD) × 100.

## Files Generated

- `analyze_sff_hprd.py` - Analysis script
- `sff_hprd_analysis_results.json` - Detailed results in JSON format
- `SFF_HPRD_ANALYSIS_SUMMARY.md` - This summary document








