#!/usr/bin/env python3
"""
Script to generate quarterly_medians.json with national-level medians for all quarters.

This script:
1. Reads facility_quarterly_metrics.csv (or facility_lite_metrics.csv)
2. Calculates national medians for each quarter
3. Updates quarterly_medians.json with missing quarters (Q2 and Q3 2025)

Medians calculated:
- Total_Nurse_HPRD_Median
- RN_HPRD_Median (from Total_RN_HPRD)
- Nurse_Care_HPRD_Median
- RN_Care_HPRD_Median (from Direct_Care_RN_HPRD)
- Contract_Percentage_Median
"""

import pandas as pd
import numpy as np
import json
import os

def calculate_median(values, exclude_zeros=False):
    """Calculate median - matches JavaScript implementation
    For contract percentage, include zeros since many facilities have 0% contract staffing
    """
    if exclude_zeros:
        sorted_vals = sorted([v for v in values if not (pd.isna(v) or np.isnan(v)) and v > 0])
    else:
        sorted_vals = sorted([v for v in values if not (pd.isna(v) or np.isnan(v))])
    if not sorted_vals:
        return np.nan
    mid = len(sorted_vals) // 2
    if len(sorted_vals) % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    return sorted_vals[mid]

def main():
    print("="*80)
    print("GENERATING QUARTERLY MEDIANS")
    print("="*80)
    
    # Try to load facility data
    facility_file = None
    if os.path.exists('facility_lite_metrics.csv'):
        facility_file = 'facility_lite_metrics.csv'
        print(f"\n1. Loading {facility_file}...")
        facility_df = pd.read_csv(facility_file, low_memory=False)
    elif os.path.exists('facility_quarterly_metrics.csv'):
        facility_file = 'facility_quarterly_metrics.csv'
        print(f"\n1. Loading {facility_file}...")
        facility_df = pd.read_csv(facility_file, low_memory=False)
    else:
        print("ERROR: Neither facility_lite_metrics.csv nor facility_quarterly_metrics.csv found")
        return
    
    print(f"   - Loaded {len(facility_df):,} facility records")
    
    # Load existing quarterly_medians.json
    print("\n2. Loading existing quarterly_medians.json...")
    if os.path.exists('quarterly_medians.json'):
        with open('quarterly_medians.json', 'r') as f:
            existing_medians = json.load(f)
        print(f"   - Found {len(existing_medians)} existing quarters")
    else:
        existing_medians = []
        print("   - No existing file, starting fresh")
    
    # Get all quarters from facility data
    all_quarters = sorted(facility_df['CY_Qtr'].unique())
    print(f"\n3. Found {len(all_quarters)} quarters in facility data")
    print(f"   - First quarter: {all_quarters[0]}")
    print(f"   - Last quarter: {all_quarters[-1]}")
    
    # Create a dictionary of existing medians by quarter
    existing_by_quarter = {item['CY_Qtr']: item for item in existing_medians}
    
    # Calculate medians for each quarter
    print("\n4. Calculating medians for each quarter...")
    all_medians = []
    
    for quarter in all_quarters:
        quarter_facilities = facility_df[facility_df['CY_Qtr'] == quarter].copy()
        
        if len(quarter_facilities) == 0:
            print(f"   - Warning: No facilities found for {quarter}")
            continue
        
        # Check if we already have this quarter
        # Force recalculation for Q2 and Q3 2025 to fix contract % median
        force_recalculate = quarter in ['2025Q2', '2025Q3']
        
        if quarter in existing_by_quarter and not force_recalculate:
            # Use existing data but verify/update if needed
            median_data = existing_by_quarter[quarter].copy()
            print(f"   - {quarter}: Using existing data (facility_count: {median_data.get('facility_count', 'N/A')})")
        else:
            # Calculate new medians
            print(f"   - {quarter}: Calculating medians from {len(quarter_facilities):,} facilities...")
            
            # Map column names based on which file we're using
            if 'Total_RN_HPRD' in quarter_facilities.columns:
                rn_col = 'Total_RN_HPRD'
            elif 'RN_HPRD' in quarter_facilities.columns:
                rn_col = 'RN_HPRD'
            else:
                rn_col = None
            
            if 'Direct_Care_RN_HPRD' in quarter_facilities.columns:
                rn_care_col = 'Direct_Care_RN_HPRD'
            elif 'RN_Care_HPRD' in quarter_facilities.columns:
                rn_care_col = 'RN_Care_HPRD'
            else:
                rn_care_col = None
            
            median_data = {
                'CY_Qtr': quarter,
                'Total_Nurse_HPRD_Median': calculate_median(quarter_facilities['Total_Nurse_HPRD'].tolist(), exclude_zeros=True),
                'Contract_Percentage_Median': calculate_median(quarter_facilities['Contract_Percentage'].tolist(), exclude_zeros=False),  # Include zeros for contract %
                'facility_count': len(quarter_facilities)
            }
            
            # Add RN HPRD median if column exists
            if rn_col and rn_col in quarter_facilities.columns:
                median_data['RN_HPRD_Median'] = calculate_median(quarter_facilities[rn_col].tolist(), exclude_zeros=True)
            else:
                median_data['RN_HPRD_Median'] = np.nan
            
            # Add Nurse Care HPRD median
            if 'Nurse_Care_HPRD' in quarter_facilities.columns:
                median_data['Nurse_Care_HPRD_Median'] = calculate_median(quarter_facilities['Nurse_Care_HPRD'].tolist(), exclude_zeros=True)
            else:
                median_data['Nurse_Care_HPRD_Median'] = np.nan
            
            # Add RN Care HPRD median if column exists
            if rn_care_col and rn_care_col in quarter_facilities.columns:
                median_data['RN_Care_HPRD_Median'] = calculate_median(quarter_facilities[rn_care_col].tolist(), exclude_zeros=True)
            else:
                median_data['RN_Care_HPRD_Median'] = np.nan
        
        # Convert NaN to None for JSON serialization
        for key, value in median_data.items():
            if pd.isna(value) or (isinstance(value, float) and np.isnan(value)):
                median_data[key] = None
            elif isinstance(value, (np.integer, np.floating)):
                median_data[key] = float(value)
        
        all_medians.append(median_data)
    
    # Sort by quarter
    all_medians.sort(key=lambda x: x['CY_Qtr'])
    
    # Save updated file
    print(f"\n5. Saving quarterly_medians.json...")
    with open('quarterly_medians.json', 'w') as f:
        json.dump(all_medians, f, indent=2)
    
    print(f"   - Saved {len(all_medians)} quarters")
    
    # Show summary of latest quarters
    print(f"\n6. Latest quarters in file:")
    for item in all_medians[-5:]:
        q = item['CY_Qtr']
        hprd = item.get('Total_Nurse_HPRD_Median', 'N/A')
        contract = item.get('Contract_Percentage_Median', 'N/A')
        count = item.get('facility_count', 'N/A')
        print(f"   - {q}: HPRD={hprd}, Contract%={contract}, Facilities={count}")
    
    print("\n" + "="*80)
    print("SUCCESS: quarterly_medians.json updated!")
    print("="*80)

if __name__ == '__main__':
    main()
