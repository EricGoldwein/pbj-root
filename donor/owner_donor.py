# CMS Ownership → FEC Donation Linkage Script
# PURPOSE:
# Extract all nursing home owners from CMS data and query FEC API to find
# all political donations made by each owner. Creates a comprehensive database
# of owner-donation relationships.
#
# This script is designed to be auditable, deterministic, and defensible.

# ASSUMPTIONS:
# - You have CMS ownership CSV(s) with enrollment_id and owner fields
# - You have a valid FEC API key (set in fec_api_client.py or as environment variable)
# - The script queries FEC API for each unique owner

import pandas as pd
import re
import os
from pathlib import Path
from datetime import datetime
import time
import duckdb

# Import FEC API client
try:
    from fec_api_client import (
        query_donations_by_name,
        normalize_fec_donation,
        donations_to_dataframe
    )
except ImportError:
    print("ERROR: fec_api_client.py not found. Please ensure it's in the same directory.")
    raise

# ---------------------------
# CONFIG
# ---------------------------
# Paths relative to script location or workspace root
BASE_DIR = Path(__file__).parent.parent if Path(__file__).parent.name == "donor" else Path.cwd()

# Use SNF_All_Owners_Jan_2026.csv as specified
CMS_OWNERSHIP_PATH = BASE_DIR / "ownership" / "SNF_All_Owners_Jan_2026.csv"

# Allow override via environment variable if needed
env_file = os.getenv("CMS_OWNERSHIP_FILE")
if env_file:
    CMS_OWNERSHIP_PATH = Path(env_file)

# Filter options for testing/faster processing
FILTER_STATE = os.getenv("FILTER_STATE", "")  # e.g., "CA", "NY", "TX", "DE" - empty string = all states
FILTER_LIMIT = int(os.getenv("FILTER_LIMIT", "0"))  # Limit number of owners to process (0 = all)

# Mode: "extract" = just extract owners (FAST - no API calls), "query" = query FEC API for all owners (SLOW - takes hours)
# NOTE: For dashboard use, just run MODE=extract. The dashboard queries FEC API on-demand when you search.
MODE = os.getenv("MODE", "extract")  # "extract" (recommended) or "query" (only if you want to pre-process all donations)

# Output directory
OUTPUT_DIR = BASE_DIR / "donor" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_OWNERSHIP_NORM = OUTPUT_DIR / "ownership_normalized.csv"
OUT_OWNERS_DB = OUTPUT_DIR / "owners_database.csv"
OUT_DONATIONS_DB = OUTPUT_DIR / "owner_donations_database.csv"
OUT_SUMMARY = OUTPUT_DIR / "owner_donations_summary.csv"

# ---------------------------
# HELPERS
# ---------------------------

def normalize_name(s):
    if pd.isna(s):
        return None
    s = s.upper()
    s = re.sub(r"[^A-Z ]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

# ---------------------------
# LOAD DATA
# ---------------------------
print(f"Loading ownership data from: {CMS_OWNERSHIP_PATH}")
if not CMS_OWNERSHIP_PATH.exists():
    raise FileNotFoundError(f"Ownership file not found: {CMS_OWNERSHIP_PATH}")
# Try different encodings - CSV might be Windows-1252, Latin-1, or have BOM
encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
ownership = None

for encoding in encodings_to_try:
    try:
        ownership = pd.read_csv(CMS_OWNERSHIP_PATH, dtype=str, low_memory=False, encoding=encoding)
        print(f"Loaded {len(ownership)} ownership records (using {encoding} encoding)")
        break
    except UnicodeDecodeError:
        continue

if ownership is None:
    raise ValueError(f"Could not read CSV file with any encoding. Tried: {encodings_to_try}")

# Apply filters if specified
if FILTER_STATE:
    # Filter by state - check STATE - OWNER column
    if "STATE - OWNER" in ownership.columns:
        before = len(ownership)
        ownership = ownership[ownership["STATE - OWNER"].str.upper() == FILTER_STATE.upper()].copy()
        print(f"Filtered to state '{FILTER_STATE}': {len(ownership)} records (from {before})")
    else:
        print(f"Warning: STATE - OWNER column not found. Available columns: {list(ownership.columns)[:10]}")

if FILTER_LIMIT > 0:
    print(f"Limiting to first {FILTER_LIMIT} ownership records for testing")
    ownership = ownership.head(FILTER_LIMIT).copy()

# ---------------------------
# NORMALIZE CMS OWNERSHIP
# ---------------------------

# SNF_All_Owners format
ownership["owner_full_name"] = (
    ownership[["FIRST NAME - OWNER", "MIDDLE NAME - OWNER", "LAST NAME - OWNER"]]
    .fillna("")
    .agg(" ".join, axis=1)
    .apply(normalize_name)
)

ownership["owner_org_name"] = ownership["ORGANIZATION NAME - OWNER"].apply(normalize_name)
ownership["facility_name"] = ownership["ORGANIZATION NAME"].apply(normalize_name)

ownership["is_equity_owner"] = ownership["ROLE TEXT - OWNER"].str.contains("5%", na=False)
ownership["is_officer"] = ownership["ROLE TEXT - OWNER"].str.contains("OFFICER", na=False)

ownership["association_date"] = pd.to_datetime(
    ownership["ASSOCIATION DATE - OWNER"], errors="coerce"
)

# Keep ASSOCIATE ID - OWNER for proper matching back to original data
ownership_norm = (
    ownership
    .groupby([
        "ENROLLMENT ID",
        "ASSOCIATE ID - OWNER",  # Add this for proper matching
        "owner_full_name",
        "owner_org_name"
    ], dropna=False)
    .agg({
        "facility_name": "first",
        "association_date": "min",
        "is_equity_owner": "max",
        "is_officer": "max"
    })
    .reset_index()
)

ownership_norm.to_csv(OUT_OWNERSHIP_NORM, index=False)

# ---------------------------
# EXTRACT UNIQUE OWNERS
# ---------------------------

print("\nExtracting unique owners using DuckDB (FAST - SQL-based)...")

# Use DuckDB for fast SQL-based extraction (much faster than row-by-row pandas)
conn = duckdb.connect(':memory:')
conn.execute("PRAGMA threads=8")
conn.execute("PRAGMA memory_limit='8GB'")

print("Step 1: Loading data into DuckDB...")
# Register DataFrames with DuckDB
conn.register('ownership', ownership)
conn.register('ownership_norm', ownership_norm)

print("Step 2: Extracting unique individual owners (SQL query)...")
# Extract individual owners with SQL - aggregates everything in one query!
# Much faster than row-by-row pandas processing!
individuals_query = """
SELECT 
    norm.owner_full_name as owner_name,
    COALESCE(norm.owner_org_name, '') as owner_org_name,
    -- Get original name (use the FIRST matching row's original name)
    -- Since we're joining on ASSOCIATE ID - OWNER, this should be exact match
    COALESCE(
        MIN(TRIM(CONCAT(
            COALESCE(own."FIRST NAME - OWNER", ''),
            CASE WHEN own."MIDDLE NAME - OWNER" IS NOT NULL AND own."MIDDLE NAME - OWNER" != '' 
                 THEN ' ' || own."MIDDLE NAME - OWNER" ELSE '' END,
            CASE WHEN own."LAST NAME - OWNER" IS NOT NULL AND own."LAST NAME - OWNER" != '' 
                 THEN ' ' || own."LAST NAME - OWNER" ELSE '' END
        ))),
        norm.owner_full_name
    ) as owner_name_original,
    -- Aggregate facilities
    STRING_AGG(DISTINCT norm.facility_name, ', ') as facilities,
    STRING_AGG(DISTINCT norm."ENROLLMENT ID", ', ') as enrollment_ids,
    MAX(CASE WHEN norm.is_equity_owner THEN 1 ELSE 0 END) = 1 as is_equity_owner,
    MAX(CASE WHEN norm.is_officer THEN 1 ELSE 0 END) = 1 as is_officer,
    MIN(norm.association_date) as earliest_association
FROM ownership_norm norm
LEFT JOIN ownership own ON 
    norm."ENROLLMENT ID" = own."ENROLLMENT ID"
    AND norm."ASSOCIATE ID - OWNER" = own."ASSOCIATE ID - OWNER"
WHERE norm.owner_full_name IS NOT NULL AND norm.owner_full_name != ''
GROUP BY norm.owner_full_name, norm.owner_org_name
"""

individual_owners_df = conn.execute(individuals_query).df()
print(f"  ✓ Found {len(individual_owners_df)} unique individuals")

print("Step 3: Extracting unique organization owners (SQL query)...")
# Extract organization owners with SQL
orgs_query = """
SELECT 
    norm.owner_org_name as owner_name,
    '' as owner_org_name,
    -- Get original name (use first non-empty from ownership table)
    COALESCE(
        MIN(CASE 
            WHEN own."ORGANIZATION NAME - OWNER" IS NOT NULL AND own."ORGANIZATION NAME - OWNER" != ''
            THEN own."ORGANIZATION NAME - OWNER"
            ELSE NULL
        END),
        norm.owner_org_name
    ) as owner_name_original,
    -- Aggregate facilities
    STRING_AGG(DISTINCT norm.facility_name, ', ') as facilities,
    STRING_AGG(DISTINCT norm."ENROLLMENT ID", ', ') as enrollment_ids,
    false as is_equity_owner,
    false as is_officer,
    MIN(norm.association_date) as earliest_association
FROM ownership_norm norm
LEFT JOIN ownership own ON 
    norm."ENROLLMENT ID" = own."ENROLLMENT ID"
    AND norm."ASSOCIATE ID - OWNER" = own."ASSOCIATE ID - OWNER"
WHERE norm.owner_org_name IS NOT NULL AND norm.owner_org_name != ''
GROUP BY norm.owner_org_name
"""

org_owners_df = conn.execute(orgs_query).df()
print(f"  ✓ Found {len(org_owners_df)} unique organizations")

print("Step 4: Combining and deduplicating...")
# Combine and add owner_type
individual_owners_df['owner_type'] = 'INDIVIDUAL'
org_owners_df['owner_type'] = 'ORGANIZATION'

# Combine
owners_df = pd.concat([individual_owners_df, org_owners_df], ignore_index=True)

# Remove duplicates
owners_df = owners_df.drop_duplicates(subset=['owner_name', 'owner_type'])

# Reorder columns to match expected format
column_order = ['owner_name', 'owner_name_original', 'owner_type', 'owner_org_name', 
                'facilities', 'enrollment_ids', 'is_equity_owner', 'is_officer', 'earliest_association']
owners_df = owners_df[[col for col in column_order if col in owners_df.columns]]

# Convert boolean columns to proper format
if 'is_equity_owner' in owners_df.columns:
    owners_df['is_equity_owner'] = owners_df['is_equity_owner'].astype(bool)
if 'is_officer' in owners_df.columns:
    owners_df['is_officer'] = owners_df['is_officer'].astype(bool)

print(f"\n✓ Found {len(owners_df)} unique owners:")
print(f"  - {len(owners_df[owners_df['owner_type'] == 'INDIVIDUAL'])} individuals")
print(f"  - {len(owners_df[owners_df['owner_type'] == 'ORGANIZATION'])} organizations")

# Apply owner limit if specified (for testing)
if FILTER_LIMIT > 0 and len(owners_df) > FILTER_LIMIT:
    print(f"\nLimiting to first {FILTER_LIMIT} owners for testing")
    owners_df = owners_df.head(FILTER_LIMIT).copy()

# Save owners database
print("Step 5: Saving to file...")
owners_df.to_csv(OUT_OWNERS_DB, index=False)
print(f"\n✓ [OK] Owners database saved to: {OUT_OWNERS_DB}")

# If mode is "extract" only, stop here (RECOMMENDED - fast!)
if MODE.lower() == "extract":
    print("\n" + "="*60)
    print("✓ Extraction complete! Owners saved to database.")
    print(f"✓ Found {len(owners_df)} unique owners ready for search.")
    print("\n💡 Next steps:")
    print("   1. Start the dashboard: python donor/owner_donor_dashboard.py")
    print("   2. Search for owners in the web interface")
    print("   3. Click 'Query FEC API (Live)' to get donations on-demand")
    print("\n⚠️  NOTE: Don't run MODE=query unless you want to pre-process")
    print("   donations for ALL owners (takes hours). The dashboard queries")
    print("   the FEC API on-demand when you search, which is much faster!")
    print("="*60)
    exit(0)

# If mode is "query" only, load from saved file
if MODE.lower() == "query":
    print(f"\nLoading owners from: {OUT_OWNERS_DB}")
    if not OUT_OWNERS_DB.exists():
        raise FileNotFoundError(f"Owners database not found: {OUT_OWNERS_DB}\nRun with MODE=extract first.")
    owners_df = pd.read_csv(OUT_OWNERS_DB, dtype=str)
    print(f"Loaded {len(owners_df)} owners from database")

# ---------------------------
# QUERY FEC API FOR EACH OWNER
# ---------------------------

print("\n" + "="*60)
print("⚠️  WARNING: Querying FEC API for ALL owners...")
print("="*60)
print(f"This will query the FEC API for {len(owners_df)} owners.")
print("This will take MANY HOURS due to rate limiting!")
print("\n💡 RECOMMENDED: Stop this (Ctrl+C) and use the dashboard instead:")
print("   1. Run: python donor/owner_donor_dashboard.py")
print("   2. Search for owners in the web interface")
print("   3. Click 'Query FEC API (Live)' button to query on-demand")
print("\nThe dashboard queries the FEC API only when you search for a specific")
print("owner, which is much faster than pre-processing all owners!")
print("\nIf you really want to pre-process all donations, continue...")
print("The script will process owners one at a time with rate limiting.\n")

all_donations = []
processed_count = 0
skipped_count = 0
error_count = 0

# Check if API key is set before starting
import os
try:
    import fec_api_client
    # Check environment variable directly (most reliable)
    env_key = os.getenv("FEC_API_KEY", "").strip()
    
    if env_key:
        # Force update the module's API key from environment
        fec_api_client.FEC_API_KEY = env_key
        print(f"\n[OK] FEC API key found in environment variable")
    elif fec_api_client.FEC_API_KEY != "YOUR_API_KEY_HERE":
        print(f"\n[OK] FEC API key found in fec_api_client.py")
    else:
        print("\n⚠️  WARNING: FEC API key not set!")
        print("   Set it with: $env:FEC_API_KEY = 'your_key_here'")
        print("   Or edit fec_api_client.py line 27")
        print("\n   Continuing anyway to show what would be queried...\n")
except ImportError:
    print("ERROR: Could not import fec_api_client")
    raise

for idx, owner in owners_df.iterrows():
    owner_name = str(owner["owner_name"])
    owner_name_original = str(owner["owner_name_original"])
    owner_type = str(owner["owner_type"])
    
    # Determine FEC API contributor type
    fec_contributor_type = "IND" if owner_type == "INDIVIDUAL" else "ORG"
    
    print(f"\n[{processed_count + skipped_count + error_count + 1}/{len(owners_df)}] Owner: {owner_name_original}")
    print(f"    Type: {owner_type}")
    print(f"    Normalized name for search: '{owner_name}'")
    print(f"    Facilities: {len(str(owner['facilities']).split(', '))} facility(ies)")
    print(f"    Querying FEC API...", end=" ")
    
    try:
        # Try multiple name variations for better matching
        name_variations = [owner_name]
        
        # For individuals, also try last name only and different formats
        if owner_type == "INDIVIDUAL":
            name_parts = owner_name.split()
            if len(name_parts) >= 2:
                # Try last name only
                name_variations.append(name_parts[-1])
                # Try "First Last" format (if we have middle initial)
                if len(name_parts) == 3:
                    name_variations.append(f"{name_parts[0]} {name_parts[2]}")
        
        # Try original name as well
        if owner_name_original and owner_name_original != owner_name:
            name_variations.append(owner_name_original)
        
        # Remove duplicates while preserving order
        seen = set()
        name_variations = [x for x in name_variations if not (x in seen or seen.add(x))]
        
        all_donations_for_owner = []
        for name_var in name_variations:
            # Query FEC API with this name variation
            donations = query_donations_by_name(
                contributor_name=name_var,
                contributor_type=fec_contributor_type,
                per_page=100
            )
            if donations:
                all_donations_for_owner.extend(donations)
        
        # Remove duplicates based on sub_id (FEC record ID)
        if all_donations_for_owner:
            seen_ids = set()
            unique_donations = []
            for d in all_donations_for_owner:
                record_id = d.get("sub_id")
                if record_id and record_id not in seen_ids:
                    seen_ids.add(record_id)
                    unique_donations.append(d)
            donations = unique_donations
        else:
            donations = []
        
        if donations:
            print(f"[FOUND] Found {len(donations)} donation(s)")
            
            # Normalize and add owner context
            for donation in donations:
                normalized = normalize_fec_donation(donation)
                normalized["owner_name"] = owner_name
                normalized["owner_name_original"] = owner_name_original
                normalized["owner_type"] = owner_type
                normalized["owner_facilities"] = str(owner["facilities"])
                normalized["owner_enrollment_ids"] = str(owner["enrollment_ids"])
                normalized["owner_is_equity"] = owner["is_equity_owner"]
                normalized["owner_is_officer"] = owner["is_officer"]
                normalized["owner_association_date"] = owner["earliest_association"]
                all_donations.append(normalized)
            
            # Show sample of what was found
            if len(donations) > 0:
                sample = donations[0]
                committee = sample.get("committee", {}).get("name", "Unknown")
                amount = sample.get("contribution_receipt_amount", 0)
                date = sample.get("contribution_receipt_date", "Unknown")
                print(f"    Sample: ${amount:,.2f} to {committee} on {date}")
        else:
            print("[NONE] No donations found")
            skipped_count += 1
        
        processed_count += 1
        
    except ValueError as e:
        # API key error
        if "API key" in str(e):
            print(f"[ERROR] {str(e)}")
            print(f"    Skipping remaining owners. Please set FEC_API_KEY and run again.")
            error_count += 1
            break
        else:
            print(f"[ERROR] {str(e)}")
            error_count += 1
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {str(e)}")
        error_count += 1
        continue

# ---------------------------
# SAVE DONATIONS DATABASE
# ---------------------------

if all_donations:
    donations_df = pd.DataFrame(all_donations)
    donations_df.to_csv(OUT_DONATIONS_DB, index=False)
    
    # Create summary
    summary = donations_df.groupby(["owner_name", "owner_type"]).agg({
        "donation_amount": ["count", "sum", "mean", "min", "max"],
        "committee_name": lambda x: ", ".join(x.unique()[:5]),  # First 5 committees
        "candidate_name": lambda x: ", ".join([str(v) for v in x.dropna().unique()[:5]])  # First 5 candidates
    }).reset_index()
    
    summary.columns = [
        "owner_name", "owner_type", "donation_count", "total_donated", 
        "avg_donation", "min_donation", "max_donation", "committees", "candidates"
    ]
    
    summary = summary.sort_values("total_donated", ascending=False)
    summary.to_csv(OUT_SUMMARY, index=False)
    
    print("\n" + "="*60)
    print("Processing complete!")
    print("="*60)
    print(f"Total owners in database: {len(owners_df)}")
    print(f"  - Successfully queried: {processed_count}")
    print(f"  - No donations found: {skipped_count}")
    print(f"  - Errors: {error_count}")
    print(f"\nTotal donations found: {len(donations_df)}")
    if len(donations_df) > 0:
        print(f"Total amount donated: ${donations_df['donation_amount'].sum():,.2f}")
        print(f"Date range: {donations_df['donation_date'].min()} to {donations_df['donation_date'].max()}")
        print(f"\nTop recipients:")
        top_committees = donations_df.groupby('committee_name')['donation_amount'].sum().sort_values(ascending=False).head(5)
        for committee, amount in top_committees.items():
            if pd.notna(committee) and committee:
                print(f"  - {committee}: ${amount:,.2f}")
    print(f"\nOutputs written:")
    print(f"  - {OUT_OWNERSHIP_NORM}")
    print(f"  - {OUT_OWNERS_DB}")
    print(f"  - {OUT_DONATIONS_DB}")
    print(f"  - {OUT_SUMMARY}")
    print("="*60)
else:
    print("\n" + "="*60)
    print("Processing complete!")
    print("="*60)
    print(f"Total owners in database: {len(owners_df)}")
    print(f"  - Successfully queried: {processed_count}")
    print(f"  - No donations found: {skipped_count}")
    print(f"  - Errors: {error_count}")
    print(f"\nNo donations found for any owners.")
    if error_count > 0:
        print(f"\n⚠️  {error_count} error(s) occurred. Check messages above.")
    print(f"\nOutputs written:")
    print(f"  - {OUT_OWNERSHIP_NORM}")
    print(f"  - {OUT_OWNERS_DB}")
    print("="*60)
