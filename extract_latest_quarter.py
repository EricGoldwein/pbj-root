#!/usr/bin/env python3
"""
Extract only the most recent quarter's data from large CSV files
to create smaller files for deployment.
Finds the most recent quarter that exists in ALL files (state, provider, facility).
"""

import pandas as pd
import os
import re

def find_most_recent_common_quarter():
    """
    Find the most recent quarter that exists in ALL three files:
    - state_quarterly_metrics.csv
    - provider_info_combined.csv  
    - facility_quarterly_metrics.csv
    Returns the quarter in state format (e.g., "2025Q2")
    """
    print("\nFinding most recent quarter available in ALL files...")
    
    # Get quarters from state data (format: "2025Q2")
    state_df = pd.read_csv('state_quarterly_metrics.csv')
    state_quarters = set(state_df['CY_Qtr'].unique())
    print(f"State data latest: {state_df['CY_Qtr'].max()}")
    
    # Get quarters from facility data (format: "2025Q2")
    facility_df = pd.read_csv('facility_quarterly_metrics.csv', usecols=['CY_Qtr'], low_memory=False)
    facility_quarters = set(facility_df['CY_Qtr'].unique())
    print(f"Facility data latest: {facility_df['CY_Qtr'].max()}")
    
    # Get quarters from provider data (format: "Q2 2025")
    print("Reading provider_info_combined.csv to find available quarters...")
    provider_quarters = set()
    for chunk in pd.read_csv('provider_info_combined.csv', usecols=['quarter'], chunksize=50000, low_memory=False):
        valid_quarters = [q for q in chunk['quarter'].dropna().unique() if isinstance(q, str)]
        provider_quarters.update(valid_quarters)
    
    # Convert provider format to state format for comparison
    def convert_provider_to_state(provider_q):
        """Convert 'Q2 2025' to '2025Q2'"""
        if not isinstance(provider_q, str):
            return None
        # Try "Q2 2025" format
        match = re.match(r'Q(\d)\s+(\d{4})', provider_q)
        if match:
            return f"{match.group(2)}Q{match.group(1)}"
        # Try "2025Q2" format (already in state format)
        match = re.match(r'(\d{4})Q(\d)', provider_q)
        if match:
            return provider_q
        return None
    
    # Convert provider quarters to state format
    provider_quarters_state = set()
    for provider_q in provider_quarters:
        state_q = convert_provider_to_state(provider_q)
        if state_q:
            provider_quarters_state.add(state_q)
    
    print(f"Provider data latest (converted): {sorted(provider_quarters_state)[-1] if provider_quarters_state else 'N/A'}")
    
    # Find quarters that exist in ALL three files
    common_quarters = state_quarters & facility_quarters & provider_quarters_state
    
    if not common_quarters:
        print("WARNING: No common quarters found in all three files!")
        # Try just state and provider
        common_quarters = state_quarters & provider_quarters_state
        if not common_quarters:
            print("Falling back to state data's most recent quarter")
            return state_df['CY_Qtr'].max()
        print("Using state + provider common quarters (facility may be outdated)")
    
    # Sort and get most recent
    most_recent = sorted(common_quarters)[-1]
    print(f"\nMost recent common quarter (all files): {most_recent}")
    return most_recent

def extract_facility_quarterly_latest(target_quarter):
    """Extract specified quarter from facility_quarterly_metrics.csv"""
    print(f"\nExtracting {target_quarter} from facility_quarterly_metrics.csv...")
    df = pd.read_csv('facility_quarterly_metrics.csv', low_memory=False)
    
    # Check if target quarter exists
    available_quarters = df['CY_Qtr'].unique()
    if target_quarter not in available_quarters:
        print(f"WARNING: {target_quarter} not found in facility_quarterly_metrics.csv")
        print(f"Available quarters: {sorted(available_quarters)[-5:]}")
        # Use most recent available
        target_quarter = df['CY_Qtr'].max()
        print(f"Using most recent available: {target_quarter}")
    
    # Filter to target quarter
    df_latest = df[df['CY_Qtr'] == target_quarter].copy()
    
    print(f"Original rows: {len(df):,}")
    print(f"Latest quarter rows: {len(df_latest):,}")
    
    # Save
    output_file = 'facility_quarterly_metrics_latest.csv'
    df_latest.to_csv(output_file, index=False)
    
    print(f"Saved to {output_file}")
    print(f"Size reduction: {len(df_latest)/len(df)*100:.1f}% of original")
    return target_quarter

def extract_provider_info_latest(target_quarter_state_format):
    """
    Extract most recent quarter from provider_info_combined.csv
    Writes in chunks to avoid disk space issues
    target_quarter_state_format: e.g., "2025Q2" (state format)
    Need to match to provider format: "Q2 2025"
    """
    print(f"\nExtracting {target_quarter_state_format} from provider_info_combined.csv...")
    
    # Parse target quarter
    year = target_quarter_state_format[:4]
    quarter_num = target_quarter_state_format[5]
    provider_format = f"Q{quarter_num} {year}"
    
    print(f"Looking for quarter: {provider_format} (provider format)")
    print(f"Or: {target_quarter_state_format} (state format)")
    
    output_file = 'provider_info_combined_latest.csv'
    temp_file = 'provider_info_combined_latest_temp.csv'
    
    # Remove temp file if it exists
    if os.path.exists(temp_file):
        os.remove(temp_file)
    
    # Read header first
    header_df = pd.read_csv('provider_info_combined.csv', nrows=1)
    
    # Read in chunks and write directly to avoid memory issues
    chunk_size = 50000
    total_rows = 0
    matched_rows = 0
    first_chunk = True
    
    print("Processing in chunks and writing directly to file...")
    for chunk in pd.read_csv('provider_info_combined.csv', chunksize=chunk_size, low_memory=False):
        total_rows += len(chunk)
        
        # Try both formats
        mask = (
            (chunk['quarter'] == provider_format) |
            (chunk['quarter'] == target_quarter_state_format) |
            (chunk['quarter'].str.contains(f"Q{quarter_num}.*{year}", na=False, regex=True))
        )
        
        matched_chunk = chunk[mask].copy()
        if len(matched_chunk) > 0:
            matched_rows += len(matched_chunk)
            # Write chunk directly to file (append mode)
            matched_chunk.to_csv(temp_file, mode='a', header=first_chunk, index=False)
            first_chunk = False
            print(f"  Found {len(matched_chunk):,} rows in chunk (total matched: {matched_rows:,})")
    
    if matched_rows == 0:
        print("WARNING: No matching quarter found in provider_info_combined.csv")
        print("Creating empty file with headers")
        header_df.to_csv(output_file, index=False)
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return
    
    # Rename temp file to final file
    if os.path.exists(temp_file):
        if os.path.exists(output_file):
            os.remove(output_file)
        os.rename(temp_file, output_file)
    
    print(f"\nOriginal rows (approx): {total_rows:,}")
    print(f"Latest quarter rows: {matched_rows:,}")
    print(f"Saved to {output_file}")
    print(f"Size reduction: {matched_rows/total_rows*100:.1f}% of original")

if __name__ == '__main__':
    # Find most recent quarter that exists in ALL files
    most_recent_quarter = find_most_recent_common_quarter()
    
    print(f"\nUsing quarter for all files: {most_recent_quarter}")
    
    # Extract facility data for the most recent common quarter
    extract_facility_quarterly_latest(most_recent_quarter)
    
    # Extract provider info for the most recent common quarter
    extract_provider_info_latest(most_recent_quarter)
    
    print("\nDone! Created:")
    print("  - facility_quarterly_metrics_latest.csv")
    print("  - provider_info_combined_latest.csv")
    print(f"\nBoth files now contain data for: {most_recent_quarter}")
    print("You can now use these files instead of the full datasets.")
