#!/usr/bin/env python3
"""
Extract Q3 2025 daily data for facility 335513 (Seagate) and append to facility_335513_complete_data.csv

This script:
1. Looks for Q3 2025 daily data in source files
2. Filters for facility 335513
3. Appends to facility_335513_complete_data.csv

Usage:
    python extract_seagate_q3_data.py [source_file.csv]

If no source file is provided, it will look for common PBJ daily data file names.
"""

import pandas as pd
import sys
import os
from pathlib import Path

FACILITY_NUM = '335513'
TARGET_QUARTER = '2025Q3'
Q3_START_DATE = 20250701  # July 1, 2025
Q3_END_DATE = 20250930    # September 30, 2025

def find_source_file():
    """Look for potential source files with daily PBJ data"""
    possible_names = [
        'pbj_nursing_staff_q3_2025.csv',
        'nursing_staff_q3_2025.csv',
        'pbj_daily_q3_2025.csv',
        'NH_PBJ_Nursing_Staff_Q3_2025.csv',
        'NH_PBJ_Nursing_Staff_2025Q3.csv',
    ]
    
    # Check current directory and common locations
    search_paths = [
        Path('.'),
        Path('../'),
        Path('pbj_lite/'),
        Path('../pbj_lite/'),
    ]
    
    for path in search_paths:
        for name in possible_names:
            full_path = path / name
            if full_path.exists():
                return str(full_path)
    
    return None

def extract_q3_data_from_source(source_file):
    """Extract Q3 2025 data for facility 335513 from source file"""
    print(f"Reading source file: {source_file}")
    
    # Try to read the file - handle different formats
    try:
        # Try reading with different encodings and separators
        df = pd.read_csv(source_file, low_memory=False, encoding='utf-8')
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(source_file, low_memory=False, encoding='latin-1')
        except:
            df = pd.read_csv(source_file, low_memory=False, encoding='cp1252')
    
    print(f"  Loaded {len(df):,} rows from source file")
    print(f"  Columns: {list(df.columns)[:10]}...")
    
    # Find facility identifier column (could be PROVNUM, CCN, Provider_Number, etc.)
    facility_col = None
    for col in df.columns:
        if col.upper() in ['PROVNUM', 'CCN', 'PROVIDER_NUMBER', 'PROVIDERNUMBER', 'FACILITY_ID']:
            facility_col = col
            break
    
    if not facility_col:
        print("ERROR: Could not find facility identifier column")
        print(f"Available columns: {list(df.columns)}")
        return None
    
    # Find date column
    date_col = None
    for col in df.columns:
        if col.upper() in ['WORKDATE', 'WORK_DATE', 'DATE', 'REPORTING_DATE', 'PAYROLL_DATE']:
            date_col = col
            break
    
    if not date_col:
        print("ERROR: Could not find date column")
        print(f"Available columns: {list(df.columns)}")
        return None
    
    # Filter for facility 335513
    # Convert facility column to string for comparison
    df[facility_col] = df[facility_col].astype(str).str.strip()
    facility_df = df[df[facility_col] == FACILITY_NUM].copy()
    
    if len(facility_df) == 0:
        print(f"WARNING: No data found for facility {FACILITY_NUM} in source file")
        return None
    
    print(f"  Found {len(facility_df):,} rows for facility {FACILITY_NUM}")
    
    # Filter for Q3 2025 dates
    # Convert date to integer format (YYYYMMDD) for comparison
    if date_col in facility_df.columns:
        # Handle different date formats
        date_series = pd.to_datetime(facility_df[date_col], errors='coerce')
        facility_df['_date_int'] = date_series.dt.strftime('%Y%m%d').astype(float)
        q3_df = facility_df[
            (facility_df['_date_int'] >= Q3_START_DATE) & 
            (facility_df['_date_int'] <= Q3_END_DATE)
        ].copy()
        facility_df = facility_df.drop('_date_int', axis=1)
    else:
        print("WARNING: Could not filter by date - date column not found")
        q3_df = facility_df
    
    print(f"  Found {len(q3_df):,} rows for Q3 2025 (July 1 - September 30, 2025)")
    
    if len(q3_df) == 0:
        print("WARNING: No Q3 2025 data found")
        return None
    
    return q3_df

def load_existing_file():
    """Load existing facility_335513_complete_data.csv"""
    file_path = 'facility_335513_complete_data.csv'
    if not os.path.exists(file_path):
        print(f"ERROR: {file_path} not found")
        return None
    
    df = pd.read_csv(file_path, low_memory=False)
    print(f"Loaded existing file: {len(df):,} rows")
    print(f"  Last date: {df['WorkDate'].max()}")
    print(f"  Last quarter: {df['CY_Qtr'].iloc[-1] if len(df) > 0 else 'N/A'}")
    return df

def map_columns(source_df, existing_df):
    """Map columns from source to match existing file format"""
    # Get column mapping - this will need to be adjusted based on actual source file format
    existing_cols = list(existing_df.columns)
    
    # Create a mapping dictionary
    # This is a placeholder - actual mapping will depend on source file format
    column_mapping = {}
    
    # Try to auto-detect column mappings
    source_cols_lower = {col.lower(): col for col in source_df.columns}
    existing_cols_lower = {col.lower(): col for col in existing_cols}
    
    for existing_col in existing_cols:
        existing_lower = existing_col.lower()
        if existing_lower in source_cols_lower:
            column_mapping[existing_col] = source_cols_lower[existing_lower]
        # Also try partial matches
        for source_col_lower, source_col in source_cols_lower.items():
            if existing_lower.replace('_', '').replace('hrs', 'hours') in source_col_lower:
                if existing_col not in column_mapping:
                    column_mapping[existing_col] = source_col
    
    print(f"Column mapping: {len(column_mapping)} columns matched")
    return column_mapping

def main():
    print("=" * 80)
    print("Extract Q3 2025 Data for Facility 335513 (Seagate)")
    print("=" * 80)
    print()
    
    # Check for source file argument
    if len(sys.argv) > 1:
        source_file = sys.argv[1]
    else:
        source_file = find_source_file()
        if not source_file:
            print("ERROR: No source file provided and none found automatically")
            print("\nUsage:")
            print("  python extract_seagate_q3_data.py <source_file.csv>")
            print("\nOr place a PBJ daily data file in the current directory with one of these names:")
            print("  - pbj_nursing_staff_q3_2025.csv")
            print("  - nursing_staff_q3_2025.csv")
            print("  - pbj_daily_q3_2025.csv")
            return
    
    if not os.path.exists(source_file):
        print(f"ERROR: Source file not found: {source_file}")
        return
    
    # Load existing file
    existing_df = load_existing_file()
    if existing_df is None:
        return
    
    # Extract Q3 2025 data
    q3_df = extract_q3_data_from_source(source_file)
    if q3_df is None or len(q3_df) == 0:
        print("\nCould not extract Q3 2025 data. Please check:")
        print("  1. Source file contains data for facility 335513")
        print("  2. Source file contains Q3 2025 dates (July 1 - September 30, 2025)")
        print("  3. Column names match expected format")
        return
    
    # Map columns to match existing file format
    # For now, we'll assume the source file has similar column names
    # You may need to adjust this based on your actual source file format
    
    # Ensure Q3 data has CY_Qtr column set to 2025Q3
    if 'CY_Qtr' in q3_df.columns:
        q3_df['CY_Qtr'] = TARGET_QUARTER
    elif 'CY_Qtr' in existing_df.columns:
        q3_df['CY_Qtr'] = TARGET_QUARTER
    
    # Ensure WorkDate is in correct format (YYYYMMDD integer)
    if 'WorkDate' in q3_df.columns:
        # Convert to integer format if it's a date
        if q3_df['WorkDate'].dtype == 'object':
            q3_df['WorkDate'] = pd.to_datetime(q3_df['WorkDate'], errors='coerce').dt.strftime('%Y%m%d').astype(int)
    
    # Try to align columns
    # Get columns that exist in both
    common_cols = [col for col in existing_df.columns if col in q3_df.columns]
    missing_cols = [col for col in existing_df.columns if col not in q3_df.columns]
    
    if missing_cols:
        print(f"\nWARNING: {len(missing_cols)} columns missing in source data:")
        print(f"  {missing_cols[:10]}...")
        print("  These will be filled with NaN or default values")
    
    # Select and reorder columns to match existing file
    q3_aligned = pd.DataFrame()
    for col in existing_df.columns:
        if col in q3_df.columns:
            q3_aligned[col] = q3_df[col]
        else:
            # Fill missing columns with appropriate defaults
            if col == 'PROVNUM':
                q3_aligned[col] = FACILITY_NUM
            elif col == 'PROVNAME':
                q3_aligned[col] = 'SEAGATE REHABILITATION AND NURSING CENTER'
            elif col == 'CITY':
                q3_aligned[col] = 'BROOKLYN'
            elif col == 'STATE':
                q3_aligned[col] = 'NY'
            elif col == 'COUNTY_NAME':
                q3_aligned[col] = 'Kings'
            elif col == 'COUNTY_FIPS':
                q3_aligned[col] = 47
            elif col == 'CY_Qtr':
                q3_aligned[col] = TARGET_QUARTER
            else:
                q3_aligned[col] = 0.0  # Default for numeric columns
    
    print(f"\nPrepared {len(q3_aligned):,} rows for Q3 2025")
    print(f"  Date range: {q3_aligned['WorkDate'].min()} to {q3_aligned['WorkDate'].max()}")
    
    # Combine with existing data
    combined_df = pd.concat([existing_df, q3_aligned], ignore_index=True)
    
    # Sort by date
    combined_df = combined_df.sort_values('WorkDate').reset_index(drop=True)
    
    print(f"\nCombined file will have {len(combined_df):,} rows")
    print(f"  Date range: {combined_df['WorkDate'].min()} to {combined_df['WorkDate'].max()}")
    
    # Save
    output_file = 'facility_335513_complete_data.csv'
    try:
        combined_df.to_csv(output_file, index=False)
        print(f"\n✓ Successfully updated {output_file}")
        print(f"  Added {len(q3_aligned):,} rows for Q3 2025")
    except Exception as e:
        print(f"\nERROR: Could not save file: {e}")
        print("  File may be open in another program. Please close it and try again.")

if __name__ == '__main__':
    main()
