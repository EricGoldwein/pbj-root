"""
Analysis of HPRD metrics for Special Focus Facilities (SFFs) by type.
Examines total HPRD, direct care HPRD, RN HPRD, and % case-mix by SFF status.
Also incorporates months as SFF into the analysis.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional

def normalize_ccn(ccn: str) -> str:
    """Normalize CCN to 6 digits with leading zeros."""
    if not ccn:
        return ''
    ccn_str = str(ccn).strip().replace(' ', '').replace('-', '').replace('_', '')
    # Remove non-digits
    ccn_str = ''.join(c for c in ccn_str if c.isdigit())
    if not ccn_str:
        return ''
    return ccn_str.zfill(6)

def load_sff_facilities(json_path: str) -> pd.DataFrame:
    """Load SFF facilities from JSON file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    facilities = []
    for facility in data.get('facilities', []):
        facilities.append({
            'provider_number': normalize_ccn(facility.get('provider_number', '')),
            'facility_name': facility.get('facility_name', ''),
            'state': facility.get('state', ''),
            'category': facility.get('category', ''),
            'months_as_sff': facility.get('months_as_sff'),
            'met_survey_criteria': facility.get('met_survey_criteria', ''),
        })
    
    return pd.DataFrame(facilities)

def load_facility_metrics(csv_path: str) -> pd.DataFrame:
    """Load facility metrics (HPRD data) from CSV."""
    df = pd.read_csv(csv_path, dtype={'PROVNUM': str})
    
    # Filter for Q2 2025 (most recent)
    if 'CY_Qtr' in df.columns:
        df = df[df['CY_Qtr'] == '2025Q2'].copy()
    
    # Normalize provider numbers
    df['PROVNUM'] = df['PROVNUM'].apply(normalize_ccn)
    
    # Select relevant columns
    cols = ['PROVNUM', 'Total_Nurse_HPRD', 'Nurse_Care_HPRD', 'Total_RN_HPRD', 'Census']
    df = df[cols].copy()
    
    return df

def load_provider_info(csv_path: str) -> pd.DataFrame:
    """Load provider info (case-mix data) from CSV."""
    df = pd.read_csv(csv_path, dtype={'ccn': str})
    
    # Filter for Q2 2025
    if 'quarter' in df.columns:
        df = df[df['quarter'] == '2025Q2'].copy()
    
    # Normalize provider numbers
    df['ccn'] = df['ccn'].apply(normalize_ccn)
    
    # Select relevant columns
    cols = ['ccn', 'case_mix_total_nurse_hrs_per_resident_per_day']
    df = df[cols].copy()
    df = df.rename(columns={'ccn': 'PROVNUM'})
    
    return df

def calculate_percent_case_mix(total_hprd: float, case_mix_expected: float) -> Optional[float]:
    """Calculate percent of case-mix expected."""
    if pd.isna(total_hprd) or pd.isna(case_mix_expected):
        return None
    if total_hprd <= 0 or case_mix_expected <= 0:
        return None
    return (total_hprd / case_mix_expected) * 100

def calculate_weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    """Calculate census-weighted mean."""
    # Filter out NaN values and ensure weights are positive
    mask = values.notna() & weights.notna() & (weights > 0)
    if mask.sum() == 0:
        return np.nan
    valid_values = values[mask]
    valid_weights = weights[mask]
    return (valid_values * valid_weights).sum() / valid_weights.sum()

def analyze_by_sff_type(df: pd.DataFrame) -> Dict:
    """Analyze HPRD metrics by SFF type using census-weighted averages."""
    results = {}
    
    # Map category to SFF status
    category_map = {
        'SFF': 'SFF',
        'Candidate': 'Candidate',
        'Graduate': 'Graduate',
        'Terminated': 'Terminated'
    }
    
    df['sff_status'] = df['category'].map(category_map)
    
    # Overall analysis (all SFF-related facilities)
    overall = df[df['sff_status'].notna()].copy()
    
    # Analysis by type
    for status in ['SFF', 'Candidate', 'Graduate', 'Terminated']:
        subset = df[df['sff_status'] == status].copy()
        if len(subset) == 0:
            continue
        
        # Filter out facilities with missing HPRD data
        valid_hprd = subset[
            (subset['Total_Nurse_HPRD'].notna()) & 
            (subset['Total_Nurse_HPRD'] > 0)
        ].copy()
        
        if len(valid_hprd) == 0:
            continue
        
        # Filter for facilities with valid census data for weighted calculations
        valid_census = valid_hprd[
            (valid_hprd['Census'].notna()) & 
            (valid_hprd['Census'] > 0)
        ].copy()
        
        # Calculate census-weighted means
        if len(valid_census) > 0:
            weighted_total_hprd = calculate_weighted_mean(
                valid_census['Total_Nurse_HPRD'], 
                valid_census['Census']
            )
            weighted_direct_care_hprd = calculate_weighted_mean(
                valid_census['Nurse_Care_HPRD'], 
                valid_census['Census']
            ) if 'Nurse_Care_HPRD' in valid_census.columns else None
            weighted_rn_hprd = calculate_weighted_mean(
                valid_census['Total_RN_HPRD'], 
                valid_census['Census']
            ) if 'Total_RN_HPRD' in valid_census.columns else None
            weighted_case_mix = calculate_weighted_mean(
                valid_census['percent_case_mix'], 
                valid_census['Census']
            ) if 'percent_case_mix' in valid_census.columns else None
        else:
            weighted_total_hprd = np.nan
            weighted_direct_care_hprd = None
            weighted_rn_hprd = None
            weighted_case_mix = None
        
        results[status] = {
            'count': len(subset),
            'count_with_hprd': len(valid_hprd),
            'count_with_census': len(valid_census),
            'total_hprd': {
                'mean_weighted': weighted_total_hprd if not np.isnan(weighted_total_hprd) else None,
                'mean_unweighted': valid_hprd['Total_Nurse_HPRD'].mean(),
                'median': valid_hprd['Total_Nurse_HPRD'].median(),
                'std': valid_hprd['Total_Nurse_HPRD'].std(),
                'min': valid_hprd['Total_Nurse_HPRD'].min(),
                'max': valid_hprd['Total_Nurse_HPRD'].max(),
                'q25': valid_hprd['Total_Nurse_HPRD'].quantile(0.25),
                'q75': valid_hprd['Total_Nurse_HPRD'].quantile(0.75),
            },
            'direct_care_hprd': {
                'mean_weighted': weighted_direct_care_hprd if weighted_direct_care_hprd is not None and not np.isnan(weighted_direct_care_hprd) else None,
                'mean_unweighted': valid_hprd['Nurse_Care_HPRD'].mean() if 'Nurse_Care_HPRD' in valid_hprd.columns else None,
                'median': valid_hprd['Nurse_Care_HPRD'].median() if 'Nurse_Care_HPRD' in valid_hprd.columns else None,
            },
            'rn_hprd': {
                'mean_weighted': weighted_rn_hprd if weighted_rn_hprd is not None and not np.isnan(weighted_rn_hprd) else None,
                'mean_unweighted': valid_hprd['Total_RN_HPRD'].mean() if 'Total_RN_HPRD' in valid_hprd.columns else None,
                'median': valid_hprd['Total_RN_HPRD'].median() if 'Total_RN_HPRD' in valid_hprd.columns else None,
            },
            'percent_case_mix': {
                'mean_weighted': weighted_case_mix if weighted_case_mix is not None and not np.isnan(weighted_case_mix) else None,
                'mean_unweighted': valid_hprd['percent_case_mix'].mean() if 'percent_case_mix' in valid_hprd.columns else None,
                'median': valid_hprd['percent_case_mix'].median() if 'percent_case_mix' in valid_hprd.columns else None,
            },
            'months_as_sff': {
                'mean': subset['months_as_sff'].mean() if 'months_as_sff' in subset.columns else None,
                'median': subset['months_as_sff'].median() if 'months_as_sff' in subset.columns else None,
            } if status in ['SFF', 'Candidate'] else None,
        }
    
    # Overall analysis
    valid_overall = overall[
        (overall['Total_Nurse_HPRD'].notna()) & 
        (overall['Total_Nurse_HPRD'] > 0)
    ].copy()
    
    if len(valid_overall) > 0:
        valid_census_overall = valid_overall[
            (valid_overall['Census'].notna()) & 
            (valid_overall['Census'] > 0)
        ].copy()
        
        if len(valid_census_overall) > 0:
            weighted_total_hprd = calculate_weighted_mean(
                valid_census_overall['Total_Nurse_HPRD'], 
                valid_census_overall['Census']
            )
            weighted_direct_care_hprd = calculate_weighted_mean(
                valid_census_overall['Nurse_Care_HPRD'], 
                valid_census_overall['Census']
            ) if 'Nurse_Care_HPRD' in valid_census_overall.columns else None
            weighted_rn_hprd = calculate_weighted_mean(
                valid_census_overall['Total_RN_HPRD'], 
                valid_census_overall['Census']
            ) if 'Total_RN_HPRD' in valid_census_overall.columns else None
            weighted_case_mix = calculate_weighted_mean(
                valid_census_overall['percent_case_mix'], 
                valid_census_overall['Census']
            ) if 'percent_case_mix' in valid_census_overall.columns else None
        else:
            weighted_total_hprd = np.nan
            weighted_direct_care_hprd = None
            weighted_rn_hprd = None
            weighted_case_mix = None
        
        results['Overall'] = {
            'count': len(overall),
            'count_with_hprd': len(valid_overall),
            'count_with_census': len(valid_census_overall),
            'total_hprd': {
                'mean_weighted': weighted_total_hprd if not np.isnan(weighted_total_hprd) else None,
                'mean_unweighted': valid_overall['Total_Nurse_HPRD'].mean(),
                'median': valid_overall['Total_Nurse_HPRD'].median(),
                'std': valid_overall['Total_Nurse_HPRD'].std(),
            },
            'direct_care_hprd': {
                'mean_weighted': weighted_direct_care_hprd if weighted_direct_care_hprd is not None and not np.isnan(weighted_direct_care_hprd) else None,
                'mean_unweighted': valid_overall['Nurse_Care_HPRD'].mean() if 'Nurse_Care_HPRD' in valid_overall.columns else None,
                'median': valid_overall['Nurse_Care_HPRD'].median() if 'Nurse_Care_HPRD' in valid_overall.columns else None,
            },
            'rn_hprd': {
                'mean_weighted': weighted_rn_hprd if weighted_rn_hprd is not None and not np.isnan(weighted_rn_hprd) else None,
                'mean_unweighted': valid_overall['Total_RN_HPRD'].mean() if 'Total_RN_HPRD' in valid_overall.columns else None,
                'median': valid_overall['Total_RN_HPRD'].median() if 'Total_RN_HPRD' in valid_overall.columns else None,
            },
            'percent_case_mix': {
                'mean_weighted': weighted_case_mix if weighted_case_mix is not None and not np.isnan(weighted_case_mix) else None,
                'mean_unweighted': valid_overall['percent_case_mix'].mean() if 'percent_case_mix' in valid_overall.columns else None,
                'median': valid_overall['percent_case_mix'].median() if 'percent_case_mix' in valid_overall.columns else None,
            },
        }
    
    return results

def analyze_by_months_as_sff(df: pd.DataFrame) -> Dict:
    """Analyze HPRD metrics by months as SFF (for SFFs and Candidates only) using census-weighted averages."""
    results = {}
    
    # Filter to SFFs and Candidates with months_as_sff data
    sff_candidates = df[
        (df['category'].isin(['SFF', 'Candidate'])) &
        (df['months_as_sff'].notna()) &
        (df['Total_Nurse_HPRD'].notna()) &
        (df['Total_Nurse_HPRD'] > 0)
    ].copy()
    
    if len(sff_candidates) == 0:
        return results
    
    # Create bins for months as SFF
    sff_candidates['months_bin'] = pd.cut(
        sff_candidates['months_as_sff'],
        bins=[0, 6, 12, 18, 24, 100],
        labels=['0-6 months', '7-12 months', '13-18 months', '19-24 months', '25+ months']
    )
    
    for bin_label in sff_candidates['months_bin'].cat.categories:
        subset = sff_candidates[sff_candidates['months_bin'] == bin_label]
        if len(subset) == 0:
            continue
        
        # Filter for facilities with valid census data
        valid_census = subset[
            (subset['Census'].notna()) & 
            (subset['Census'] > 0)
        ].copy()
        
        # Calculate weighted means
        if len(valid_census) > 0:
            weighted_total_hprd = calculate_weighted_mean(
                valid_census['Total_Nurse_HPRD'], 
                valid_census['Census']
            )
            weighted_case_mix = calculate_weighted_mean(
                valid_census['percent_case_mix'], 
                valid_census['Census']
            ) if 'percent_case_mix' in valid_census.columns else None
        else:
            weighted_total_hprd = np.nan
            weighted_case_mix = None
        
        results[bin_label] = {
            'count': len(subset),
            'count_with_census': len(valid_census),
            'total_hprd_mean_weighted': weighted_total_hprd if not np.isnan(weighted_total_hprd) else None,
            'total_hprd_mean_unweighted': subset['Total_Nurse_HPRD'].mean(),
            'total_hprd_median': subset['Total_Nurse_HPRD'].median(),
            'percent_case_mix_mean_weighted': weighted_case_mix if weighted_case_mix is not None and not np.isnan(weighted_case_mix) else None,
            'percent_case_mix_mean_unweighted': subset['percent_case_mix'].mean() if 'percent_case_mix' in subset.columns else None,
            'percent_case_mix_median': subset['percent_case_mix'].median() if 'percent_case_mix' in subset.columns else None,
        }
    
    return results

def print_analysis_results(results_by_type: Dict, results_by_months: Dict):
    """Print formatted analysis results."""
    print("=" * 80)
    print("SFF HPRD METRICS ANALYSIS")
    print("=" * 80)
    print()
    
    # Analysis by SFF Type
    print("ANALYSIS BY SFF TYPE")
    print("-" * 80)
    
    for status in ['Overall', 'SFF', 'Candidate', 'Graduate', 'Terminated']:
        if status not in results_by_type:
            continue
        
        data = results_by_type[status]
        print(f"\n{status}:")
        print(f"  Total Facilities: {data['count']}")
        print(f"  Facilities with HPRD Data: {data['count_with_hprd']}")
        if 'count_with_census' in data:
            print(f"  Facilities with Census Data: {data['count_with_census']}")
        
        if 'total_hprd' in data and data['total_hprd']:
            th = data['total_hprd']
            print(f"  Total HPRD:")
            if 'mean_weighted' in th and th['mean_weighted'] is not None:
                print(f"    Mean (Census-Weighted): {th['mean_weighted']:.2f}")
            if 'mean_unweighted' in th:
                print(f"    Mean (Unweighted): {th['mean_unweighted']:.2f}")
            print(f"    Median: {th['median']:.2f}")
            if 'std' in th:
                print(f"    Std Dev: {th['std']:.2f}")
            if 'min' in th and 'max' in th:
                print(f"    Range: {th['min']:.2f} - {th['max']:.2f}")
            if 'q25' in th and 'q75' in th:
                print(f"    IQR: {th['q25']:.2f} - {th['q75']:.2f}")
        
        if 'direct_care_hprd' in data and data['direct_care_hprd']:
            dch = data['direct_care_hprd']
            print(f"  Direct Care HPRD:")
            if dch.get('mean_weighted') is not None:
                print(f"    Mean (Census-Weighted): {dch['mean_weighted']:.2f}")
            if dch.get('mean_unweighted') is not None:
                print(f"    Mean (Unweighted): {dch['mean_unweighted']:.2f}")
            if dch.get('median') is not None:
                print(f"    Median: {dch['median']:.2f}")
        
        if 'rn_hprd' in data and data['rn_hprd']:
            rn = data['rn_hprd']
            print(f"  RN HPRD:")
            if rn.get('mean_weighted') is not None:
                print(f"    Mean (Census-Weighted): {rn['mean_weighted']:.2f}")
            if rn.get('mean_unweighted') is not None:
                print(f"    Mean (Unweighted): {rn['mean_unweighted']:.2f}")
            if rn.get('median') is not None:
                print(f"    Median: {rn['median']:.2f}")
        
        if 'percent_case_mix' in data and data['percent_case_mix']:
            pcm = data['percent_case_mix']
            print(f"  % Case-Mix:")
            if pcm.get('mean_weighted') is not None:
                print(f"    Mean (Census-Weighted): {pcm['mean_weighted']:.1f}%")
            if pcm.get('mean_unweighted') is not None:
                print(f"    Mean (Unweighted): {pcm['mean_unweighted']:.1f}%")
            if pcm.get('median') is not None:
                print(f"    Median: {pcm['median']:.1f}%")
        
        if 'months_as_sff' in data and data['months_as_sff']:
            mas = data['months_as_sff']
            print(f"  Months as SFF:")
            print(f"    Mean: {mas['mean']:.1f}")
            print(f"    Median: {mas['median']:.1f}")
    
    # Analysis by Months as SFF
    if results_by_months:
        print("\n" + "=" * 80)
        print("ANALYSIS BY MONTHS AS SFF (SFFs and Candidates only)")
        print("-" * 80)
        
        for bin_label, data in results_by_months.items():
            print(f"\n{bin_label}:")
            print(f"  Count: {data['count']}")
            if data.get('count_with_census'):
                print(f"  Count with Census: {data['count_with_census']}")
            if data.get('total_hprd_mean_weighted') is not None:
                print(f"  Total HPRD Mean (Census-Weighted): {data['total_hprd_mean_weighted']:.2f}")
            if data.get('total_hprd_mean_unweighted') is not None:
                print(f"  Total HPRD Mean (Unweighted): {data['total_hprd_mean_unweighted']:.2f}")
            print(f"  Total HPRD Median: {data['total_hprd_median']:.2f}")
            if data.get('percent_case_mix_mean_weighted') is not None:
                print(f"  % Case-Mix Mean (Census-Weighted): {data['percent_case_mix_mean_weighted']:.1f}%")
            if data.get('percent_case_mix_mean_unweighted') is not None:
                print(f"  % Case-Mix Mean (Unweighted): {data['percent_case_mix_mean_unweighted']:.1f}%")
            if data.get('percent_case_mix_median') is not None:
                print(f"  % Case-Mix Median: {data['percent_case_mix_median']:.1f}%")

def generate_phoebe_takeaway(results_by_type: Dict, results_by_months: Dict) -> str:
    """Generate a Phoebe J takeaway summary."""
    takeaways = []
    
    # Key finding: Compare SFFs vs Candidates vs Graduates (use weighted means)
    if 'SFF' in results_by_type and 'Candidate' in results_by_type:
        sff_hprd = results_by_type['SFF']['total_hprd'].get('mean_weighted') or results_by_type['SFF']['total_hprd'].get('mean_unweighted')
        candidate_hprd = results_by_type['Candidate']['total_hprd'].get('mean_weighted') or results_by_type['Candidate']['total_hprd'].get('mean_unweighted')
        
        if abs(sff_hprd - candidate_hprd) > 0.05:  # Only report if meaningful difference
            if sff_hprd < candidate_hprd:
                diff = candidate_hprd - sff_hprd
                pct_diff = (diff / candidate_hprd) * 100
                takeaways.append(
                    f"Current SFFs have lower total HPRD ({sff_hprd:.2f}) than SFF Candidates ({candidate_hprd:.2f}), "
                    f"a difference of {diff:.2f} hours ({pct_diff:.1f}% lower)."
                )
            else:
                diff = sff_hprd - candidate_hprd
                pct_diff = (diff / candidate_hprd) * 100
                takeaways.append(
                    f"Current SFFs have slightly higher total HPRD ({sff_hprd:.2f}) than SFF Candidates ({candidate_hprd:.2f}), "
                    f"though the difference is minimal ({diff:.2f} hours, {pct_diff:.1f}% higher)."
                )
    
    # Compare to Graduates (use weighted means)
    if 'SFF' in results_by_type and 'Graduate' in results_by_type:
        sff_hprd = results_by_type['SFF']['total_hprd'].get('mean_weighted') or results_by_type['SFF']['total_hprd'].get('mean_unweighted')
        grad_hprd = results_by_type['Graduate']['total_hprd'].get('mean_weighted') or results_by_type['Graduate']['total_hprd'].get('mean_unweighted')
        
        if abs(sff_hprd - grad_hprd) > 0.05:
            if sff_hprd < grad_hprd:
                diff = grad_hprd - sff_hprd
                pct_diff = (diff / grad_hprd) * 100
                takeaways.append(
                    f"Current SFFs have {diff:.2f} fewer total HPRD ({pct_diff:.1f}% lower) than facilities that graduated "
                    f"from the SFF program ({grad_hprd:.2f} vs {sff_hprd:.2f})."
                )
            else:
                diff = sff_hprd - grad_hprd
                pct_diff = (diff / grad_hprd) * 100
                takeaways.append(
                    f"Current SFFs have {diff:.2f} more total HPRD ({pct_diff:.1f}% higher) than facilities that graduated "
                    f"from the SFF program ({sff_hprd:.2f} vs {grad_hprd:.2f})."
                )
    
    # Case-mix analysis - key finding (use weighted means)
    if 'SFF' in results_by_type and results_by_type['SFF']['percent_case_mix']:
        sff_pcm = results_by_type['SFF']['percent_case_mix'].get('mean_weighted') or results_by_type['SFF']['percent_case_mix'].get('mean_unweighted')
        if sff_pcm < 100:
            gap = 100 - sff_pcm
            takeaways.append(
                f"Current SFFs are providing {sff_pcm:.1f}% of their case-mix expected staffing, "
                f"indicating they are understaffed by {gap:.1f} percentage points relative to their resident acuity."
            )
        elif sff_pcm > 100:
            excess = sff_pcm - 100
            takeaways.append(
                f"Current SFFs are providing {sff_pcm:.1f}% of their case-mix expected staffing, "
                f"exceeding expectations by {excess:.1f} percentage points."
            )
    
    # Months as SFF analysis - key finding
    if results_by_months:
        # Compare early vs late
        early_bins = ['0-6 months', '7-12 months']
        late_bins = ['19-24 months', '25+ months']
        
        early_hprd = []
        late_hprd = []
        early_pcm = []
        late_pcm = []
        
        for bin_label in early_bins:
            if bin_label in results_by_months:
                hprd_val = results_by_months[bin_label].get('total_hprd_mean_weighted') or results_by_months[bin_label].get('total_hprd_mean_unweighted')
                if hprd_val is not None:
                    early_hprd.append(hprd_val)
                pcm_val = results_by_months[bin_label].get('percent_case_mix_mean_weighted') or results_by_months[bin_label].get('percent_case_mix_mean_unweighted')
                if pcm_val is not None:
                    early_pcm.append(pcm_val)
        
        for bin_label in late_bins:
            if bin_label in results_by_months:
                hprd_val = results_by_months[bin_label].get('total_hprd_mean_weighted') or results_by_months[bin_label].get('total_hprd_mean_unweighted')
                if hprd_val is not None:
                    late_hprd.append(hprd_val)
                pcm_val = results_by_months[bin_label].get('percent_case_mix_mean_weighted') or results_by_months[bin_label].get('percent_case_mix_mean_unweighted')
                if pcm_val is not None:
                    late_pcm.append(pcm_val)
        
        if early_hprd and late_hprd:
            early_avg = np.mean(early_hprd)
            late_avg = np.mean(late_hprd)
            if abs(early_avg - late_avg) > 0.05:
                if late_avg < early_avg:
                    diff = early_avg - late_avg
                    pct_diff = (diff / early_avg) * 100
                    takeaways.append(
                        f"Facilities that have been in the SFF program longer (19+ months) have lower HPRD "
                        f"({late_avg:.2f}) than newer SFFs (0-12 months: {early_avg:.2f}), a difference of "
                        f"{diff:.2f} hours ({pct_diff:.1f}% lower). This suggests that extended time in the "
                        f"program may be associated with persistent staffing challenges."
                    )
                else:
                    diff = late_avg - early_avg
                    pct_diff = (diff / early_avg) * 100
                    takeaways.append(
                        f"Facilities that have been in the SFF program longer (19+ months) have higher HPRD "
                        f"({late_avg:.2f}) than newer SFFs (0-12 months: {early_avg:.2f}), a difference of "
                        f"{diff:.2f} hours ({pct_diff:.1f}% higher)."
                    )
        
        # Case-mix by months
        if early_pcm and late_pcm:
            early_pcm_avg = np.mean(early_pcm)
            late_pcm_avg = np.mean(late_pcm)
            if abs(early_pcm_avg - late_pcm_avg) > 2:  # 2 percentage point threshold
                if late_pcm_avg < early_pcm_avg:
                    diff = early_pcm_avg - late_pcm_avg
                    takeaways.append(
                        f"Facilities in the program longer (19+ months) are providing {late_pcm_avg:.1f}% of "
                        f"case-mix expected staffing, compared to {early_pcm_avg:.1f}% for newer facilities "
                        f"(0-12 months), a {diff:.1f} percentage point gap."
                    )
    
    # RN HPRD comparison (use weighted means)
    if 'SFF' in results_by_type and 'Candidate' in results_by_type:
        if results_by_type['SFF'].get('rn_hprd') and results_by_type['Candidate'].get('rn_hprd'):
            sff_rn = results_by_type['SFF']['rn_hprd'].get('mean_weighted') or results_by_type['SFF']['rn_hprd'].get('mean_unweighted')
            candidate_rn = results_by_type['Candidate']['rn_hprd'].get('mean_weighted') or results_by_type['Candidate']['rn_hprd'].get('mean_unweighted')
            if abs(sff_rn - candidate_rn) > 0.05:
                if sff_rn < candidate_rn:
                    diff = candidate_rn - sff_rn
                    takeaways.append(
                        f"Current SFFs have lower RN HPRD ({sff_rn:.2f}) than Candidates ({candidate_rn:.2f}), "
                        f"indicating less registered nurse staffing."
                    )
    
    # Overall summary (use weighted means)
    if 'Overall' in results_by_type:
        overall_hprd = results_by_type['Overall']['total_hprd'].get('mean_weighted') or results_by_type['Overall']['total_hprd'].get('mean_unweighted')
        overall_pcm = None
        if results_by_type['Overall'].get('percent_case_mix'):
            overall_pcm = results_by_type['Overall']['percent_case_mix'].get('mean_weighted') or results_by_type['Overall']['percent_case_mix'].get('mean_unweighted')
        
        summary = f"Across all SFF program facilities (SFFs, Candidates, Graduates, and Terminated), "
        summary += f"the average total HPRD is {overall_hprd:.2f} hours per resident day."
        if overall_pcm:
            if overall_pcm < 100:
                summary += f" These facilities are providing {overall_pcm:.1f}% of their case-mix expected staffing, "
                summary += f"indicating systemic understaffing across the SFF program."
            else:
                summary += f" These facilities are providing {overall_pcm:.1f}% of their case-mix expected staffing."
        takeaways.append(summary)
    
    return "\n".join(takeaways)

def main():
    """Main analysis function."""
    # File paths
    base_path = Path(__file__).parent
    sff_json_path = base_path / 'pbj-wrapped' / 'public' / 'sff-facilities.json'
    facility_csv_path = base_path / 'facility_lite_metrics.csv'
    provider_csv_path = base_path / 'provider_info_combined_latest.csv'
    
    print("Loading data...")
    
    # Load data
    sff_df = load_sff_facilities(str(sff_json_path))
    facility_df = load_facility_metrics(str(facility_csv_path))
    provider_df = load_provider_info(str(provider_csv_path))
    
    print(f"Loaded {len(sff_df)} SFF facilities")
    print(f"Loaded {len(facility_df)} facility metrics records")
    print(f"Loaded {len(provider_df)} provider info records")
    
    # Merge data
    print("\nMerging data...")
    merged_df = sff_df.merge(
        facility_df,
        left_on='provider_number',
        right_on='PROVNUM',
        how='left'
    )
    
    merged_df = merged_df.merge(
        provider_df,
        left_on='provider_number',
        right_on='PROVNUM',
        how='left',
        suffixes=('', '_provider')
    )
    
    # Calculate percent case-mix
    merged_df['percent_case_mix'] = merged_df.apply(
        lambda row: calculate_percent_case_mix(
            row['Total_Nurse_HPRD'],
            row['case_mix_total_nurse_hrs_per_resident_per_day']
        ),
        axis=1
    )
    
    print(f"Merged dataset: {len(merged_df)} facilities")
    print(f"Facilities with HPRD data: {merged_df['Total_Nurse_HPRD'].notna().sum()}")
    print(f"Facilities with case-mix data: {merged_df['percent_case_mix'].notna().sum()}")
    
    # Perform analyses
    print("\nPerforming analyses...")
    results_by_type = analyze_by_sff_type(merged_df)
    results_by_months = analyze_by_months_as_sff(merged_df)
    
    # Print results
    print_analysis_results(results_by_type, results_by_months)
    
    # Generate Phoebe J takeaway
    print("\n" + "=" * 80)
    print("PHOEBE J TAKEAWAY")
    print("=" * 80)
    print()
    takeaway = generate_phoebe_takeaway(results_by_type, results_by_months)
    print(takeaway)
    
    # Save detailed results to JSON
    output_path = base_path / 'sff_hprd_analysis_results.json'
    output_data = {
        'analysis_by_type': results_by_type,
        'analysis_by_months': results_by_months,
        'phoebe_takeaway': takeaway
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, default=str)
    
    print(f"\n\nDetailed results saved to: {output_path}")

if __name__ == '__main__':
    main()

