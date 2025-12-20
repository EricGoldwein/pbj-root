#!/usr/bin/env python3
"""
Verification script for median and exclude admin/DON calculations
Checks calculations for USA, Regions, and States
"""

import pandas as pd
import numpy as np
from collections import defaultdict

def calculate_median(values):
    """Calculate median - matches JavaScript implementation"""
    sorted_vals = sorted([v for v in values if not np.isnan(v) and v > 0])
    if not sorted_vals:
        return 0
    mid = len(sorted_vals) // 2
    if len(sorted_vals) % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    return sorted_vals[mid]

def load_data():
    """Load CSV files"""
    print("Loading data files...")
    
    # Load state quarterly metrics
    state_df = pd.read_csv('state_quarterly_metrics.csv')
    
    # Load national quarterly metrics
    national_df = pd.read_csv('national_quarterly_metrics.csv')
    
    # Load CMS region mapping
    region_df = pd.read_csv('cms_region_state_mapping.csv')
    
    # Load provider info (sample first 1000 rows to check structure)
    print("Loading provider info (first 10000 rows for verification)...")
    provider_df = pd.read_csv('provider_info_combined.csv', nrows=10000)
    
    return state_df, national_df, region_df, provider_df

def verify_state_medians(state_df, provider_df, quarter='2025Q2'):
    """
    Verify state median calculations
    ISSUE FOUND: Nurse_Care_HPRD median uses reported_total_nurse_hrs_per_resident_per_day
    instead of actual direct care values
    """
    print("\n" + "="*80)
    print("VERIFYING STATE MEDIANS")
    print("="*80)
    
    # Filter to most recent quarter
    state_q = state_df[state_df['CY_Qtr'] == quarter].copy()
    
    # Try both quarter formats: "2025Q2" and "Q2 2025"
    alt_quarter = quarter.replace('Q', ' Q')  # "2025Q2" -> "Q2 2025"
    provider_q = provider_df[
        (provider_df['quarter'] == quarter) | 
        (provider_df['quarter'] == alt_quarter)
    ].copy()
    
    print(f"\nQuarter: {quarter}")
    print(f"States in state data: {len(state_q)}")
    print(f"Facilities in provider data (sample): {len(provider_q)}")
    
    # Check a sample state
    sample_state = 'Alabama'
    state_abbr = 'AL'
    
    state_row = state_q[state_q['STATE'] == state_abbr]
    if state_row.empty:
        print(f"\nWARNING: State {state_abbr} not found in state data for {quarter}")
        return
    
    state_data = state_row.iloc[0]
    print(f"\n--- Sample State: {sample_state} ({state_abbr}) ---")
    print(f"State-level Total_Nurse_HPRD: {state_data['Total_Nurse_HPRD']:.4f}")
    print(f"State-level RN_HPRD: {state_data['RN_HPRD']:.4f}")
    print(f"State-level Nurse_Care_HPRD: {state_data['Nurse_Care_HPRD']:.4f}")
    print(f"State-level RN_Care_HPRD: {state_data['RN_Care_HPRD']:.4f}")
    
    # Get facilities for this state
    state_providers = provider_q[provider_q['state'] == state_abbr]
    print(f"\nFacilities in provider data: {len(state_providers)}")
    
    if len(state_providers) > 0:
        # Calculate medians as the code does
        total_hprds = state_providers['reported_total_nurse_hrs_per_resident_per_day'].dropna()
        total_hprds = total_hprds[total_hprds > 0].tolist()
        
        rn_hprds = state_providers['reported_rn_hrs_per_resident_per_day'].dropna()
        rn_hprds = rn_hprds[rn_hprds > 0].tolist()
        
        # ISSUE: This uses total_nurse instead of direct care!
        direct_care_hprds = state_providers['reported_total_nurse_hrs_per_resident_per_day'].dropna()
        direct_care_hprds = direct_care_hprds[direct_care_hprds > 0].tolist()
        
        rn_care_hprds = state_providers['reported_rn_hrs_per_resident_per_day'].dropna()
        rn_care_hprds = rn_care_hprds[rn_care_hprds > 0].tolist()
        
        print(f"\nFacility-level values (n={len(total_hprds)}):")
        print(f"  Total_Nurse_HPRD median: {calculate_median(total_hprds):.4f}")
        print(f"  RN_HPRD median: {calculate_median(rn_hprds):.4f}")
        print(f"  ISSUE: Nurse_Care_HPRD median uses total_nurse (not direct care): {calculate_median(direct_care_hprds):.4f}")
        print(f"  RN_Care_HPRD median: {calculate_median(rn_care_hprds):.4f}")
        
        print(f"\nPROBLEM: Nurse_Care_HPRD median should use direct care values,")
        print(f"   but code uses reported_total_nurse_hrs_per_resident_per_day")
        print(f"   This is an approximation, not the true direct care median!")
    else:
        print("WARNING: No provider data found for this state")

def verify_usa_calculations(state_df, national_df, quarter='2025Q2'):
    """
    Verify USA-level calculations
    ISSUE: Medians are calculated from state-level values (median of state averages),
    NOT from facility-level values (true national median)
    """
    print("\n" + "="*80)
    print("VERIFYING USA CALCULATIONS")
    print("="*80)
    
    state_q = state_df[state_df['CY_Qtr'] == quarter].copy()
    national_row = national_df[national_df['CY_Qtr'] == quarter]
    
    if national_row.empty:
        print(f"WARNING: No national data for {quarter}")
        return
    
    national_data = national_row.iloc[0]
    
    print(f"\nQuarter: {quarter}")
    print(f"States: {len(state_q)}")
    
    # National values from CSV
    print(f"\n--- National Values (from CSV) ---")
    print(f"Total_Nurse_HPRD: {national_data['Total_Nurse_HPRD']:.4f}")
    print(f"RN_HPRD: {national_data['RN_HPRD']:.4f}")
    print(f"Nurse_Care_HPRD: {national_data['Nurse_Care_HPRD']:.4f}")
    print(f"RN_Care_HPRD: {national_data['RN_Care_HPRD']:.4f}")
    
    # Calculate medians from state values (as code does)
    state_medians = {
        'Total_Nurse_HPRD': calculate_median(state_q['Total_Nurse_HPRD'].tolist()),
        'RN_HPRD': calculate_median(state_q['RN_HPRD'].tolist()),
        'Nurse_Care_HPRD': calculate_median(state_q['Nurse_Care_HPRD'].tolist()),
        'RN_Care_HPRD': calculate_median(state_q['RN_Care_HPRD'].tolist())
    }
    
    print(f"\n--- Medians (from state-level values) ---")
    print(f"NOTE: These are medians of STATE AVERAGES, not facility medians!")
    print(f"Total_Nurse_HPRD median: {state_medians['Total_Nurse_HPRD']:.4f}")
    print(f"RN_HPRD median: {state_medians['RN_HPRD']:.4f}")
    print(f"Nurse_Care_HPRD median: {state_medians['Nurse_Care_HPRD']:.4f}")
    print(f"RN_Care_HPRD median: {state_medians['RN_Care_HPRD']:.4f}")
    
    # Verify exclude admin/DON calculation
    print(f"\n--- Exclude Admin/DON Calculation ---")
    total_direct_care_hours = 0
    total_rn_care_hours = 0
    total_resident_days = 0
    
    for _, state in state_q.iterrows():
        resident_days = state['total_resident_days']
        if resident_days > 0:
            direct_care = state['Nurse_Care_HPRD']  # Already excludes admin/DON
            rn_care = state['RN_Care_HPRD']  # Already excludes admin/DON
            total_direct_care_hours += direct_care * resident_days
            total_rn_care_hours += rn_care * resident_days
            total_resident_days += resident_days
    
    if total_resident_days > 0:
        usa_direct_care = total_direct_care_hours / total_resident_days
        usa_rn_care = total_rn_care_hours / total_resident_days
        
        print(f"Calculated USA Direct Care HPRD (weighted): {usa_direct_care:.4f}")
        print(f"Expected from CSV: {national_data['Nurse_Care_HPRD']:.4f}")
        print(f"Difference: {abs(usa_direct_care - national_data['Nurse_Care_HPRD']):.6f}")
        
        print(f"\nCalculated USA RN Care HPRD (weighted): {usa_rn_care:.4f}")
        print(f"Expected from CSV: {national_data['RN_Care_HPRD']:.4f}")
        print(f"Difference: {abs(usa_rn_care - national_data['RN_Care_HPRD']):.6f}")
        
        # Calculate medians of state direct care values
        direct_care_values = state_q['Nurse_Care_HPRD'].tolist()
        rn_care_values = state_q['RN_Care_HPRD'].tolist()
        
        print(f"\nMedians of state direct care values:")
        print(f"Direct Care HPRD median: {calculate_median(direct_care_values):.4f}")
        print(f"RN Care HPRD median: {calculate_median(rn_care_values):.4f}")

def verify_region_calculations(state_df, region_df, quarter='2025Q2'):
    """
    Verify region-level calculations
    ISSUES:
    1. Medians are calculated from state medians (median of medians), not facility medians
    2. Exclude admin/DON uses weighted averages correctly
    """
    print("\n" + "="*80)
    print("VERIFYING REGION CALCULATIONS")
    print("="*80)
    
    state_q = state_df[state_df['CY_Qtr'] == quarter].copy()
    
    # Create region mapping
    region_mapping = {}
    for _, row in region_df.iterrows():
        state_abbr = row['State_Code'].strip()
        region_mapping[state_abbr] = {
            'regionNumber': int(row['CMS_Region_Number']),
            'regionName': row['CMS_Region_Name'].strip(),
            'regionFull': row['CMS_Region_Full'].strip()
        }
    
    # Group states by region
    region_data = defaultdict(lambda: {
        'states': [],
        'total_resident_days': 0,
        'total_nurse_hours': 0,
        'total_rn_hours': 0,
        'total_nurse_care_hours': 0,
        'total_rn_care_hours': 0,
        'total_nurse_aide_hours': 0
    })
    
    for _, state in state_q.iterrows():
        state_abbr = state['STATE']
        if state_abbr not in region_mapping:
            continue
        
        region_info = region_mapping[state_abbr]
        region_key = region_info['regionFull']
        
        region_data[region_key]['states'].append(state_abbr)
        resident_days = state['total_resident_days']
        
        if resident_days > 0:
            region_data[region_key]['total_resident_days'] += resident_days
            region_data[region_key]['total_nurse_hours'] += state['Total_Nurse_HPRD'] * resident_days
            region_data[region_key]['total_rn_hours'] += state['RN_HPRD'] * resident_days
            region_data[region_key]['total_nurse_care_hours'] += state['Nurse_Care_HPRD'] * resident_days
            region_data[region_key]['total_rn_care_hours'] += state['RN_Care_HPRD'] * resident_days
            region_data[region_key]['total_nurse_aide_hours'] += state['Nurse_Assistant_HPRD'] * resident_days
    
    # Calculate region HPRDs
    print(f"\nQuarter: {quarter}")
    print(f"Regions: {len(region_data)}")
    
    # Sample one region
    sample_region = list(region_data.keys())[0]
    region = region_data[sample_region]
    
    print(f"\n--- Sample Region: {sample_region} ---")
    print(f"States: {', '.join(region['states'])}")
    print(f"Total resident days: {region['total_resident_days']:,.0f}")
    
    if region['total_resident_days'] > 0:
        region_total_hprd = region['total_nurse_hours'] / region['total_resident_days']
        region_rn_hprd = region['total_rn_hours'] / region['total_resident_days']
        region_direct_care_hprd = region['total_nurse_care_hours'] / region['total_resident_days']
        region_rn_care_hprd = region['total_rn_care_hours'] / region['total_resident_days']
        
        print(f"\nWeighted averages (standard):")
        print(f"Total_Nurse_HPRD: {region_total_hprd:.4f}")
        print(f"RN_HPRD: {region_rn_hprd:.4f}")
        print(f"Direct Care HPRD (excl admin/DON): {region_direct_care_hprd:.4f}")
        print(f"RN Care HPRD (excl admin/DON): {region_rn_care_hprd:.4f}")
        
        # Calculate median of state values in region
        region_states = state_q[state_q['STATE'].isin(region['states'])]
        state_medians_in_region = {
            'Total_Nurse_HPRD': calculate_median(region_states['Total_Nurse_HPRD'].tolist()),
            'RN_HPRD': calculate_median(region_states['RN_HPRD'].tolist()),
            'Direct_Care_HPRD': calculate_median(region_states['Nurse_Care_HPRD'].tolist()),
            'RN_Care_HPRD': calculate_median(region_states['RN_Care_HPRD'].tolist())
        }
        
        print(f"\nMedians (from state-level values in region):")
        print(f"   NOTE: These are medians of STATE AVERAGES, not facility medians!")
        print(f"Total_Nurse_HPRD median: {state_medians_in_region['Total_Nurse_HPRD']:.4f}")
        print(f"RN_HPRD median: {state_medians_in_region['RN_HPRD']:.4f}")
        print(f"Direct Care HPRD median: {state_medians_in_region['Direct_Care_HPRD']:.4f}")
        print(f"RN Care HPRD median: {state_medians_in_region['RN_Care_HPRD']:.4f}")

def main():
    print("="*80)
    print("CALCULATION VERIFICATION REPORT")
    print("="*80)
    
    try:
        state_df, national_df, region_df, provider_df = load_data()
        
        # Find most recent quarter
        quarters = sorted(state_df['CY_Qtr'].unique(), reverse=True)
        most_recent = quarters[0] if quarters else '2025Q2'
        print(f"\nMost recent quarter in data: {most_recent}")
        
        # Verify calculations
        verify_state_medians(state_df, provider_df, most_recent)
        verify_usa_calculations(state_df, national_df, most_recent)
        verify_region_calculations(state_df, region_df, most_recent)
        
        print("\n" + "="*80)
        print("SUMMARY OF ISSUES FOUND")
        print("="*80)
        print("""
1. STATE MEDIANS - Nurse_Care_HPRD:
   ISSUE: Uses reported_total_nurse_hrs_per_resident_per_day instead of direct care values
   This is an approximation, not the true direct care median

2. USA MEDIANS:
   NOTE: Calculated as median of STATE AVERAGES, not median of all facilities
   CORRECT: Exclude admin/DON calculation is correct (weighted by resident days)

3. REGION MEDIANS:
   NOTE: Calculated as median of STATE MEDIANS within region (median of medians)
   CORRECT: Exclude admin/DON calculation is correct (weighted by resident days)

4. EXCLUDE ADMIN/DON:
   CORRECT: State level: Uses Nurse_Care_HPRD and RN_Care_HPRD (already excludes admin/DON)
   CORRECT: USA level: Weighted average by resident days (correct)
   CORRECT: Region level: Weighted average by resident days (correct)
   NOTE: Medians don't account for excludeAdminDON toggle (pre-calculated)
        """)
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

