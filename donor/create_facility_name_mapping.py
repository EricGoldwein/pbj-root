"""
Create a mapping file that joins Legal Business Name (provider_info) with ORGANIZATION NAME (ownership)
This speeds up facility matching in the dashboard.
"""

import pandas as pd
from pathlib import Path
import sys

BASE_DIR = Path(__file__).parent.parent

# Paths
PROVIDER_INFO_LATEST = BASE_DIR / "provider_info" / "NH_ProviderInfo_Jan2026.csv"
OWNERSHIP_FILE = BASE_DIR / "ownership" / "SNF_All_Owners_Jan_2026.csv"
OUTPUT_MAPPING = BASE_DIR / "donor" / "output" / "facility_name_mapping.csv"

def normalize_name(name):
    """Normalize name for matching"""
    if pd.isna(name) or not name:
        return ""
    return str(name).upper().strip()

def create_facility_mapping():
    """Create mapping between Legal Business Name and ORGANIZATION NAME"""
    print("="*60)
    print("Creating Facility Name Mapping")
    print("="*60)
    
    # Load provider info
    if not PROVIDER_INFO_LATEST.exists():
        print(f"❌ Provider info file not found: {PROVIDER_INFO_LATEST}")
        return False
    
    print(f"Loading provider info: {PROVIDER_INFO_LATEST}")
    try:
        provider_df = pd.read_csv(PROVIDER_INFO_LATEST, dtype=str, low_memory=False, encoding='utf-8')
    except UnicodeDecodeError:
        # Try with different encodings if UTF-8 fails
        try:
            provider_df = pd.read_csv(PROVIDER_INFO_LATEST, dtype=str, low_memory=False, encoding='utf-8-sig')
        except UnicodeDecodeError:
            provider_df = pd.read_csv(PROVIDER_INFO_LATEST, dtype=str, low_memory=False, encoding='latin-1')
    print(f"✓ Loaded {len(provider_df)} provider records")
    
    # Check for Legal Business Name column
    if 'Legal Business Name' not in provider_df.columns:
        print("❌ 'Legal Business Name' column not found in provider info")
        print(f"Available columns: {[c for c in provider_df.columns if 'legal' in c.lower() or 'business' in c.lower()]}")
        return False
    
    # Load ownership file
    if not OWNERSHIP_FILE.exists():
        print(f"❌ Ownership file not found: {OWNERSHIP_FILE}")
        return False
    
    print(f"Loading ownership file: {OWNERSHIP_FILE}")
    try:
        ownership_df = pd.read_csv(OWNERSHIP_FILE, dtype=str, low_memory=False, nrows=None, encoding='utf-8')
    except UnicodeDecodeError:
        # Try with different encodings if UTF-8 fails
        try:
            ownership_df = pd.read_csv(OWNERSHIP_FILE, dtype=str, low_memory=False, nrows=None, encoding='utf-8-sig')
        except UnicodeDecodeError:
            # Try Windows-1252 or Latin-1 for Windows CSV files
            try:
                ownership_df = pd.read_csv(OWNERSHIP_FILE, dtype=str, low_memory=False, nrows=None, encoding='cp1252')
            except UnicodeDecodeError:
                ownership_df = pd.read_csv(OWNERSHIP_FILE, dtype=str, low_memory=False, nrows=None, encoding='latin-1')
    print(f"✓ Loaded {len(ownership_df)} ownership records")
    
    # Extract unique ORGANIZATION NAME values
    print("\nExtracting unique ORGANIZATION NAME values from ownership file...")
    org_names = ownership_df['ORGANIZATION NAME'].dropna().unique()
    print(f"✓ Found {len(org_names)} unique organization names")
    
    # Create normalized versions for matching
    provider_df['legal_business_name_norm'] = provider_df['Legal Business Name'].apply(normalize_name)
    org_names_df = pd.DataFrame({
        'ORGANIZATION NAME': org_names,
        'org_name_norm': [normalize_name(n) for n in org_names]
    })
    
    # Match Legal Business Name to ORGANIZATION NAME
    print("\nMatching Legal Business Name to ORGANIZATION NAME...")
    matches = []
    
    # Get CCN column name
    ccn_col = 'CMS Certification Number (CCN)' if 'CMS Certification Number (CCN)' in provider_df.columns else 'ccn'
    
    for _, org_row in org_names_df.iterrows():
        org_name = org_row['ORGANIZATION NAME']
        org_name_norm = org_row['org_name_norm']
        
        if not org_name_norm:
            continue
        
        # Try exact match
        matched = provider_df[provider_df['legal_business_name_norm'] == org_name_norm]
        
        if matched.empty:
            # Try partial match (remove common suffixes)
            org_clean = org_name_norm.replace(' LLC', '').replace(' INC', '').replace(' CORP', '').replace(' LP', '').replace(' L.L.C.', '').replace(' INC.', '').strip()
            matched = provider_df[
                provider_df['legal_business_name_norm'].str.replace(' LLC', '').str.replace(' INC', '').str.replace(' CORP', '').str.replace(' LP', '').str.replace(' L.L.C.', '').str.replace(' INC.', '').str.strip() == org_clean
            ]
        
        # Try fuzzy matching - remove punctuation and extra spaces
        if matched.empty:
            # Normalize both sides: remove commas, periods, hyphens, normalize spaces (multiple passes)
            org_fuzzy = org_name_norm.replace(',', '').replace('.', '').replace('-', ' ').replace('  ', ' ').replace('  ', ' ').strip()
            matched = provider_df[
                provider_df['legal_business_name_norm'].str.replace(',', '').str.replace('.', '').str.replace('-', ' ').str.replace('  ', ' ').str.replace('  ', ' ').str.strip() == org_fuzzy
            ]
        
        # Try contains match (if still empty) - match first 15 characters
        if matched.empty and len(org_name_norm) > 10:
            name_prefix = org_name_norm[:15]
            matched = provider_df[
                provider_df['legal_business_name_norm'].str[:15] == name_prefix
            ]
        
        if not matched.empty:
            # Take first match
            prov_row = matched.iloc[0]
            matches.append({
                'ORGANIZATION NAME': org_name,
                'Legal Business Name': prov_row['Legal Business Name'],
                'CCN': prov_row.get(ccn_col, ''),
                'Provider Name': prov_row.get('Provider Name', ''),
                'State': prov_row.get('State', ''),
                'City/Town': prov_row.get('City/Town', ''),
                'Chain ID': prov_row.get('Chain ID', ''),
                'Chain Name': prov_row.get('Chain Name', '')
            })
    
    # Create mapping DataFrame
    mapping_df = pd.DataFrame(matches)
    print(f"✓ Created {len(mapping_df)} matches")
    
    # Save mapping
    OUTPUT_MAPPING.parent.mkdir(parents=True, exist_ok=True)
    mapping_df.to_csv(OUTPUT_MAPPING, index=False)
    print(f"\n✓ Saved mapping to: {OUTPUT_MAPPING}")
    print(f"  - {len(mapping_df)} facility name matches")
    print(f"  - Coverage: {len(mapping_df)/len(org_names)*100:.1f}% of organization names matched")
    
    return True

if __name__ == '__main__':
    success = create_facility_mapping()
    sys.exit(0 if success else 1)
