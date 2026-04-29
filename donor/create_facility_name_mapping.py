"""
Create a mapping file that joins Legal Business Name (provider_info) with ORGANIZATION NAME (ownership)
This speeds up facility matching in the dashboard.
"""

import pandas as pd
from pathlib import Path
import sys
import re

BASE_DIR = Path(__file__).parent.parent

OUTPUT_MAPPING = BASE_DIR / "donor" / "output" / "facility_name_mapping.csv"

def normalize_name(name):
    """Normalize name for matching"""
    if pd.isna(name) or not name:
        return ""
    return str(name).upper().strip()


def _read_csv_safe(path: Path) -> pd.DataFrame:
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return pd.read_csv(path, dtype=str, low_memory=False, encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, dtype=str, low_memory=False)


def _latest_provider_info_path():
    provider_dir = BASE_DIR / "provider_info"
    files = list(provider_dir.glob("NH_ProviderInfo_*.csv"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _latest_ownership_path():
    ownership_dir = BASE_DIR / "ownership"
    files = list(ownership_dir.glob("SNF_All_Owners*.csv"))
    if not files:
        return None
    # Prefer latest date parsed from filename when available.
    scored = []
    for p in files:
        m = re.search(r'(\d{4})[._-](\d{1,2})(?:[._-](\d{1,2}))?', p.stem)
        if m:
            scored.append((int(m.group(1)), int(m.group(2)), p))
            continue
        m2 = re.search(r'_(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[_-](\d{4})', p.stem, re.IGNORECASE)
        if m2:
            month_map = {
                "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
            }
            scored.append((int(m2.group(2)), month_map[m2.group(1).lower()], p))
    if scored:
        scored.sort(reverse=True)
        return scored[0][2]
    return max(files, key=lambda p: p.stat().st_mtime)

def create_facility_mapping():
    """Create mapping between Legal Business Name and ORGANIZATION NAME"""
    print("="*60)
    print("Creating Facility Name Mapping")
    print("="*60)
    
    provider_info_latest = _latest_provider_info_path()
    ownership_file = _latest_ownership_path()

    # Load provider info
    if provider_info_latest is None or not provider_info_latest.exists():
        print("❌ Provider info file not found in provider_info/")
        return False
    
    print(f"Loading provider info: {provider_info_latest}")
    provider_df = _read_csv_safe(provider_info_latest)
    print(f"✓ Loaded {len(provider_df)} provider records")
    
    # Check for Legal Business Name column
    if 'Legal Business Name' not in provider_df.columns:
        print("❌ 'Legal Business Name' column not found in provider info")
        print(f"Available columns: {[c for c in provider_df.columns if 'legal' in c.lower() or 'business' in c.lower()]}")
        return False
    
    # Load ownership file
    if ownership_file is None or not ownership_file.exists():
        print("❌ Ownership file not found in ownership/")
        return False
    
    print(f"Loading ownership file: {ownership_file}")
    ownership_df = _read_csv_safe(ownership_file)
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
