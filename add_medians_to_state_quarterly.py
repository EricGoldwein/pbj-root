#!/usr/bin/env python3
"""
Script to calculate state and region medians from facility_quarterly_metrics.csv
and add them to state_quarterly_metrics.csv, plus create cms_region_quarterly_metrics.csv

This script:
1. Reads facility_quarterly_metrics.csv
2. For each state/quarter combination, calculates medians from facility-level data
3. Adds median columns to state_quarterly_metrics.csv
4. Creates cms_region_quarterly_metrics.csv with:
   - Aggregated averages (weighted by resident days) - same structure as state_quarterly_metrics.csv
   - Medians calculated from facility-level data for each region/quarter

Medians calculated:
- Total_Nurse_HPRD_Median
- RN_HPRD_Median
- Nurse_Care_HPRD_Median
- RN_Care_HPRD_Median
- Nurse_Assistant_HPRD_Median
- Contract_Percentage_Median
"""

import pandas as pd
import numpy as np
from collections import defaultdict

def calculate_median(values):
    """Calculate median - matches JavaScript implementation"""
    sorted_vals = sorted([v for v in values if not (pd.isna(v) or np.isnan(v)) and v > 0])
    if not sorted_vals:
        return np.nan
    mid = len(sorted_vals) // 2
    if len(sorted_vals) % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    return sorted_vals[mid]

def main():
    print("="*80)
    print("Adding Medians to State Quarterly Metrics")
    print("="*80)
    
    # Load data
    print("\n1. Loading data files...")
    facility_df = pd.read_csv('facility_lite_metrics.csv', low_memory=False)
    state_df = pd.read_csv('state_quarterly_metrics.csv')
    region_df = pd.read_csv('cms_region_state_mapping.csv')
    
    print(f"   - Loaded {len(facility_df):,} facility records")
    print(f"   - Loaded {len(state_df):,} state/quarter records")
    print(f"   - Loaded {len(region_df)} region mappings")
    
    # Create region mapping: state -> region info
    print("\n2. Creating region mapping...")
    state_to_region = {}
    for _, row in region_df.iterrows():
        state_abbr = row['State_Code'].strip()
        state_to_region[state_abbr] = {
            'regionNumber': int(row['CMS_Region_Number']),
            'regionName': row['CMS_Region_Name'].strip(),
            'regionFull': row['CMS_Region_Full'].strip()
        }
    print(f"   - Mapped {len(state_to_region)} states to regions")
    
    # Get most recent quarter only
    all_quarters = sorted(state_df['CY_Qtr'].unique())
    most_recent_quarter = all_quarters[-1] if all_quarters else None
    quarters = [most_recent_quarter] if most_recent_quarter else []
    
    if not most_recent_quarter:
        print("ERROR: No quarters found in state data")
        return
    
    print(f"\n3. Processing most recent quarter only: {most_recent_quarter}")
    
    # Initialize median columns in state_df
    median_columns = [
        'Total_Nurse_HPRD_Median',
        'RN_HPRD_Median',
        'Nurse_Care_HPRD_Median',
        'RN_Care_HPRD_Median',
        'Nurse_Assistant_HPRD_Median',
        'Contract_Percentage_Median'
    ]
    
    for col in median_columns:
        if col not in state_df.columns:
            state_df[col] = np.nan
    
    # Calculate state medians for most recent quarter only
    print(f"\n4. Calculating state medians for {most_recent_quarter}...")
    state_median_count = 0
    
    quarter = most_recent_quarter
    # Filter facilities for most recent quarter
    quarter_facilities = facility_df[facility_df['CY_Qtr'] == quarter].copy()
    
    if len(quarter_facilities) == 0:
        print(f"   - Warning: No facilities found for quarter {quarter}")
    else:
        # Group by state
        for state_abbr in state_df[state_df['CY_Qtr'] == quarter]['STATE'].unique():
            state_facilities = quarter_facilities[quarter_facilities['STATE'] == state_abbr].copy()
            
            if len(state_facilities) == 0:
                continue
            
            # Calculate medians - map column names from facility_lite_metrics.csv
            # facility_lite_metrics.csv has: Total_Nurse_HPRD, Nurse_Care_HPRD, Total_RN_HPRD, Direct_Care_RN_HPRD, Contract_Percentage
            medians = {
                'Total_Nurse_HPRD_Median': calculate_median(state_facilities['Total_Nurse_HPRD'].tolist()),
                'RN_HPRD_Median': calculate_median(state_facilities['Total_RN_HPRD'].tolist()) if 'Total_RN_HPRD' in state_facilities.columns else np.nan,
                'Nurse_Care_HPRD_Median': calculate_median(state_facilities['Nurse_Care_HPRD'].tolist()),
                'RN_Care_HPRD_Median': calculate_median(state_facilities['Direct_Care_RN_HPRD'].tolist()) if 'Direct_Care_RN_HPRD' in state_facilities.columns else np.nan,
                'Nurse_Assistant_HPRD_Median': np.nan,  # Not available in facility_lite_metrics.csv
                'Contract_Percentage_Median': calculate_median(state_facilities['Contract_Percentage'].tolist())
            }
            
            # Update state_df
            mask = (state_df['CY_Qtr'] == quarter) & (state_df['STATE'] == state_abbr)
            for col, value in medians.items():
                state_df.loc[mask, col] = value
            
            state_median_count += 1
    
    print(f"   - Calculated medians for {state_median_count} states")
    
    # Create CMS region quarterly metrics file (most recent quarter only)
    print(f"\n5. Creating cms_region_quarterly_metrics.csv for {quarter}...")
    
    # Group states by region
    region_states = defaultdict(list)
    region_info_map = {}
    for state_abbr, region_info in state_to_region.items():
        region_full = region_info['regionFull']
        region_states[region_full].append(state_abbr)
        if region_full not in region_info_map:
            region_info_map[region_full] = region_info
    
    # Build region quarterly metrics for most recent quarter only
    region_quarterly_rows = []
    
    # Filter facilities for most recent quarter (already filtered above)
    # quarter_facilities is already filtered to most recent quarter
    
    if len(quarter_facilities) == 0:
        print("   - Warning: No facilities found for most recent quarter")
    else:
        # Get state data for most recent quarter (for aggregating averages)
        quarter_state_data = state_df[state_df['CY_Qtr'] == quarter].copy()
        
        for region_full, states_in_region in region_states.items():
            # Get all facilities from states in this region
            # IMPORTANT: Calculate medians from facility-level data, not from state medians
            region_facilities = quarter_facilities[quarter_facilities['STATE'].isin(states_in_region)].copy()
            
            if len(region_facilities) == 0:
                continue
            
            print(f"   - Processing {region_full}: {len(region_facilities)} facilities")
            
            # Get state data for states in this region
            region_state_data = quarter_state_data[quarter_state_data['STATE'].isin(states_in_region)].copy()
            
            # Aggregate facility counts and resident days from state data (for consistency)
            # facility_lite_metrics.csv doesn't have hours or resident days, so we use state data
            facility_count = region_state_data['facility_count'].sum() if len(region_state_data) > 0 else len(region_facilities)
            total_resident_days = region_state_data['total_resident_days'].sum() if len(region_state_data) > 0 else 0
            avg_days_reported = region_state_data['avg_days_reported'].max() if len(region_state_data) > 0 else 0
            avg_daily_census = total_resident_days / (facility_count * avg_days_reported) if facility_count > 0 and avg_days_reported > 0 else 0
            MDScensus = region_state_data['MDScensus'].sum() if len(region_state_data) > 0 and 'MDScensus' in region_state_data.columns else 0
            
            # Aggregate hours from state data (weighted by resident days, matching JavaScript logic)
            # facility_lite_metrics.csv doesn't have hours columns, so we must use state data
            if len(region_state_data) > 0:
                # Aggregate from state data (already weighted)
                total_nurse_hours = (region_state_data['Total_Nurse_HPRD'] * region_state_data['total_resident_days']).sum()
                total_rn_hours = (region_state_data['RN_HPRD'] * region_state_data['total_resident_days']).sum()
                total_nurse_care_hours = (region_state_data['Nurse_Care_HPRD'] * region_state_data['total_resident_days']).sum()
                total_rn_care_hours = (region_state_data['RN_Care_HPRD'] * region_state_data['total_resident_days']).sum()
                total_nurse_assistant_hours = (region_state_data['Nurse_Assistant_HPRD'] * region_state_data['total_resident_days']).sum()
                total_contract_hours = (region_state_data['Total_Contract_Hours']).sum() if 'Total_Contract_Hours' in region_state_data.columns else 0
            else:
                # Fallback: set to 0 if no state data (shouldn't happen)
                total_nurse_hours = 0
                total_rn_hours = 0
                total_nurse_care_hours = 0
                total_rn_care_hours = 0
                total_nurse_assistant_hours = 0
                total_contract_hours = 0
            
            # Calculate weighted averages (HPRD)
            total_nurse_hprd = total_nurse_hours / total_resident_days if total_resident_days > 0 else 0
            rn_hprd = total_rn_hours / total_resident_days if total_resident_days > 0 else 0
            nurse_care_hprd = total_nurse_care_hours / total_resident_days if total_resident_days > 0 else 0
            rn_care_hprd = total_rn_care_hours / total_resident_days if total_resident_days > 0 else 0
            nurse_assistant_hprd = total_nurse_assistant_hours / total_resident_days if total_resident_days > 0 else 0
            contract_percentage = (total_contract_hours / total_nurse_hours * 100) if total_nurse_hours > 0 else 0
            
            # Calculate percentages
            direct_care_percentage = (total_nurse_care_hours / total_nurse_hours * 100) if total_nurse_hours > 0 else 0
            total_rn_percentage = (total_rn_hours / total_nurse_hours * 100) if total_nurse_hours > 0 else 0
            nurse_aide_percentage = (total_nurse_assistant_hours / total_nurse_hours * 100) if total_nurse_hours > 0 else 0
            
            # Calculate medians from facility-level data - map column names from facility_lite_metrics.csv
            medians = {
                'Total_Nurse_HPRD_Median': calculate_median(region_facilities['Total_Nurse_HPRD'].tolist()),
                'RN_HPRD_Median': calculate_median(region_facilities['Total_RN_HPRD'].tolist()) if 'Total_RN_HPRD' in region_facilities.columns else np.nan,
                'Nurse_Care_HPRD_Median': calculate_median(region_facilities['Nurse_Care_HPRD'].tolist()),
                'RN_Care_HPRD_Median': calculate_median(region_facilities['Direct_Care_RN_HPRD'].tolist()) if 'Direct_Care_RN_HPRD' in region_facilities.columns else np.nan,
                'Nurse_Assistant_HPRD_Median': np.nan,  # Not available in facility_lite_metrics.csv
                'Contract_Percentage_Median': calculate_median(region_facilities['Contract_Percentage'].tolist())
            }
            
            # Get region info
            region_info = region_info_map[region_full]
            
            # Create row matching state_quarterly_metrics.csv structure
            region_row = {
                'REGION': region_full,  # Use REGION column instead of STATE
                'REGION_NUMBER': region_info['regionNumber'],
                'REGION_NAME': region_info['regionName'],
                'CY_Qtr': quarter,
                'facility_count': facility_count,
                'avg_days_reported': avg_days_reported,
                'total_resident_days': total_resident_days,
                'avg_daily_census': avg_daily_census,
                'MDScensus': MDScensus,
                'Total_Nurse_Hours': total_nurse_hours,
                'Total_RN_Hours': total_rn_hours,
                'Total_Nurse_Care_Hours': total_nurse_care_hours,
                'Total_RN_Care_Hours': total_rn_care_hours,
                'Total_Nurse_Assistant_Hours': total_nurse_assistant_hours,
                'Total_Contract_Hours': total_contract_hours,
                'Total_Nurse_HPRD': total_nurse_hprd,
                'RN_HPRD': rn_hprd,
                'Nurse_Care_HPRD': nurse_care_hprd,
                'RN_Care_HPRD': rn_care_hprd,
                'Nurse_Assistant_HPRD': nurse_assistant_hprd,
                'Contract_Percentage': contract_percentage,
                'Direct_Care_Percentage': direct_care_percentage,
                'Total_RN_Percentage': total_rn_percentage,
                'Nurse_Aide_Percentage': nurse_aide_percentage,
                **medians
            }
            
            region_quarterly_rows.append(region_row)
    
    print(f"   - Calculated data for {len(region_quarterly_rows)} regions")
    
    # Create region quarterly metrics DataFrame
    if region_quarterly_rows:
        region_quarterly_df = pd.DataFrame(region_quarterly_rows)
        
        # Ensure median columns are in the right order
        column_order = [
            'REGION', 'REGION_NUMBER', 'REGION_NAME', 'CY_Qtr',
            'facility_count', 'avg_days_reported', 'total_resident_days', 'avg_daily_census', 'MDScensus',
            'Total_Nurse_Hours', 'Total_RN_Hours', 'Total_Nurse_Care_Hours', 'Total_RN_Care_Hours',
            'Total_Nurse_Assistant_Hours', 'Total_Contract_Hours',
            'Total_Nurse_HPRD', 'RN_HPRD', 'Nurse_Care_HPRD', 'RN_Care_HPRD',
            'Nurse_Assistant_HPRD', 'Contract_Percentage',
            'Direct_Care_Percentage', 'Total_RN_Percentage', 'Nurse_Aide_Percentage',
            'Total_Nurse_HPRD_Median', 'RN_HPRD_Median', 'Nurse_Care_HPRD_Median',
            'RN_Care_HPRD_Median', 'Nurse_Assistant_HPRD_Median', 'Contract_Percentage_Median'
        ]
        
        # Reorder columns
        region_quarterly_df = region_quarterly_df[column_order]
        
        # Save region quarterly metrics
        print("\n6. Saving cms_region_quarterly_metrics.csv...")
        try:
            region_quarterly_df.to_csv('cms_region_quarterly_metrics.csv', index=False)
            print(f"   - Saved {len(region_quarterly_df):,} region/quarter rows")
        except PermissionError:
            # If permission denied, save to a temporary file
            temp_filename = 'cms_region_quarterly_metrics_updated.csv'
            region_quarterly_df.to_csv(temp_filename, index=False)
            print(f"   - ERROR: Could not write to cms_region_quarterly_metrics.csv (file may be open)")
            print(f"   - Saved to {temp_filename} instead")
            print(f"   - Please close cms_region_quarterly_metrics.csv and manually replace it with {temp_filename}")
    else:
        print("\n6. Warning: No region data to save")
    
    # Filter state_df to most recent quarter only before saving
    print("\n7. Filtering state_quarterly_metrics.csv to most recent quarter only...")
    state_df_latest = state_df[state_df['CY_Qtr'] == quarter].copy()
    print(f"   - Filtered to {len(state_df_latest):,} rows (from {len(state_df):,} total)")
    
    # Save updated state_quarterly_metrics.csv (most recent quarter only)
    print("\n8. Saving updated state_quarterly_metrics.csv...")
    try:
        # Try to save directly
        state_df_latest.to_csv('state_quarterly_metrics.csv', index=False)
        print(f"   - Saved {len(state_df_latest):,} state rows for {quarter}")
    except PermissionError:
        # If permission denied, save to a temporary file and ask user to replace manually
        temp_filename = 'state_quarterly_metrics_updated.csv'
        state_df_latest.to_csv(temp_filename, index=False)
        print(f"   - ERROR: Could not write to state_quarterly_metrics.csv (file may be open in Excel)")
        print(f"   - Saved to {temp_filename} instead")
        print(f"   - Please close state_quarterly_metrics.csv and manually replace it with {temp_filename}")
        print(f"   - Or run the script again after closing the file")
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"✓ Added median columns to state_quarterly_metrics.csv (quarter: {quarter}):")
    for col in median_columns:
        non_null = state_df_latest[col].notna().sum()
        print(f"   - {col}: {non_null:,} values calculated")
    
    if region_quarterly_rows:
        print(f"\n✓ Created cms_region_quarterly_metrics.csv with:")
        print(f"   - {len(region_quarterly_rows)} region/quarter combinations")
        print(f"   - Aggregated averages (weighted by resident days)")
        print(f"   - Facility-level medians")
        for col in median_columns:
            non_null = region_quarterly_df[col].notna().sum()
            print(f"   - {col}: {non_null:,} values calculated")
    
    print("\n" + "="*80)
    print("Next steps:")
    print("1. Update report.html to read medians from state_quarterly_metrics.csv")
    print("2. Update report.html to read region data from cms_region_quarterly_metrics.csv")
    print("3. Remove on-the-fly median calculations from JavaScript")
    print("="*80)

if __name__ == '__main__':
    main()

