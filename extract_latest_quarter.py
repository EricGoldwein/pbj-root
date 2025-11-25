#!/usr/bin/env python3
"""
Extract only the most recent quarter's data from large CSV files
to create smaller files for deployment.
"""

import pandas as pd
import sys

def extract_facility_quarterly_latest():
    """Extract most recent quarter from facility_quarterly_metrics.csv"""
    print("Reading facility_quarterly_metrics.csv...")
    df = pd.read_csv('facility_quarterly_metrics.csv')
    
    # Find most recent quarter
    most_recent = df['CY_Qtr'].max()
    print(f"Most recent quarter: {most_recent}")
    
    # Filter to most recent quarter
    df_latest = df[df['CY_Qtr'] == most_recent].copy()
    
    print(f"Original rows: {len(df):,}")
    print(f"Latest quarter rows: {len(df_latest):,}")
    
    # Save
    output_file = 'facility_quarterly_metrics_latest.csv'
    df_latest.to_csv(output_file, index=False)
    
    original_size = pd.read_csv('facility_quarterly_metrics.csv', nrows=1).memory_usage(deep=True).sum() * len(df) / 1024 / 1024
    new_size = len(df_latest) * df_latest.memory_usage(deep=True).sum() / 1024 / 1024
    
    print(f"Saved to {output_file}")
    print(f"Size reduction: {len(df_latest)/len(df)*100:.1f}% of original")
    return most_recent

def extract_provider_info_latest(target_quarter_state_format):
    """
    Extract most recent quarter from provider_info_combined.csv
    target_quarter_state_format: e.g., "2025Q2" (state format)
    Need to match to provider format: "Q2 2025"
    """
    print("\nReading provider_info_combined.csv...")
    
    # Parse target quarter
    # State format: "2025Q2" -> Provider format: "Q2 2025"
    year = target_quarter_state_format[:4]
    quarter_num = target_quarter_state_format[5]
    provider_format = f"Q{quarter_num} {year}"
    
    print(f"Looking for quarter: {provider_format} (provider format)")
    print(f"Or: {target_quarter_state_format} (state format)")
    
    # Read in chunks to handle large file
    chunks = []
    chunk_size = 50000
    total_rows = 0
    matched_rows = 0
    
    for chunk in pd.read_csv('provider_info_combined.csv', chunksize=chunk_size):
        total_rows += len(chunk)
        
        # Try both formats
        mask = (
            (chunk['quarter'] == provider_format) |
            (chunk['quarter'] == target_quarter_state_format) |
            (chunk['quarter'].str.contains(f"Q{quarter_num}.*{year}", na=False, regex=True))
        )
        
        matched_chunk = chunk[mask].copy()
        if len(matched_chunk) > 0:
            chunks.append(matched_chunk)
            matched_rows += len(matched_chunk)
            print(f"  Found {len(matched_chunk):,} rows in chunk (total matched: {matched_rows:,})")
    
    if not chunks:
        print("WARNING: No matching quarter found in provider_info_combined.csv")
        print("This might mean the quarter column uses a different format")
        print("Creating empty file - you may need to manually filter")
        pd.DataFrame(columns=pd.read_csv('provider_info_combined.csv', nrows=1).columns).to_csv('provider_info_combined_latest.csv', index=False)
        return
    
    # Combine chunks
    df_latest = pd.concat(chunks, ignore_index=True)
    
    print(f"\nOriginal rows (approx): {total_rows:,}")
    print(f"Latest quarter rows: {len(df_latest):,}")
    
    # Save
    output_file = 'provider_info_combined_latest.csv'
    df_latest.to_csv(output_file, index=False)
    
    print(f"Saved to {output_file}")
    print(f"Size reduction: {len(df_latest)/total_rows*100:.1f}% of original")

if __name__ == '__main__':
    # Get most recent quarter from facility data (which has fewer quarters)
    most_recent = extract_facility_quarterly_latest()
    
    # Use state data's most recent quarter for provider info (since it's more up-to-date)
    state_df = pd.read_csv('state_quarterly_metrics.csv')
    state_most_recent = state_df['CY_Qtr'].max()
    print(f"\nState data most recent quarter: {state_most_recent}")
    
    # Extract provider info for the most recent quarter
    extract_provider_info_latest(state_most_recent)
    
    print("\nDone! Created:")
    print("  - facility_quarterly_metrics_latest.csv")
    print("  - provider_info_combined_latest.csv")
    print("\nYou can now use these files instead of the full datasets.")

