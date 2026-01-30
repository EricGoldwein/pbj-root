#!/usr/bin/env python3
"""
Update facility_335513_complete_data.csv and facility_335513_provider_info_data.csv with Q3 2025 data

This script extracts Q3 2025 data from provider_info_combined.csv and updates the Seagate facility files.
"""

import pandas as pd
import os
from datetime import datetime, timedelta

FACILITY_NUM = '335513'
TARGET_QUARTER = '2025Q3'
Q3_START_DATE = 20250701  # July 1, 2025
Q3_END_DATE = 20250930    # September 30, 2025

def update_provider_info():
    """Update facility_335513_provider_info_data.csv with Q3 2025 entries"""
    print("=" * 80)
    print("Updating facility_335513_provider_info_data.csv")
    print("=" * 80)
    
    # Load existing file
    existing_file = 'facility_335513_provider_info_data.csv'
    if not os.path.exists(existing_file):
        print(f"ERROR: {existing_file} not found")
        return False
    
    existing_df = pd.read_csv(existing_file)
    print(f"Loaded existing file: {len(existing_df):,} rows")
    print(f"  Last processing_date: {existing_df['processing_date'].max()}")
    
    # Load provider_info_combined.csv and filter for facility 335513, Q3 2025
    print("\nLoading provider_info_combined.csv...")
    try:
        # Read in chunks to handle large file
        chunks = []
        chunk_size = 100000
        total_rows = 0
        
        for chunk in pd.read_csv('provider_info_combined.csv', chunksize=chunk_size, low_memory=False):
            total_rows += len(chunk)
            # Filter for facility 335513
            chunk['ccn'] = chunk['ccn'].astype(str).str.strip()
            facility_chunk = chunk[chunk['ccn'] == FACILITY_NUM]
            
            if len(facility_chunk) > 0:
                # Filter for Q3 2025
                q3_chunk = facility_chunk[
                    facility_chunk['quarter'].astype(str).str.contains('Q3.*2025', case=False, na=False, regex=True)
                ]
                if len(q3_chunk) > 0:
                    chunks.append(q3_chunk)
                    print(f"  Found {len(q3_chunk):,} Q3 2025 rows in chunk")
        
        if not chunks:
            print("  WARNING: No Q3 2025 data found in provider_info_combined.csv for facility 335513")
            print("  You may need to add Q3 2025 data to provider_info_combined.csv first")
            return False
        
        q3_df = pd.concat(chunks, ignore_index=True)
        print(f"\nExtracted {len(q3_df):,} Q3 2025 rows from provider_info_combined.csv")
        
        # Get unique months (July, August, September 2025)
        q3_df['processing_date'] = pd.to_datetime(q3_df['processing_date'], errors='coerce')
        q3_df = q3_df.sort_values('processing_date')
        
        # Group by month and take the latest entry for each month
        q3_df['month'] = q3_df['processing_date'].dt.to_period('M')
        monthly_entries = q3_df.groupby('month').last().reset_index()
        
        print(f"  Found {len(monthly_entries):,} unique months in Q3 2025")
        
        # Map columns to match existing file format
        # Get column mapping
        existing_cols = list(existing_df.columns)
        q3_cols = list(q3_df.columns)
        
        # Create new rows matching existing format
        new_rows = []
        for _, row in monthly_entries.iterrows():
            new_row = {}
            for col in existing_cols:
                # Map columns
                if col == 'ccn':
                    new_row[col] = FACILITY_NUM
                elif col == 'quarter':
                    new_row[col] = TARGET_QUARTER
                elif col in q3_cols:
                    new_row[col] = row[col]
                elif col == 'processing_date':
                    # Use the date from the row
                    new_row[col] = row['processing_date'].strftime('%Y-%m-%d') if pd.notna(row['processing_date']) else None
                else:
                    # Try to find similar column name
                    found = False
                    for q3_col in q3_cols:
                        if col.lower() == q3_col.lower() or col.lower().replace('_', '') == q3_col.lower().replace('_', ''):
                            new_row[col] = row[q3_col]
                            found = True
                            break
                    if not found:
                        new_row[col] = None
            
            new_rows.append(new_row)
        
        if not new_rows:
            print("  WARNING: Could not create new rows - column mapping issue")
            return False
        
        new_df = pd.DataFrame(new_rows)
        print(f"\nCreated {len(new_df):,} new rows for Q3 2025")
        
        # Combine with existing
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        combined_df = combined_df.sort_values('processing_date').reset_index(drop=True)
        
        # Save
        try:
            combined_df.to_csv(existing_file, index=False)
            print(f"\n✓ Successfully updated {existing_file}")
            print(f"  Added {len(new_df):,} rows for Q3 2025")
            print(f"  Total rows: {len(combined_df):,}")
            return True
        except Exception as e:
            print(f"\nERROR: Could not save file: {e}")
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_complete_data():
    """Update facility_335513_complete_data.csv with Q3 2025 daily data"""
    print("\n" + "=" * 80)
    print("Updating facility_335513_complete_data.csv")
    print("=" * 80)
    print("\nNOTE: This requires daily-level PBJ source data files from CMS.")
    print("The daily data file (facility_335513_complete_data.csv) contains one row per day.")
    print("To update it, you need to:")
    print("  1. Download Q3 2025 PBJ daily data from CMS")
    print("  2. Extract rows for facility 335513")
    print("  3. Run: python extract_seagate_q3_data.py <source_daily_file.csv>")
    print("\nAlternatively, if you have the daily data in another format,")
    print("you can manually append Q3 2025 rows (July 1 - September 30, 2025) to the file.")
    print("\nThe file currently ends at 2025-06-30 and needs data through 2025-09-30.")
    
    # Check current state
    existing_file = 'facility_335513_complete_data.csv'
    if os.path.exists(existing_file):
        df = pd.read_csv(existing_file)
        print(f"\nCurrent file status:")
        print(f"  Total rows: {len(df):,}")
        print(f"  Last date: {df['WorkDate'].max()}")
        print(f"  Last quarter: {df['CY_Qtr'].iloc[-1] if len(df) > 0 else 'N/A'}")
        print(f"  Needs: Q3 2025 data (2025-07-01 through 2025-09-30)")

def main():
    print("=" * 80)
    print("Update Seagate Facility Files with Q3 2025 Data")
    print("=" * 80)
    print()
    
    # Update provider info file
    provider_success = update_provider_info()
    
    # Note about daily data file
    update_complete_data()
    
    print("\n" + "=" * 80)
    if provider_success:
        print("SUMMARY:")
        print("  SUCCESS: Updated facility_335513_provider_info_data.csv with Q3 2025 data")
        print("  NOTE: facility_335513_complete_data.csv requires daily source data")
    else:
        print("SUMMARY:")
        print("  WARNING: Could not update provider info - check if Q3 2025 data exists in provider_info_combined.csv")
        print("  WARNING: facility_335513_complete_data.csv requires daily source data")
    print("=" * 80)

if __name__ == '__main__':
    main()
