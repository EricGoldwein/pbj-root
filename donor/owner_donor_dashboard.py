"""
Nursing Home Owner Donation Search Dashboard
For journalists and attorneys to search owners and view political donations
"""

from flask import Flask, render_template, jsonify, request
import pandas as pd
import os
import re
from pathlib import Path
import json
import sys
from pathlib import Path
# Add donor directory to path for imports
donor_dir = Path(__file__).parent
if str(donor_dir) not in sys.path:
    sys.path.insert(0, str(donor_dir))

from fec_api_client import (
    query_donations_by_name,
    query_donations_by_committee,
    normalize_fec_donation,
    build_schedule_a_docquery_link,
    is_valid_docquery_schedule_a_url,
    FEC_API_KEY,
    FEC_API_BASE_URL,
)
import requests

app = Flask(__name__, template_folder='templates')

# Data paths
BASE_DIR = Path(__file__).parent.parent
OWNERS_DB = BASE_DIR / "donor" / "output" / "owners_database.csv"
OWNERSHIP_RAW = BASE_DIR / "ownership" / "SNF_All_Owners_Jan_2026.csv"  # Full 250k CSV
OWNERSHIP_NORM = BASE_DIR / "donor" / "output" / "ownership_normalized.csv"
PROVIDER_INFO = BASE_DIR / "provider_info_combined.csv"
PROVIDER_INFO_LATEST = BASE_DIR / "provider_info" / "NH_ProviderInfo_Dec2025.csv"  # Has Legal Business Name
FACILITY_NAME_MAPPING = BASE_DIR / "donor" / "output" / "facility_name_mapping.csv"  # Pre-computed mapping
ENTITY_LOOKUP = BASE_DIR / "ownership" / "entity_lookup.csv"
DONATIONS_DB = BASE_DIR / "donor" / "output" / "owner_donations_database.csv"
# FEC committee master: CMTE_ID -> CMTE_NM (cm26=2025-2026, cm24=2023-2024, etc.)
FEC_COMMITTEE_MASTER_DIR = BASE_DIR / "donor" / "data" / "fec_committee_master"
FEC_COMMITTEE_MASTER_FILES = [
    "cm26_2025_2026.csv", "cm24_2023_2024.csv", "cm22_2021_2022.csv",
    "cm20_2019_2020.csv", "cm18_2017_2018.csv", "cm16_2015_2016.csv", "cm14_2013_2014.csv",
]
# Committee search: only load cycles since 2020 (cm20+) for autocomplete
FEC_COMMITTEE_MASTER_FILES_RECENT = [
    "cm26_2025_2026.csv", "cm24_2023_2024.csv", "cm22_2021_2022.csv", "cm20_2019_2020.csv",
]
FEC_CM_FALLBACK_RECENT = ["cm26.csv", "cm24.csv", "cm22.csv", "cm20.csv"]
# Fallback: donor/cm26.csv, donor/cm24.csv, etc. (same cycle naming)
DONOR_DIR = BASE_DIR / "donor"
FEC_CM_FALLBACK = ["cm26.csv", "cm24.csv", "cm22.csv", "cm20.csv", "cm18.csv", "cm16.csv", "cm14.csv"]

# Cache data
committee_master = None  # dict CMTE_ID -> CMTE_NM, loaded at startup for fast lookup
committee_master_extended = None  # list of {id, name, type, dsgn} for committee search autocomplete (test page)
owners_df = None
ownership_df = None
ownership_raw_df = None  # Raw ownership file for provider matching
provider_info_df = None
provider_info_latest_df = None  # Latest provider info with Legal Business Name
facility_name_mapping_df = None  # Pre-computed mapping
entity_lookup_df = None
donations_df = None
facility_metrics_df = None

# JSON-serializable sanitizer: NaN/Inf/pd.NA are not valid JSON; replace with None
def sanitize_for_json(obj):
    """Recursively replace NaN, Inf, and pd.NA with None so jsonify() produces valid JSON."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    # Pandas/NumPy NA or NaN (must check before float so we catch pd.NA)
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(obj, float):
        if obj != obj or obj == float('inf') or obj == float('-inf'):  # nan or inf
            return None
    # NumPy scalars (e.g. from DataFrame row) - convert to Python type or None
    if hasattr(obj, 'item'):
        try:
            v = obj.item()
            return sanitize_for_json(v)
        except (ValueError, TypeError, AttributeError):
            return None
    return obj


# Normalize name function (matches owner_donor.py)
def normalize_name_for_matching(s):
    """Normalize name for matching - same as owner_donor.py normalize_name"""
    if pd.isna(s) or not s:
        return ""
    import re
    s = str(s).upper()
    s = re.sub(r"[^A-Z ]", "", s)  # Remove all non-alphabetic characters (keep only A-Z and spaces)
    s = re.sub(r"\s+", " ", s).strip()  # Normalize whitespace
    return s

# Name variation mapping (common nicknames)
NAME_VARIATIONS = {
    'WILLIAM': ['BILL', 'WILL', 'WILLY'],
    'ROBERT': ['BOB', 'ROB', 'BOBBY'],
    'RICHARD': ['DICK', 'RICK', 'RICH'],
    'JAMES': ['JIM', 'JIMMY', 'JAMIE'],
    'JOHN': ['JACK', 'JOHNNY'],
    'CHARLES': ['CHARLIE', 'CHUCK'],
    'MICHAEL': ['MIKE', 'MIKEY'],
    'JOSEPH': ['JOE', 'JOEY'],
    'THOMAS': ['TOM', 'TOMMY'],
    'CHRISTOPHER': ['CHRIS'],
    'DANIEL': ['DAN', 'DANNY'],
    'MATTHEW': ['MATT'],
    'ANTHONY': ['TONY'],
    'EDWARD': ['ED', 'EDDIE', 'TED'],
    'JOSEPH': ['JOE'],
    'PATRICK': ['PAT'],
    'KENNETH': ['KEN'],
    'STEPHEN': ['STEVE'],
    'ANDREW': ['ANDY'],
    'JOSHUA': ['JOSH'],
    'BENJAMIN': ['BEN'],
    'NICHOLAS': ['NICK'],
    'JONATHAN': ['JON'],
    'SAMUEL': ['SAM'],
    'ALEXANDER': ['ALEX'],
    'CHRISTIAN': ['CHRIS'],
    'RYAN': ['RYAN'],
    'NATHAN': ['NATE'],
    'TYLER': ['TY'],
    'JACOB': ['JAKE'],
}


def _fec_contributor_matches_owner(contributor_name: str, owner_name: str, owner_type: str) -> bool:
    """
    Check if FEC contributor_name plausibly matches the owner we searched for.
    Prevents false attribution when FEC fuzzy matching returns similar but different entities
    (e.g. CAPITAL ONE when searching CORPORATE INTERFACE).
    """
    if not contributor_name or not owner_name:
        return True  # Don't filter if missing
    contrib_norm = normalize_name_for_matching(contributor_name)
    owner_norm = normalize_name_for_matching(owner_name)
    if not contrib_norm or not owner_norm:
        return True
    # Owner name is substring of contributor (exact match) - always allow
    if owner_norm in contrib_norm:
        return True
    # Contributor is substring of owner - allow
    if contrib_norm in owner_norm:
        return True
    # For organizations: require owner's first 2 significant words to appear in contributor
    # This excludes "CAPITAL ONE SERVICES LLC CORPORATE" when owner is "CORPORATE INTERFACE"
    SUFFIXES = {'LLC', 'INC', 'CORP', 'LP', 'LTD', 'SERVICES', 'CONSULTING', 'THE'}
    owner_words = [w for w in owner_norm.split() if w and w not in SUFFIXES]
    if len(owner_words) >= 2 and owner_type.upper() == "ORGANIZATION":
        phrase = f"{owner_words[0]} {owner_words[1]}"
        if phrase in contrib_norm:
            return True
        # First word alone can match too many (e.g. "CORPORATE" matches CAPITAL ONE... CORPORATE)
        # Require at least the 2-word phrase for orgs
        return False
    if owner_words and owner_words[0] in contrib_norm:
        return True
    return False


def normalize_name_for_search(name):
    """Normalize name and generate variations for flexible matching"""
    if pd.isna(name) or not name:
        return []
    
    name_upper = str(name).upper().strip()
    variations = [name_upper]
    
    # Split into parts
    parts = name_upper.split()
    if len(parts) >= 2:
        first = parts[0]
        last = parts[-1]
        
        # Add first word alone if it's substantial - BUT skip overly broad org terms that cause
        # false positives (e.g. "CORPORATE" matches "CAPITAL ONE SERVICES LLC CORPORATE")
        OVERLY_BROAD_ORG_WORDS = {'THE', 'AND', 'OF', 'FOR', 'INC', 'LLC', 'CORP', 'LP', 'LTD',
                                  'CORPORATE', 'SERVICES', 'CONSULTING', 'INTERFACE'}
        if len(first) >= 3 and first not in OVERLY_BROAD_ORG_WORDS:
            variations.append(first)
        
        # Add nickname variations
        if first in NAME_VARIATIONS:
            for nickname in NAME_VARIATIONS[first]:
                variations.append(f"{nickname} {last}")
                if len(parts) > 2:
                    # Handle middle names/initials
                    variations.append(f"{nickname} {parts[1]} {last}")
        
        # Add last name only (if substantial)
        if len(last) >= 3 and last not in ['INC', 'LLC', 'CORP', 'LP', 'LTD', 'SERVICES', 'CONSULTING']:
            variations.append(last)
        
        # Add "First Last" (without middle)
        if len(parts) > 2:
            variations.append(f"{first} {last}")
    
    return list(set(variations))


def _load_committee_master():
    """
    Load FEC committee master (CMTE_ID -> CMTE_NM) from CSVs.
    Tries donor/data/fec_committee_master/*.csv first, then donor/cm*.csv.
    Newer cycles override older so we have one in-memory lookup for display/verification.
    """
    out = {}
    # Prefer data/fec_committee_master (named by cycle). Load oldest first so newer cycle wins.
    for fname in reversed(FEC_COMMITTEE_MASTER_FILES):
        path = FEC_COMMITTEE_MASTER_DIR / fname
        if not path.exists():
            continue
        try:
            try:
                df = pd.read_csv(path, dtype=str, usecols=["CMTE_ID", "CMTE_NM"], encoding="utf-8", on_bad_lines="skip")
            except TypeError:
                df = pd.read_csv(path, dtype=str, usecols=["CMTE_ID", "CMTE_NM"], encoding="utf-8")
            for _, row in df.iterrows():
                # pandas can return float/NaN for some cells; convert to str before .strip()
                cid = str(row.get("CMTE_ID") or "").strip()
                nm = str(row.get("CMTE_NM") or "").strip()
                if cid and cid != "nan":
                    out[cid] = nm
        except Exception as e:
            print(f"  [WARN] Could not load {path}: {e}")
    # Fallback: donor/cm26.csv, donor/cm24.csv, etc.
    if not out:
        for fname in reversed(FEC_CM_FALLBACK):
            path = DONOR_DIR / fname
            if not path.exists():
                continue
            try:
                try:
                    df = pd.read_csv(path, dtype=str, usecols=["CMTE_ID", "CMTE_NM"], encoding="utf-8", on_bad_lines="skip")
                except TypeError:
                    df = pd.read_csv(path, dtype=str, usecols=["CMTE_ID", "CMTE_NM"], encoding="utf-8")
                for _, row in df.iterrows():
                    cid = str(row.get("CMTE_ID") or "").strip()
                    nm = str(row.get("CMTE_NM") or "").strip()
                    if cid and cid != "nan":
                        out[cid] = nm
            except Exception as e:
                print(f"  [WARN] Could not load {path}: {e}")
    return out


def get_committee_display_name(committee_id, fallback=""):
    """
    Return committee name from master (CMTE_NM) for verification/display.
    Uses in-memory committee_master loaded at startup; O(1) lookup.
    """
    global committee_master
    if committee_master is None:
        return fallback or ""
    cid = (committee_id or "").strip()
    if not cid:
        return fallback or ""
    return committee_master.get(cid) or fallback or ""


def _load_committee_master_extended():
    """
    Load extended committee master (id, name, type) for committee search autocomplete.
    Only cycles since 2020 (cm20+) for smaller, more relevant set.
    CMTE_TP: Q/N=PAC, O=Super PAC, J (via CMTE_DSGN)=JFC, etc.
    """
    by_id = {}  # CMTE_ID -> {id, name, type}; newer files override
    cols = ["CMTE_ID", "CMTE_NM", "CMTE_TP", "CMTE_DSGN"]
    for fname in reversed(FEC_COMMITTEE_MASTER_FILES_RECENT):  # cm20 first, cm26 last (newer wins)
        path = FEC_COMMITTEE_MASTER_DIR / fname
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path, dtype=str, usecols=cols, encoding="utf-8", on_bad_lines="skip")
        except (TypeError, ValueError, KeyError):
            try:
                df = pd.read_csv(path, dtype=str, usecols=["CMTE_ID", "CMTE_NM"], encoding="utf-8", on_bad_lines="skip")
                df["CMTE_TP"] = ""
                df["CMTE_DSGN"] = ""
            except Exception:
                continue
        for _, row in df.iterrows():
            cid = str(row.get("CMTE_ID") or "").strip()
            if not cid or cid == "nan":
                continue
            nm = str(row.get("CMTE_NM") or "").strip()
            tp = str(row.get("CMTE_TP") or "").strip().upper()
            dsgn = str(row.get("CMTE_DSGN") or "").strip().upper()
            type_label = "Committee"
            if dsgn == "J":
                type_label = "JFC"
            elif tp == "O":
                type_label = "Super PAC"
            elif tp in ("Q", "N", "V"):
                type_label = "PAC"
            by_id[cid] = {"id": cid, "name": nm, "type": type_label}
    if not by_id:
        for fname in reversed(FEC_CM_FALLBACK_RECENT):
            path = DONOR_DIR / fname
            if not path.exists():
                continue
            try:
                df = pd.read_csv(path, dtype=str, usecols=cols, encoding="utf-8", on_bad_lines="skip")
            except (TypeError, ValueError, KeyError):
                try:
                    df = pd.read_csv(path, dtype=str, usecols=["CMTE_ID", "CMTE_NM"], encoding="utf-8", on_bad_lines="skip")
                    df["CMTE_TP"] = ""
                    df["CMTE_DSGN"] = ""
                except Exception:
                    continue
            for _, row in df.iterrows():
                cid = str(row.get("CMTE_ID") or "").strip()
                if not cid or cid == "nan":
                    continue
                nm = str(row.get("CMTE_NM") or "").strip()
                tp = str(row.get("CMTE_TP") or "").strip().upper()
                dsgn = str(row.get("CMTE_DSGN") or "").strip().upper()
                type_label = "Committee"
                if dsgn == "J":
                    type_label = "JFC"
                elif tp == "O":
                    type_label = "Super PAC"
                elif tp in ("Q", "N", "V"):
                    type_label = "PAC"
                by_id[cid] = {"id": cid, "name": nm, "type": type_label}
    return list(by_id.values())


def load_data():
    """
    Load all data files - FAST: prioritize pre-processed database over raw CSV
    
    IMPORTANT: This function does NOT call the FEC API.
    - Initial load: Only loads owner names for search (from pre-processed database)
    - FEC API: Only called when user clicks "Query FEC API (Live)" button (on-demand)
    """
    global owners_df, ownership_df, ownership_raw_df, provider_info_df, entity_lookup_df, donations_df, committee_master
    
    print("="*60)
    print("Loading data for dashboard...")
    print("="*60)
    print("NOTE: This does NOT call FEC API. FEC API is called on-demand when viewing owner details.")
    print("="*60)
    
    # PART 1: Load pre-processed owners database (FAST - for search only)
    # This should be created by running: python donor/owner_donor.py MODE=extract
    # NO FEC API CALLS HERE - just owner names for search
    if OWNERS_DB.exists():
        try:
            print(f"Loading pre-processed owners database: {OWNERS_DB}")
            try:
                owners_df = pd.read_csv(OWNERS_DB, dtype=str, low_memory=False, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    owners_df = pd.read_csv(OWNERS_DB, dtype=str, low_memory=False, encoding='utf-8-sig')
                except UnicodeDecodeError:
                    owners_df = pd.read_csv(OWNERS_DB, dtype=str, low_memory=False, encoding='latin-1')
            print(f"✓ Loaded {len(owners_df)} owners from database (FAST)")
            if 'owner_type' in owners_df.columns:
                individuals = len(owners_df[owners_df['owner_type'] == 'INDIVIDUAL'])
                orgs = len(owners_df[owners_df['owner_type'] == 'ORGANIZATION'])
                print(f"  - {individuals} individuals")
                print(f"  - {orgs} organizations")
            
            # Warn if database seems incomplete (likely filtered)
            if len(owners_df) < 1000:
                print(f"\n⚠ WARNING: Only {len(owners_df)} owners loaded. This database appears incomplete.")
                print("  It was likely created with a filter (e.g., FILTER_STATE=DE or FILTER_LIMIT).")
                print("  To load ALL owners from the full 250k dataset, run:")
                print("    python donor/owner_donor.py MODE=extract")
                print("  (Make sure FILTER_STATE and FILTER_LIMIT are not set)")
        except Exception as e:
            print(f"✗ Error loading owners database: {e}")
            owners_df = pd.DataFrame()
    else:
        print(f"⚠ Owners database not found: {OWNERS_DB}")
        print("  Run 'python donor/owner_donor.py MODE=extract' to create it")
        owners_df = pd.DataFrame()
    
    # PART 2: Load pre-processed donations database (FAST - for display)
    # This is OPTIONAL - pre-processed donations from previous FEC API queries
    # If not available, user can still query FEC API live via the button
    # NO FEC API CALLS HERE - just loading previously queried data
    if DONATIONS_DB.exists():
        try:
            print(f"Loading pre-processed donations database: {DONATIONS_DB}")
            try:
                donations_df = pd.read_csv(DONATIONS_DB, dtype=str, low_memory=False, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    donations_df = pd.read_csv(DONATIONS_DB, dtype=str, low_memory=False, encoding='utf-8-sig')
                except UnicodeDecodeError:
                    donations_df = pd.read_csv(DONATIONS_DB, dtype=str, low_memory=False, encoding='latin-1')
            print(f"✓ Loaded {len(donations_df)} donation records (FAST - pre-processed)")
        except Exception as e:
            print(f"✗ Error loading donations: {e}")
            donations_df = pd.DataFrame()
    else:
        print(f"⚠ Donations database not found: {DONATIONS_DB}")
        print("  (Optional) Run 'python donor/owner_donor.py MODE=query' to pre-process donations")
        print("  Or use 'Query FEC API (Live)' button to query on-demand")
        donations_df = pd.DataFrame()
    
    # PART 3: Load FEC committee master (CMTE_ID -> CMTE_NM) for fast committee name lookup/verification
    try:
        committee_master = _load_committee_master()
        if committee_master:
            print(f"✓ Loaded FEC committee master: {len(committee_master)} committees (for display/verification)")
        else:
            print("  (No FEC committee master CSVs found; committee names from API/CSV only)")
    except Exception as e:
        print(f"  [WARN] FEC committee master: {e}")
        committee_master = {}
    
    # Load normalized ownership for facility details (if available)
    if OWNERSHIP_NORM.exists():
        try:
            try:
                ownership_df = pd.read_csv(OWNERSHIP_NORM, dtype=str, low_memory=False, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    ownership_df = pd.read_csv(OWNERSHIP_NORM, dtype=str, low_memory=False, encoding='utf-8-sig')
                except UnicodeDecodeError:
                    ownership_df = pd.read_csv(OWNERSHIP_NORM, dtype=str, low_memory=False, encoding='latin-1')
            print(f"✓ Loaded {len(ownership_df)} ownership records for facility details")
        except Exception as e:
            print(f"✗ Error loading ownership: {e}")
            ownership_df = pd.DataFrame()
    else:
        ownership_df = pd.DataFrame()
    
    # Warn if owners database seems incomplete
    if owners_df is not None and not owners_df.empty:
        if len(owners_df) < 1000:
            print(f"\n⚠ WARNING: Only {len(owners_df)} owners loaded. This seems incomplete.")
            print("  The owners database was likely created with a filter (e.g., FILTER_STATE=DE or FILTER_LIMIT).")
            print("  To load all owners, run: python donor/owner_donor.py MODE=extract (without filters)")
    
    # Load raw ownership file for provider matching (needed for ORGANIZATION NAME matching)
    # This is a large file (55MB+) - load with error handling and memory management
    global ownership_raw_df
    if OWNERSHIP_RAW.exists():
        try:
            print(f"Loading raw ownership file for provider matching: {OWNERSHIP_RAW}")
            print("  (This is a large file and may take a moment...)")
            try:
                # Use chunksize for very large files to manage memory
                ownership_raw_df = pd.read_csv(OWNERSHIP_RAW, dtype=str, low_memory=False, encoding='utf-8', nrows=None)
            except UnicodeDecodeError:
                try:
                    ownership_raw_df = pd.read_csv(OWNERSHIP_RAW, dtype=str, low_memory=False, encoding='utf-8-sig', nrows=None)
                except UnicodeDecodeError:
                    try:
                        ownership_raw_df = pd.read_csv(OWNERSHIP_RAW, dtype=str, low_memory=False, encoding='cp1252', nrows=None)
                    except UnicodeDecodeError:
                        ownership_raw_df = pd.read_csv(OWNERSHIP_RAW, dtype=str, low_memory=False, encoding='latin-1', nrows=None)
            print(f"✓ Loaded {len(ownership_raw_df)} raw ownership records for provider matching")
        except MemoryError as e:
            print(f"✗ Memory error loading raw ownership file: {e}")
            print("  The file is very large. Consider using a smaller subset or increasing server memory.")
            ownership_raw_df = pd.DataFrame()
        except Exception as e:
            print(f"✗ Error loading raw ownership file: {e}")
            import traceback
            traceback.print_exc()
            ownership_raw_df = pd.DataFrame()
    else:
        print(f"⚠ Raw ownership file not found: {OWNERSHIP_RAW}")
        print("  Provider search by name/CCN will have limited functionality")
        ownership_raw_df = pd.DataFrame()
    
    # Note: ownership_df is already loaded above, no need to load again
    
    if PROVIDER_INFO.exists():
        try:
            # First, check what columns are available
            try:
                sample_df = pd.read_csv(PROVIDER_INFO, nrows=1, dtype=str, low_memory=False, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    sample_df = pd.read_csv(PROVIDER_INFO, nrows=1, dtype=str, low_memory=False, encoding='utf-8-sig')
                except UnicodeDecodeError:
                    sample_df = pd.read_csv(PROVIDER_INFO, nrows=1, dtype=str, low_memory=False, encoding='latin-1')
            available_cols = list(sample_df.columns)
            
            # Try to find county column (could be county_name, county, County, etc.)
            county_col = None
            for col in available_cols:
                if 'county' in col.lower() or 'township' in col.lower():
                    county_col = col
                    break
            
            # Build usecols list with available columns
            base_cols = ['ccn', 'provider_name', 'state', 'city', 'avg_residents_per_day', 'overall_rating', 'ownership_type']
            usecols_list = [col for col in base_cols if col in available_cols]
            if county_col and county_col not in usecols_list:
                usecols_list.append(county_col)
            
            # Add entity ID columns if available
            for entity_col in ['Chain ID', 'chain_id', 'Chain_ID', 'Entity ID', 'entity_id', 'affiliated_entity_id', 
                             'Chain Name', 'chain_name', 'Chain_Name', 'Entity Name', 'entity_name', 'affiliated_entity_name']:
                if entity_col in available_cols and entity_col not in usecols_list:
                    usecols_list.append(entity_col)
            
            # Determine encoding from sample read
            encoding = 'utf-8'
            try:
                pd.read_csv(PROVIDER_INFO, nrows=1, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    pd.read_csv(PROVIDER_INFO, nrows=1, encoding='utf-8-sig')
                    encoding = 'utf-8-sig'
                except UnicodeDecodeError:
                    encoding = 'latin-1'
            
            provider_info_df = pd.read_csv(PROVIDER_INFO, dtype=str, low_memory=False, 
                                          usecols=usecols_list,  # type: ignore
                                          nrows=None, encoding=encoding)
            print(f"✓ Loaded {len(provider_info_df)} provider records")
        except Exception as e:
            print(f"✗ Error loading provider info (trying full load): {e}")
            try:
                try:
                    provider_info_df = pd.read_csv(PROVIDER_INFO, dtype=str, low_memory=False, encoding='utf-8')
                except UnicodeDecodeError:
                    try:
                        provider_info_df = pd.read_csv(PROVIDER_INFO, dtype=str, low_memory=False, encoding='utf-8-sig')
                    except UnicodeDecodeError:
                        provider_info_df = pd.read_csv(PROVIDER_INFO, dtype=str, low_memory=False, encoding='latin-1')
                print(f"✓ Loaded {len(provider_info_df)} provider records (full)")
            except Exception as e2:
                print(f"✗ Error loading provider info: {e2}")
                provider_info_df = pd.DataFrame()
    
    # Load latest provider info with Legal Business Name (for facility matching)
    global provider_info_latest_df
    if PROVIDER_INFO_LATEST.exists():
        try:
            print(f"Loading latest provider info with Legal Business Name: {PROVIDER_INFO_LATEST}")
            try:
                provider_info_latest_df = pd.read_csv(PROVIDER_INFO_LATEST, dtype=str, low_memory=False, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    provider_info_latest_df = pd.read_csv(PROVIDER_INFO_LATEST, dtype=str, low_memory=False, encoding='utf-8-sig')
                except UnicodeDecodeError:
                    provider_info_latest_df = pd.read_csv(PROVIDER_INFO_LATEST, dtype=str, low_memory=False, encoding='latin-1')
            print(f"✓ Loaded {len(provider_info_latest_df)} provider records (with Legal Business Name)")
        except Exception as e:
            print(f"✗ Error loading latest provider info: {e}")
            provider_info_latest_df = pd.DataFrame()
    else:
        print(f"⚠ Latest provider info not found: {PROVIDER_INFO_LATEST}")
        provider_info_latest_df = pd.DataFrame()
    
    # Load pre-computed facility name mapping (if exists - speeds up matching)
    global facility_name_mapping_df
    if FACILITY_NAME_MAPPING.exists():
        try:
            print(f"Loading facility name mapping: {FACILITY_NAME_MAPPING}")
            try:
                facility_name_mapping_df = pd.read_csv(FACILITY_NAME_MAPPING, dtype=str, low_memory=False, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    facility_name_mapping_df = pd.read_csv(FACILITY_NAME_MAPPING, dtype=str, low_memory=False, encoding='utf-8-sig')
                except UnicodeDecodeError:
                    facility_name_mapping_df = pd.read_csv(FACILITY_NAME_MAPPING, dtype=str, low_memory=False, encoding='latin-1')
            print(f"✓ Loaded {len(facility_name_mapping_df)} facility name mappings (FAST)")
        except Exception as e:
            print(f"✗ Error loading facility name mapping: {e}")
            facility_name_mapping_df = pd.DataFrame()
    else:
        print(f"⚠ Facility name mapping not found: {FACILITY_NAME_MAPPING}")
        print("  Run 'python donor/create_facility_name_mapping.py' to create it (speeds up matching)")
        facility_name_mapping_df = pd.DataFrame()
    
    if ENTITY_LOOKUP.exists():
        try:
            try:
                entity_lookup_df = pd.read_csv(ENTITY_LOOKUP, dtype=str, low_memory=False, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    entity_lookup_df = pd.read_csv(ENTITY_LOOKUP, dtype=str, low_memory=False, encoding='utf-8-sig')
                except UnicodeDecodeError:
                    entity_lookup_df = pd.read_csv(ENTITY_LOOKUP, dtype=str, low_memory=False, encoding='latin-1')
            print(f"Loaded {len(entity_lookup_df)} entity records")
        except Exception as e:
            print(f"Error loading entity lookup: {e}")
            entity_lookup_df = pd.DataFrame()
    
    # Load facility metrics if available (for performance data)
    global facility_metrics_df
    FACILITY_METRICS = BASE_DIR / "facility_lite_metrics.csv"
    if not FACILITY_METRICS.exists():
        FACILITY_METRICS = BASE_DIR / "facility_quarterly_metrics.csv"
    
    if FACILITY_METRICS.exists():
        try:
            # Load key columns only to avoid memory issues
            try:
                facility_metrics_df = pd.read_csv(FACILITY_METRICS, dtype=str, low_memory=False, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    facility_metrics_df = pd.read_csv(FACILITY_METRICS, dtype=str, low_memory=False, encoding='utf-8-sig')
                except UnicodeDecodeError:
                    facility_metrics_df = pd.read_csv(FACILITY_METRICS, dtype=str, low_memory=False, encoding='latin-1')
            print(f"Loaded {len(facility_metrics_df)} facility metric records")
        except Exception as e:
            print(f"Error loading facility metrics: {e}")
            facility_metrics_df = pd.DataFrame()
    else:
        print("No facility metrics file found. Performance data will not be available.")
        facility_metrics_df = pd.DataFrame()


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('owner_donor_dashboard.html')


@app.route('/test')
def index_test():
    """Test page with Committee search mode (additive, isolated)"""
    return render_template('owner_donor_dashboard_test.html')


@app.route('/api/autocomplete')
def autocomplete():
    """Provide autocomplete suggestions for search"""
    try:
        query = request.args.get('q', '').strip()
        search_type = request.args.get('type', 'all')  # all, individual, organization, provider
        
        if not query or len(query) < 2:
            return jsonify({'suggestions': []})
        
        # Handle provider search differently
        if search_type == 'provider':
            return autocomplete_provider_search(query)
        
        # Regular owner search
        if owners_df is None or owners_df.empty:
            return jsonify({'suggestions': []})
        
        query_upper = query.upper()
        
        # Filter by type if needed
        if search_type == 'individual':
            filtered_df = owners_df[owners_df['owner_type'] == 'INDIVIDUAL']
        elif search_type == 'organization':
            filtered_df = owners_df[owners_df['owner_type'] == 'ORGANIZATION']
        else:
            filtered_df = owners_df
        
        # Search in multiple fields (simpler for autocomplete - just contains match)
        # Convert all to uppercase for case-insensitive matching
        name_matches = (
            filtered_df['owner_name_original'].astype(str).str.upper().str.contains(query_upper, na=False, regex=False) |
            filtered_df['owner_name'].astype(str).str.upper().str.contains(query_upper, na=False, regex=False)
        )
        
        # Also check org_name if it exists
        if 'owner_org_name' in filtered_df.columns:
            org_match = filtered_df['owner_org_name'].astype(str).str.upper().str.contains(query_upper, na=False, regex=False)
            name_matches = name_matches | org_match
        
        results = filtered_df[name_matches].head(10)
        
        suggestions = []
        for _, row in results.iterrows():
            facilities_str = row.get('facilities', '') if pd.notna(row.get('facilities')) else ''
            facilities = [f.strip() for f in facilities_str.split(',') if f.strip()] if facilities_str else []
            suggestions.append({
                'name': row.get('owner_name_original', row.get('owner_name', '')),
                'type': row.get('owner_type', 'UNKNOWN'),
                'facilities': len(facilities)
            })
        
        return jsonify({'suggestions': suggestions})
    except Exception as e:
        print(f"Error in autocomplete: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def autocomplete_provider_search(query):
    """Autocomplete for provider search - searches providers and returns matching owners"""
    try:
        print(f"[DEBUG] autocomplete_provider_search: query='{query}'")
        query_upper = query.upper().strip()
        query_clean = query.replace('O', '').replace('o', '').replace(' ', '').replace('-', '').strip()
        is_ccn_search = query_clean.isdigit() and len(query_clean) <= 6
        print(f"[DEBUG] is_ccn_search={is_ccn_search}, query_clean='{query_clean}'")
        
        matched_providers = pd.DataFrame()
        matched_org_names = set()
        
        # Search in provider_info_latest_df
        if provider_info_latest_df is not None and not provider_info_latest_df.empty:
            # Search by CCN if it looks like a CCN
            if is_ccn_search:
                ccn_normalized = query_clean.zfill(6)
                ccn_col = None
                for col in ['CMS Certification Number (CCN)', 'ccn', 'CCN', 'PROVNUM']:
                    if col in provider_info_latest_df.columns:
                        ccn_col = col
                        break
                
                if ccn_col:
                    matched_providers = provider_info_latest_df[
                        provider_info_latest_df[ccn_col].astype(str).str.replace('O', '').str.replace(' ', '').str.replace('-', '').str.strip().str.zfill(6) == ccn_normalized
                    ].head(5)
                    print(f"[DEBUG] CCN search found {len(matched_providers)} providers")
            
            # Search by Provider Name
            if matched_providers.empty and 'Provider Name' in provider_info_latest_df.columns:
                matched_providers = provider_info_latest_df[
                    provider_info_latest_df['Provider Name'].astype(str).str.upper().str.contains(query_upper, na=False, regex=False)
                ].head(5)
                print(f"[DEBUG] Provider Name search found {len(matched_providers)} providers")
            
            # Also search Legal Business Name
            if 'Legal Business Name' in provider_info_latest_df.columns:
                legal_name_matches = provider_info_latest_df[
                    provider_info_latest_df['Legal Business Name'].astype(str).str.upper().str.contains(query_upper, na=False, regex=False)
                ].head(5)
                matched_providers = pd.concat([matched_providers, legal_name_matches]).drop_duplicates()
                print(f"[DEBUG] Legal Business Name search found {len(legal_name_matches)} providers, total after merge: {len(matched_providers)}")
        
        if matched_providers.empty:
            print(f"[DEBUG] No providers found, returning empty suggestions")
            return jsonify({'suggestions': []})
        
        print(f"[DEBUG] Found {len(matched_providers)} matched providers")
        
        # For autocomplete, return provider suggestions (not owners)
        suggestions = []
        seen_providers = set()
        
        for _, provider_row in matched_providers.head(10).iterrows():  # Limit to 10
            # Get provider name and CCN
            provider_name = provider_row.get('Provider Name', '')
            ccn = None
            for col in ['CMS Certification Number (CCN)', 'ccn', 'CCN', 'PROVNUM']:
                if col in provider_row.index and pd.notna(provider_row.get(col)):
                    ccn_val = str(provider_row.get(col)).strip().replace('O', '').replace(' ', '').replace('-', '')
                    if ccn_val and ccn_val.isdigit() and len(ccn_val) <= 6:
                        ccn = ccn_val.zfill(6)
                        break
            
            # Create display name: "Provider Name (CCN)" or just "Provider Name"
            if provider_name and pd.notna(provider_name):
                display_name = str(provider_name).strip()
                if ccn:
                    display_name = f"{display_name} ({ccn})"
                
                # Use provider name + CCN as unique key
                provider_key = f"{provider_name}_{ccn}" if ccn else provider_name
                if provider_key not in seen_providers:
                    seen_providers.add(provider_key)
                    suggestions.append({
                        'name': display_name,
                        'type': 'PROVIDER',
                        'facilities': 1,  # Will show as "1 Provider"
                        'provider_name': provider_name,
                        'ccn': ccn
                    })
        
        print(f"[DEBUG] Returning {len(suggestions)} provider suggestions")
        return jsonify({'suggestions': suggestions})
    except Exception as e:
        print(f"Error in autocomplete_provider_search: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'suggestions': []})


@app.route('/api/search')
def search():
    """Search for owners by name, organization, or provider (nursing home)"""
    try:
        query = request.args.get('q', '').strip()
        search_type = request.args.get('type', 'all')  # 'all', 'individual', 'organization', 'provider'
        
        if not query or len(query) < 2:
            return jsonify({'results': [], 'count': 0})
        
        if owners_df is None or owners_df.empty:
            return jsonify({'error': 'Owners database not loaded'}), 500
        
        # Handle provider search (search by provider name/CCN, then find owners)
        if search_type == 'provider':
            return search_by_provider(query)
        
        # Generate name variations for flexible matching
        query_variations = normalize_name_for_search(query)
        query_upper = query.upper()
        query_variations.append(query_upper)  # Add original
        
        if search_type == 'individual':
            mask = owners_df['owner_type'] == 'INDIVIDUAL'
        elif search_type == 'organization':
            mask = owners_df['owner_type'] == 'ORGANIZATION'
        else:
            mask = pd.Series([True] * len(owners_df))
        
        # Smart search with relevance scoring
        query_upper = query.upper().strip()
        query_words = query_upper.split()
        is_multi_word = len(query_words) > 1
        
        # Create relevance scores
        owners_df['_relevance_score'] = 0
        owners_df['_match_type'] = ''
        
        # Exact match (highest priority) - prioritize owner_name (normalized) since it's more reliable
        exact_match_normalized = owners_df['owner_name'].str.upper().str.strip() == query_upper
        exact_match_original = owners_df['owner_name_original'].str.upper().str.strip() == query_upper
        owners_df.loc[exact_match_normalized, '_relevance_score'] = 1000
        owners_df.loc[exact_match_normalized, '_match_type'] = 'exact'
        owners_df.loc[exact_match_original & ~exact_match_normalized, '_relevance_score'] = 950
        owners_df.loc[exact_match_original & ~exact_match_normalized, '_match_type'] = 'exact_original'
        
        # For multi-word queries: require ALL words to be present (not just any word)
        if is_multi_word:
            # Check if ALL words are present in the name
            all_words_match_normalized = pd.Series([True] * len(owners_df))
            all_words_match_original = pd.Series([True] * len(owners_df))
            
            for word in query_words:
                if len(word) >= 2:  # Match words 2+ chars
                    word_in_normalized = owners_df['owner_name'].str.upper().str.contains(word, na=False, regex=False)
                    word_in_original = owners_df['owner_name_original'].str.upper().str.contains(word, na=False, regex=False)
                    all_words_match_normalized = all_words_match_normalized & word_in_normalized
                    all_words_match_original = all_words_match_original & word_in_original
            
            # Only give score if ALL words match (and no exact match already)
            owners_df.loc[all_words_match_normalized & (owners_df['_relevance_score'] == 0), '_relevance_score'] = 200
            owners_df.loc[all_words_match_normalized & (owners_df['_relevance_score'] == 0), '_match_type'] = 'all_words'
            owners_df.loc[all_words_match_original & ~all_words_match_normalized & (owners_df['_relevance_score'] == 0), '_relevance_score'] = 150
            owners_df.loc[all_words_match_original & ~all_words_match_normalized & (owners_df['_relevance_score'] == 0), '_match_type'] = 'all_words_original'
        else:
            # Single word query - allow starts with and contains
            starts_normalized = owners_df['owner_name'].str.upper().str.startswith(query_upper, na=False)
            starts_original = owners_df['owner_name_original'].str.upper().str.startswith(query_upper, na=False)
            owners_df.loc[starts_normalized & (owners_df['_relevance_score'] == 0), '_relevance_score'] = 500
            owners_df.loc[starts_normalized & (owners_df['_relevance_score'] == 0), '_match_type'] = 'starts_with'
            owners_df.loc[starts_original & (owners_df['_relevance_score'] == 0), '_relevance_score'] = 450
            owners_df.loc[starts_original & (owners_df['_relevance_score'] == 0), '_match_type'] = 'starts_with_original'
            
            # Contains query (medium priority) - prioritize normalized name
            contains_normalized = owners_df['owner_name'].str.upper().str.contains(query_upper, na=False, regex=False)
            contains_original = owners_df['owner_name_original'].str.upper().str.contains(query_upper, na=False, regex=False)
            owners_df.loc[contains_normalized & (owners_df['_relevance_score'] == 0), '_relevance_score'] = 100
            owners_df.loc[contains_normalized & (owners_df['_relevance_score'] == 0), '_match_type'] = 'contains'
            owners_df.loc[contains_original & (owners_df['_relevance_score'] == 0), '_relevance_score'] = 90
            owners_df.loc[contains_original & (owners_df['_relevance_score'] == 0), '_match_type'] = 'contains_original'
        
        # Organization name match
        if 'owner_org_name' in owners_df.columns:
            if is_multi_word:
                # For multi-word, require ALL words in org name
                all_words_in_org = pd.Series([True] * len(owners_df))
                for word in query_words:
                    if len(word) >= 2:
                        word_in_org = owners_df['owner_org_name'].str.upper().str.contains(word, na=False, regex=False)
                        all_words_in_org = all_words_in_org & word_in_org
                owners_df.loc[all_words_in_org & (owners_df['_relevance_score'] == 0), '_relevance_score'] = 180
            else:
                org_exact = owners_df['owner_org_name'].str.upper() == query_upper
                org_contains = owners_df['owner_org_name'].str.upper().str.contains(query_upper, na=False, regex=False)
                owners_df.loc[org_exact & (owners_df['_relevance_score'] == 0), '_relevance_score'] = 800
                owners_df.loc[org_contains & (owners_df['_relevance_score'] == 0), '_relevance_score'] = 50
        
        # Filter by search type and get matches
        has_match = owners_df['_relevance_score'] > 0
        results = owners_df[mask & has_match].copy()
        
        # Sort by relevance (highest first), then by normalized name (more reliable)
        # If there's an exact match, ONLY show exact matches (relevance >= 1000)
        exact_matches = results[results['_relevance_score'] >= 1000]
        if not exact_matches.empty:
            # Only show exact matches - deduplicate by owner_name to avoid showing multiple records for same owner
            results = exact_matches.sort_values(['_relevance_score', 'owner_name'], ascending=[False, True])
            # Keep only first record per unique owner_name (normalized)
            results = results.drop_duplicates(subset=['owner_name'], keep='first')
            # Limit to max 10 exact matches (should usually be just 1)
            results = results.head(10)
        else:
            # No exact match, show top results
            results = results.sort_values(['_relevance_score', 'owner_name'], ascending=[False, True]).head(50)
        
        # Drop temporary columns
        results = results.drop(columns=['_relevance_score', '_match_type'], errors='ignore')
        
        # Format results
        formatted = []
        if results.empty:
            return jsonify({'results': [], 'count': 0})
        
        for _, row in results.iterrows():
            facilities_str = row.get('facilities', '') if pd.notna(row.get('facilities')) else ''
            facilities = [f.strip() for f in facilities_str.split(',') if f.strip()] if facilities_str else []
            
            enrollment_ids_str = row.get('enrollment_ids', '') if pd.notna(row.get('enrollment_ids')) else ''
            enrollment_ids = [e.strip() for e in enrollment_ids_str.split(',') if e.strip()] if enrollment_ids_str else []
            
            # Use owner_name (normalized) if it's a better match, otherwise use owner_name_original
            # owner_name is more reliable since owner_name_original can be wrong due to SQL join issues
            owner_name_display = row.get('owner_name', '')
            owner_name_orig = row.get('owner_name_original', '')
            
            # If owner_name matches the query better, use it for display
            query_upper = query.upper()
            if owner_name_display.upper() == query_upper or query_upper in owner_name_display.upper():
                display_name = owner_name_display
            elif owner_name_orig and owner_name_orig.upper() == query_upper:
                display_name = owner_name_orig
            else:
                # Prefer owner_name_original if it exists and looks valid, otherwise use owner_name
                display_name = owner_name_orig if owner_name_orig and owner_name_orig.strip() else owner_name_display
            
            formatted.append({
                'owner_name': display_name,
                'owner_name_normalized': owner_name_display,  # Keep normalized for API lookups
                'owner_type': row.get('owner_type', 'UNKNOWN'),
                'facilities': facilities,
                'num_facilities': len(facilities),
                'enrollment_ids': enrollment_ids,
                'is_equity_owner': row.get('is_equity_owner', False) if 'is_equity_owner' in row else False,
                'is_officer': row.get('is_officer', False) if 'is_officer' in row else False,
                'earliest_association': row.get('earliest_association', '') if 'earliest_association' in row else ''
            })
        
        return jsonify({'results': formatted, 'count': len(formatted)})
    except Exception as e:
        print(f"Error in search: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def _ensure_committee_master_extended():
    """Lazy-load committee_master_extended for committee search (test page only)."""
    global committee_master_extended
    if committee_master_extended is None:
        committee_master_extended = _load_committee_master_extended()
    return committee_master_extended


@app.route('/api/autocomplete/committee')
def autocomplete_committee():
    """Autocomplete for committee search (test page only)."""
    try:
        query = request.args.get('q', '').strip()
        if not query or len(query) < 2:
            return jsonify({'suggestions': []})
        committees = _ensure_committee_master_extended()
        if not committees:
            return jsonify({'suggestions': []})
        query_upper = query.upper()
        suggestions = []
        for c in committees:
            if query_upper in c['name'].upper() or query_upper in c.get('id', '').upper():
                suggestions.append({
                    'name': c['name'],
                    'id': c['id'],
                    'type': c.get('type', 'Committee'),
                })
                if len(suggestions) >= 10:
                    break
        return jsonify({'suggestions': suggestions})
    except Exception as e:
        print(f"Error in autocomplete_committee: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'suggestions': []})


@app.route('/api/committee/providers', methods=['POST'])
def committee_providers_endpoint():
    """Lazy-load providers for committee search (test page). Accepts {owners: [...], committee_id}."""
    try:
        data = request.get_json() or {}
        owners = data.get('owners', [])
        if not owners:
            return jsonify({'providers': []})
        return jsonify({'providers': _compute_providers_from_owners(owners)})
    except Exception as e:
        print(f"Error in committee_providers_endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'providers': []}), 500


def _compute_providers_from_owners(owners_deduped):
    """Compute provider list from owners (extracted for lazy loading)."""
    global owners_df, facility_name_mapping_df, provider_info_latest_df, facility_metrics_df
    providers_result = []
    prov_key_to_data = {}
    for o in owners_deduped:
        owner_matches = owners_df[owners_df['owner_name'] == o.get('owner_name_normalized', '')] if owners_df is not None and not owners_df.empty else pd.DataFrame()
        if owner_matches.empty:
            continue
        owner_row = owner_matches.iloc[0]
        facilities_str = owner_row.get('facilities', '') or ''
        facilities = [f.strip() for f in facilities_str.split(',') if f.strip()]
        amt = float(o.get('total_contributed', 0))
        for fac_name in facilities:
            ccn = None
            prov_name = fac_name
            state = ''
            if facility_name_mapping_df is not None and not facility_name_mapping_df.empty and 'ORGANIZATION NAME' in facility_name_mapping_df.columns:
                norm_fac = str(fac_name).upper().strip()
                mapping_match = facility_name_mapping_df[
                    facility_name_mapping_df['ORGANIZATION NAME'].astype(str).str.upper().str.strip() == norm_fac
                ]
                if not mapping_match.empty and 'CCN' in mapping_match.columns:
                    ccn_val = str(mapping_match.iloc[0].get('CCN', '')).strip().replace('O', '').replace(' ', '').replace('-', '')
                    if ccn_val and ccn_val.isdigit() and len(ccn_val) <= 6:
                        ccn = ccn_val.zfill(6)
            if not ccn and provider_info_latest_df is not None and not provider_info_latest_df.empty and 'Legal Business Name' in provider_info_latest_df.columns:
                norm_fac = str(fac_name).upper().strip()
                match = provider_info_latest_df[
                    provider_info_latest_df['Legal Business Name'].astype(str).str.upper().str.strip() == norm_fac
                ]
                if not match.empty:
                    r = match.iloc[0]
                    prov_name = r.get('Provider Name', r.get('Legal Business Name', fac_name))
                    for state_col in ['State', 'STATE', 'state']:
                        if state_col in r.index and pd.notna(r.get(state_col)):
                            state = str(r.get(state_col)).strip()
                            break
                    for col in ['CMS Certification Number (CCN)', 'ccn', 'CCN', 'PROVNUM']:
                        if col in r.index and pd.notna(r.get(col)):
                            ccn_val = str(r.get(col)).strip().replace('O', '').replace(' ', '').replace('-', '')
                            if ccn_val and ccn_val.isdigit() and len(ccn_val) <= 6:
                                ccn = ccn_val.zfill(6)
                                break
            if ccn and provider_info_latest_df is not None and not provider_info_latest_df.empty:
                ccn_col = 'CMS Certification Number (CCN)' if 'CMS Certification Number (CCN)' in provider_info_latest_df.columns else 'ccn'
                if ccn_col not in provider_info_latest_df.columns:
                    ccn_col = 'CCN' if 'CCN' in provider_info_latest_df.columns else 'PROVNUM'
                if ccn_col in provider_info_latest_df.columns:
                    match = provider_info_latest_df[
                        provider_info_latest_df[ccn_col].astype(str).str.replace('O', '').str.replace(' ', '').str.replace('-', '').str.strip().str.zfill(6) == ccn
                    ]
                    if not match.empty:
                        r = match.iloc[0]
                        prov_name = r.get('Provider Name', r.get('Legal Business Name', fac_name))
                        if not state:
                            for state_col in ['State', 'STATE', 'state']:
                                if state_col in r.index and pd.notna(r.get(state_col)):
                                    state = str(r.get(state_col)).strip()
                                    break
            prov_key = (fac_name, ccn or '') if ccn else (fac_name, fac_name)
            if prov_key not in prov_key_to_data:
                avg_hprd = ''
                if ccn and facility_metrics_df is not None and not facility_metrics_df.empty and 'PROVNUM' in facility_metrics_df.columns:
                    m = facility_metrics_df[facility_metrics_df['PROVNUM'].astype(str).str.zfill(6) == ccn]
                    if not m.empty:
                        try:
                            h = float(m.iloc[-1].get('Total_Nurse_HPRD', 0) or 0)
                            avg_hprd = round(h, 2) if h else ''
                        except (ValueError, TypeError):
                            pass
                prov_key_to_data[prov_key] = {
                    'provider_name': prov_name, 'state': state, 'ownership_entity': fac_name,
                    'total_amount': 0, 'ccn': ccn, 'avg_hprd': avg_hprd,
                }
            prov_key_to_data[prov_key]['total_amount'] += amt
    for pv in prov_key_to_data.values():
        pv['total_amount'] = round(pv['total_amount'], 0)  # round to dollar
        providers_result.append(pv)
    providers_result.sort(key=lambda x: -x['total_amount'])
    return providers_result


@app.route('/api/search/committee')
def search_by_committee_endpoint():
    """Search by committee: committee -> donors -> owners (providers lazy-loaded)."""
    try:
        query = request.args.get('q', '').strip()
        if not query or len(query) < 2:
            return jsonify({'error': 'Please enter at least 2 characters'}), 400
        include_providers = request.args.get('include_providers', '0').lower() in ('1', 'true', 'yes')
        return search_by_committee(query, include_providers=include_providers)
    except Exception as e:
        print(f"Error in search_by_committee_endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def search_by_committee(query, include_providers=False):
    """
    Reverse lookup: committee -> donors -> nursing home owners -> facilities.
    Returns: committee_info, owners, providers (if include_providers), raw_contributions.
    Providers are expensive; fetch on demand via include_providers=1.
    """
    global committee_master, owners_df, ownership_raw_df, provider_info_latest_df, facility_metrics_df
    if owners_df is None or owners_df.empty:
        return jsonify({'error': 'Owners database not loaded'}), 500
    # Resolve query to committee_id
    committees = _ensure_committee_master_extended()
    committee_id = None
    committee_name = None
    committee_type = "Committee"
    query_upper = query.upper().strip()
    if query_upper.startswith("C") and len(query_upper) >= 9 and query_upper[1:].isdigit():
        committee_id = query_upper[:9] if len(query_upper) >= 9 else query_upper
        for c in committees:
            if c.get('id', '').upper() == committee_id:
                committee_name = c.get('name', '')
                committee_type = c.get('type', 'Committee')
                break
        if not committee_name and committee_master:
            committee_name = committee_master.get(committee_id, '')
    else:
        for c in committees:
            if c['name'].upper() == query_upper or query_upper in c['name'].upper():
                committee_id = c.get('id', '')
                committee_name = c.get('name', '')
                committee_type = c.get('type', 'Committee')
                break
    if not committee_id:
        return jsonify({
            'error': 'Committee not found',
            'message': f'No committee found matching "{query}". Try searching by committee name (e.g., MAGA Inc.) or committee ID (C########).'
        }), 404
    try:
        raw_donations = query_donations_by_committee(committee_id)
    except Exception as e:
        print(f"FEC API error for committee {committee_id}: {e}")
        return jsonify({'error': f'Could not fetch contributions: {str(e)}'}), 500
    if not raw_donations:
        return jsonify({
            'committee': {
                'name': committee_name or committee_id,
                'id': committee_id,
                'type': committee_type,
                'election_cycles': [],
                'total_nursing_home_linked': 0,
                'total_fec_contributions': 0,
                'total_fec_donors': 0,
            },
            'owners': [],
            'providers': [],
            'raw_contributions': [],
        })
    normalized_list = [normalize_fec_donation(r) for r in raw_donations]
    donor_to_amounts = {}
    donor_to_records = {}
    for d in normalized_list:
        name = (d.get('donor_name') or '').strip()
        if not name:
            continue
        amt = float(d.get('donation_amount') or 0)
        donor_norm = normalize_name_for_matching(name)
        if donor_norm not in donor_to_amounts:
            donor_to_amounts[donor_norm] = 0
            donor_to_records[donor_norm] = []
        donor_to_amounts[donor_norm] += amt
        donor_to_records[donor_norm].append({
            'donor_name': name,
            'amount': amt,
            'date': d.get('donation_date', ''),
            'committee_name': committee_name or committee_id,
            'committee_id': committee_id,
            'fec_link': d.get('fec_docquery_url', '') or (f"https://www.fec.gov/data/receipts/?committee_id={committee_id}" if committee_id else ''),
            'employer': d.get('employer', ''),
            'occupation': d.get('occupation', ''),
            'donor_city': d.get('donor_city', ''),
            'donor_state': d.get('donor_state', ''),
        })
    def _find_owner_row(donor_norm, lookup):
        """Match donor to owner; try name-order variants (FEC LAST,FIRST vs CMS FIRST LAST)."""
        row = lookup.get(donor_norm)
        if row is not None:
            return row
        if not donor_norm or len(donor_norm) < 4:
            return None
        parts = donor_norm.split()
        if len(parts) == 2:
            row = lookup.get(f"{parts[1]} {parts[0]}")
            if row is not None:
                return row
        if len(parts) >= 3:
            row = lookup.get(f"{parts[0]} {parts[-1]}") or lookup.get(f"{parts[-1]} {parts[0]}")
            if row is not None:
                return row
        return None

    owner_name_norm_to_row = {}
    for _, row in owners_df.iterrows():
        onorm = normalize_name_for_matching(row.get('owner_name', ''))
        oorig = normalize_name_for_matching(str(row.get('owner_name_original', '')))
        if onorm:
            owner_name_norm_to_row[onorm] = row
        if oorig and oorig != onorm:
            owner_name_norm_to_row[oorig] = row
    owner_to_total = {}
    owner_to_count = {}
    owner_to_providers = {}
    owner_to_display = {}
    for donor_norm, total in donor_to_amounts.items():
        owner_row = _find_owner_row(donor_norm, owner_name_norm_to_row)
        if owner_row is None:
            continue
        facilities_str = owner_row.get('facilities', '') or ''
        facilities = [f.strip() for f in facilities_str.split(',') if f.strip()]
        display_name = owner_row.get('owner_name_original', owner_row.get('owner_name', ''))
        key = owner_row.get('owner_name', '')
        if key not in owner_to_total:
            owner_to_total[key] = 0
            owner_to_count[key] = 0
            owner_to_providers[key] = set()
            owner_to_display[key] = display_name
        owner_to_total[key] += total
        owner_to_count[key] += len(donor_to_records.get(donor_norm, []))
        for fac in facilities:
            owner_to_providers[key].add(fac)
    owners_deduped = [
        {
            'owner_name': owner_to_display[k],
            'owner_name_normalized': k,
            'total_contributed': owner_to_total[k],
            'num_contributions': owner_to_count[k],
            'linked_providers_count': len(owner_to_providers[k]),
        }
        for k in owner_to_total
    ]
    owners_deduped.sort(key=lambda x: -x['total_contributed'])
    providers_result = _compute_providers_from_owners(owners_deduped) if include_providers else []
    raw_contributions = []
    for donor_norm, recs in donor_to_records.items():
        if _find_owner_row(donor_norm, owner_name_norm_to_row) is None:
            continue
        for r in recs:
            raw_contributions.append(r)
    raw_contributions.sort(key=lambda x: (x.get('date', ''), -(x.get('amount', 0))), reverse=True)
    total_nursing_linked = sum(o['total_contributed'] for o in owners_deduped)
    total_fec = sum(donor_to_amounts.values()) if donor_to_amounts else 0
    return jsonify({
        'committee': {
            'name': committee_name or committee_id,
            'id': committee_id,
            'type': committee_type,
            'election_cycles': [],
            'total_nursing_home_linked': round(total_nursing_linked, 2),
            'total_fec_contributions': len(normalized_list),
            'total_fec_donors': len(donor_to_amounts),
            'total_fec_amount': round(total_fec, 2),
        },
        'owners': owners_deduped,
        'providers': providers_result,
        'raw_contributions': raw_contributions[:500],
        'raw_contributions_total': len(raw_contributions),
    })


def search_by_provider(query):
    """Search for owners by provider name, CCN, or Legal Business Name"""
    try:
        print(f"[DEBUG] search_by_provider: query='{query}'")
        query_upper = query.upper().strip()
        
        # Check if query is a CCN (6 digits, possibly with leading zeros or 'O' prefix)
        query_clean = query.replace('O', '').replace('o', '').replace(' ', '').replace('-', '').strip()
        is_ccn_search = query_clean.isdigit() and len(query_clean) <= 6
        print(f"[DEBUG] is_ccn_search={is_ccn_search}, query_clean='{query_clean}'")
        
        matched_providers = pd.DataFrame()
        matched_org_names = set()
        
        # Search in provider_info_latest_df
        if provider_info_latest_df is not None and not provider_info_latest_df.empty:
            # Search by CCN if it looks like a CCN
            if is_ccn_search:
                ccn_normalized = query_clean.zfill(6)
                ccn_col = None
                for col in ['CMS Certification Number (CCN)', 'ccn', 'CCN', 'PROVNUM']:
                    if col in provider_info_latest_df.columns:
                        ccn_col = col
                        break
                
                if ccn_col:
                    matched_providers = provider_info_latest_df[
                        provider_info_latest_df[ccn_col].astype(str).str.replace('O', '').str.replace(' ', '').str.replace('-', '').str.strip().str.zfill(6) == ccn_normalized
                    ]
            
            # Search by Provider Name (also search Legal Business Name at the same time)
            if matched_providers.empty and 'Provider Name' in provider_info_latest_df.columns:
                # Search Provider Name
                provider_name_matches = provider_info_latest_df[
                    provider_info_latest_df['Provider Name'].astype(str).str.upper().str.contains(query_upper, na=False, regex=False)
                ]
                matched_providers = pd.concat([matched_providers, provider_name_matches]).drop_duplicates()
            
            # Search by Legal Business Name (even if Provider Name matched, also search this)
            if 'Legal Business Name' in provider_info_latest_df.columns:
                # Try exact match first
                legal_name_matches = provider_info_latest_df[
                    provider_info_latest_df['Legal Business Name'].astype(str).str.upper().str.strip() == query_upper
                ]
                matched_providers = pd.concat([matched_providers, legal_name_matches]).drop_duplicates()
                
                # Try partial match (remove common suffixes)
                name_clean = query_upper.replace(' LLC', '').replace(' INC', '').replace(' CORP', '').replace(' LP', '').replace(' L.L.C.', '').replace(' INC.', '').replace(' REHABILITATION', ' REHAB').replace(' REHAB', ' REHABILITATION').strip()
                legal_name_matches = provider_info_latest_df[
                    provider_info_latest_df['Legal Business Name'].astype(str).str.upper().str.strip().str.replace(' LLC', '').str.replace(' INC', '').str.replace(' CORP', '').str.replace(' LP', '').str.replace(' L.L.C.', '').str.replace(' INC.', '').str.replace(' REHABILITATION', ' REHAB').str.replace(' REHAB', ' REHABILITATION').str.strip() == name_clean
                ]
                matched_providers = pd.concat([matched_providers, legal_name_matches]).drop_duplicates()
                
                # Try fuzzy matching
                name_fuzzy = query_upper.replace(',', '').replace('.', '').replace('-', ' ').replace('  ', ' ').replace('  ', ' ').strip()
                legal_name_matches = provider_info_latest_df[
                    provider_info_latest_df['Legal Business Name'].astype(str).str.upper().str.replace(',', '').str.replace('.', '').str.replace('-', ' ').str.replace('  ', ' ').str.replace('  ', ' ').str.strip() == name_fuzzy
                ]
                matched_providers = pd.concat([matched_providers, legal_name_matches]).drop_duplicates()
                
                # Try contains match
                legal_name_matches = provider_info_latest_df[
                    provider_info_latest_df['Legal Business Name'].astype(str).str.upper().str.contains(query_upper, na=False, regex=False)
                ]
                matched_providers = pd.concat([matched_providers, legal_name_matches]).drop_duplicates()
        
        if matched_providers.empty:
            print(f"[DEBUG] No providers found for query '{query}'")
            return jsonify({'results': [], 'count': 0, 'message': 'No provider found matching the search query'})
        
        print(f"[DEBUG] Found {len(matched_providers)} matched providers")
        
        # Get Legal Business Names from matched providers
        if 'Legal Business Name' in matched_providers.columns:
            legal_business_names = matched_providers['Legal Business Name'].dropna().unique()
            print(f"[DEBUG] Legal Business Names found: {list(legal_business_names)[:3]}")
            for lbn in legal_business_names:
                if pd.notna(lbn) and str(lbn).strip():
                    matched_org_names.add(str(lbn).strip().upper())
        
        # Also try matching via facility_name_mapping_df if available
        if facility_name_mapping_df is not None and not facility_name_mapping_df.empty:
            for _, provider_row in matched_providers.iterrows():
                # Get CCN from provider
                ccn_val = None
                for col in ['CMS Certification Number (CCN)', 'ccn', 'CCN', 'PROVNUM']:
                    if col in provider_row.index and pd.notna(provider_row.get(col)):
                        ccn_val = str(provider_row.get(col)).strip().replace('O', '').replace(' ', '').replace('-', '')
                        if ccn_val and ccn_val.isdigit() and len(ccn_val) <= 6:
                            ccn_val = ccn_val.zfill(6)
                            break
                
                if ccn_val:
                    # Find organization name in mapping
                    mapping_matches = facility_name_mapping_df[
                        facility_name_mapping_df['CCN'].astype(str).str.replace('O', '').str.replace(' ', '').str.replace('-', '').str.strip().str.zfill(6) == ccn_val
                    ]
                    if not mapping_matches.empty and 'ORGANIZATION NAME' in mapping_matches.columns:
                        org_names = mapping_matches['ORGANIZATION NAME'].dropna().unique()
                        for org_name in org_names:
                            if pd.notna(org_name) and str(org_name).strip():
                                matched_org_names.add(str(org_name).strip().upper())
        
        # Also try to get organization names from ownership data if available
        # Use raw ownership file for better matching
        ownership_data_to_search = ownership_raw_df if ownership_raw_df is not None and not ownership_raw_df.empty else ownership_df
        
        if ownership_data_to_search is not None and not ownership_data_to_search.empty:
            # Get CCNs from matched providers
            matched_ccns = set()
            for _, provider_row in matched_providers.iterrows():
                for col in ['CMS Certification Number (CCN)', 'ccn', 'CCN', 'PROVNUM']:
                    if col in provider_row.index and pd.notna(provider_row.get(col)):
                        ccn_val = str(provider_row.get(col)).strip().replace('O', '').replace(' ', '').replace('-', '')
                        if ccn_val and ccn_val.isdigit() and len(ccn_val) <= 6:
                            matched_ccns.add(ccn_val.zfill(6))
                            break
            
            # Find organization names in ownership data by CCN (enrollment ID)
            if matched_ccns and 'ENROLLMENT ID' in ownership_data_to_search.columns:
                for ccn in matched_ccns:
                    ownership_matches = ownership_data_to_search[
                        ownership_data_to_search['ENROLLMENT ID'].astype(str).str.replace('O', '').str.replace(' ', '').str.replace('-', '').str.strip().str.zfill(6) == ccn.zfill(6)
                    ]
                    if not ownership_matches.empty and 'ORGANIZATION NAME' in ownership_matches.columns:
                        org_names = ownership_matches['ORGANIZATION NAME'].dropna().unique()
                        for org_name in org_names:
                            if pd.notna(org_name) and str(org_name).strip():
                                matched_org_names.add(str(org_name).strip().upper())
            
            # Also match Legal Business Name directly to ORGANIZATION NAME (case-insensitive, with fuzzy matching)
            if 'Legal Business Name' in matched_providers.columns:
                for _, provider_row in matched_providers.iterrows():
                    legal_business_name = provider_row.get('Legal Business Name', '')
                    if pd.notna(legal_business_name) and str(legal_business_name).strip():
                        lbn_upper = str(legal_business_name).strip().upper()
                        # Try exact match
                        org_matches = ownership_data_to_search[
                            ownership_data_to_search['ORGANIZATION NAME'].astype(str).str.upper().str.strip() == lbn_upper
                        ]
                        if not org_matches.empty:
                            org_names = org_matches['ORGANIZATION NAME'].dropna().unique()
                            for org_name in org_names:
                                if pd.notna(org_name) and str(org_name).strip():
                                    matched_org_names.add(str(org_name).strip().upper())
                        else:
                            # Try fuzzy match (remove common suffixes)
                            lbn_clean = lbn_upper.replace(' LLC', '').replace(' INC', '').replace(' CORP', '').replace(' LP', '').replace(' L.L.C.', '').replace(' INC.', '').strip()
                            org_matches = ownership_data_to_search[
                                ownership_data_to_search['ORGANIZATION NAME'].astype(str).str.upper().str.strip().str.replace(' LLC', '').str.replace(' INC', '').str.replace(' CORP', '').str.replace(' LP', '').str.replace(' L.L.C.', '').str.replace(' INC.', '').str.strip() == lbn_clean
                            ]
                            if not org_matches.empty:
                                org_names = org_matches['ORGANIZATION NAME'].dropna().unique()
                                for org_name in org_names:
                                    if pd.notna(org_name) and str(org_name).strip():
                                        matched_org_names.add(str(org_name).strip().upper())
                            else:
                                # Try contains match
                                org_matches = ownership_data_to_search[
                                    ownership_data_to_search['ORGANIZATION NAME'].astype(str).str.upper().str.contains(lbn_upper, na=False, regex=False)
                                ]
                                if not org_matches.empty:
                                    org_names = org_matches['ORGANIZATION NAME'].dropna().unique()
                                    for org_name in org_names:
                                        if pd.notna(org_name) and str(org_name).strip():
                                            matched_org_names.add(str(org_name).strip().upper())
        
        print(f"[DEBUG] Final matched org names: {list(matched_org_names)[:5]}")
        
        # Find owners that have these organization names in their facilities
        if not matched_org_names:
            print(f"[DEBUG] No matched org names found")
            return jsonify({'results': [], 'count': 0, 'message': 'Found provider but could not match to organization name'})
        
        # Normalize matched org names for comparison (facilities field uses normalized names)
        normalized_matched_org_names = {normalize_name_for_matching(org_name) for org_name in matched_org_names}
        print(f"[DEBUG] Normalized matched org names: {list(normalized_matched_org_names)[:5]}")
        
        print(f"[DEBUG] Searching {len(owners_df)} owners for facilities matching org names")
        
        # Search owners_df for owners with matching facilities
        matching_owners = []
        seen_owner_names = set()  # Track which owners we've already added
        for _, owner_row in owners_df.iterrows():
            owner_name = owner_row.get('owner_name_original', owner_row.get('owner_name', ''))
            if owner_name in seen_owner_names:
                continue  # Skip if we've already added this owner
            
            facilities_str = owner_row.get('facilities', '') if pd.notna(owner_row.get('facilities')) else ''
            if facilities_str:
                # Facilities are already normalized (from owner_donor.py)
                facilities = [f.strip() for f in str(facilities_str).split(',') if f.strip()]
                # Check if any facility matches any of our organization names
                matched = False
                for facility in facilities:
                    # Direct match with normalized org names
                    if facility in normalized_matched_org_names:
                        matching_owners.append(owner_row)
                        seen_owner_names.add(owner_name)
                        matched = True
                        break
                    # Try fuzzy match (remove common suffixes from both sides)
                    facility_clean = normalize_name_for_matching(facility.replace(' LLC', '').replace(' INC', '').replace(' CORP', '').replace(' LP', '').replace(' L.L.C.', '').replace(' INC.', ''))
                    for org_name in normalized_matched_org_names:
                        org_clean = normalize_name_for_matching(org_name.replace(' LLC', '').replace(' INC', '').replace(' CORP', '').replace(' LP', '').replace(' L.L.C.', '').replace(' INC.', ''))
                        if facility_clean == org_clean:
                            matching_owners.append(owner_row)
                            seen_owner_names.add(owner_name)
                            matched = True
                            break
                    if matched:
                        break
        
        if not matching_owners:
            return jsonify({'results': [], 'count': 0, 'message': f'Found provider but no owners found for: {", ".join(list(matched_org_names)[:3])}'})
        
        # Deduplicate owners (keep first occurrence)
        seen_owners = set()
        unique_owners = []
        for owner_row in matching_owners:
            owner_name = owner_row.get('owner_name', '')
            if owner_name and owner_name not in seen_owners:
                seen_owners.add(owner_name)
                unique_owners.append(owner_row)
        
        # Get provider info for the response (use first matched provider)
        provider_info = None
        direct_owners = []  # List of direct owners with percentages
        
        if not matched_providers.empty:
            first_provider = matched_providers.iloc[0]
            provider_name = first_provider.get('Provider Name', '')
            ccn = None
            state = None
            for col in ['CMS Certification Number (CCN)', 'ccn', 'CCN', 'PROVNUM']:
                if col in first_provider.index and pd.notna(first_provider.get(col)):
                    ccn_val = str(first_provider.get(col)).strip().replace('O', '').replace(' ', '').replace('-', '')
                    if ccn_val and ccn_val.isdigit() and len(ccn_val) <= 6:
                        ccn = ccn_val.zfill(6)
                        break
            for col in ['State', 'STATE', 'state', 'Provider State']:
                if col in first_provider.index and pd.notna(first_provider.get(col)):
                    state = str(first_provider.get(col)).strip()
                    if state:
                        break
            
            # Get direct ownership information from ownership_raw_df
            # Match by ORGANIZATION NAME (which we already found in matched_org_names)
            if ownership_raw_df is not None and not ownership_raw_df.empty and matched_org_names:
                # Find ENROLLMENT IDs for the matched organization names
                enrollment_matches = pd.DataFrame()
                for org_name in matched_org_names:
                    org_matches = ownership_raw_df[
                        ownership_raw_df['ORGANIZATION NAME'].astype(str).str.upper().str.strip() == org_name
                    ]
                    if not org_matches.empty:
                        enrollment_matches = pd.concat([enrollment_matches, org_matches]).drop_duplicates()
                
                # If no matches by org name, try by CCN in ENROLLMENT ID
                if enrollment_matches.empty and ccn:
                    ccn_normalized = ccn.zfill(6)
                    # Try matching ENROLLMENT ID that ends with CCN
                    enrollment_matches = ownership_raw_df[
                        ownership_raw_df['ENROLLMENT ID'].astype(str).str.replace('O', '').str.replace('o', '').str.strip().str[-6:] == ccn_normalized
                    ]
                
                if not enrollment_matches.empty:
                    # Get ALL owners (not just 5%+)
                    # Filter for direct ownership (ROLE CODE 34 or similar)
                    direct_ownership = enrollment_matches[
                        (enrollment_matches['ROLE CODE - OWNER'].astype(str) == '34') |
                        (enrollment_matches['ROLE TEXT - OWNER'].astype(str).str.contains('DIRECT OWNERSHIP', na=False, case=False))
                    ]
                    
                    if not direct_ownership.empty:
                        # Group by owner name and get the highest percentage and earliest date
                        owner_data = {}
                        for _, row in direct_ownership.iterrows():
                            # Build owner name
                            first_name = str(row.get('FIRST NAME - OWNER', '')).strip()
                            middle_name = str(row.get('MIDDLE NAME - OWNER', '')).strip()
                            last_name = str(row.get('LAST NAME - OWNER', '')).strip()
                            
                            # Skip if no name
                            if not last_name or last_name == 'nan':
                                continue
                            
                            # Build full name
                            name_parts = [first_name, middle_name, last_name]
                            full_name = ' '.join([p for p in name_parts if p and p != 'nan']).strip().upper()
                            
                            # Get percentage
                            try:
                                percentage = float(row.get('PERCENTAGE OWNERSHIP', 0) or 0)
                            except (ValueError, TypeError):
                                percentage = 0
                            
                            # Skip if percentage is 0 or missing
                            if percentage <= 0:
                                continue
                            
                            # Get association date
                            assoc_date = str(row.get('ASSOCIATION DATE - OWNER', '')).strip()
                            
                            # If we already have this owner, keep the one with higher percentage
                            if full_name not in owner_data or percentage > owner_data[full_name]['percentage']:
                                owner_data[full_name] = {
                                    'name': full_name,
                                    'percentage': percentage,
                                    'date': assoc_date
                                }
                        
                        # Separate into >=5% and <5%, then sort each by percentage (descending)
                        owners_5plus = []
                        owners_under5 = []
                        for owner in owner_data.values():
                            if owner['percentage'] >= 5:
                                owners_5plus.append(owner)
                            else:
                                owners_under5.append(owner)
                        
                        # Sort both lists by percentage (descending)
                        owners_5plus = sorted(owners_5plus, key=lambda x: x['percentage'], reverse=True)
                        owners_under5 = sorted(owners_under5, key=lambda x: x['percentage'], reverse=True)
                        
                        # Combine: 5%+ first, then <5%
                        direct_owners = owners_5plus + owners_under5
                        print(f"[DEBUG] Found {len(direct_owners)} direct owners for CCN {ccn} ({len(owners_5plus)} >=5%, {len(owners_under5)} <5%)")
            
            provider_info = {
                'provider_name': provider_name if pd.notna(provider_name) else '',
                'ccn': ccn,
                'state': state,
                'direct_owners': direct_owners  # List of {name, percentage, date}
            }
        
        # Format results
        formatted = []
        for owner_row in unique_owners:
            facilities_str = owner_row.get('facilities', '') if pd.notna(owner_row.get('facilities')) else ''
            facilities = [f.strip() for f in facilities_str.split(',') if f.strip()] if facilities_str else []
            
            enrollment_ids_str = owner_row.get('enrollment_ids', '') if pd.notna(owner_row.get('enrollment_ids')) else ''
            enrollment_ids = [e.strip() for e in enrollment_ids_str.split(',') if e.strip()] if enrollment_ids_str else []
            
            owner_name_display = owner_row.get('owner_name_original', owner_row.get('owner_name', ''))
            
            formatted.append({
                'owner_name': owner_name_display,
                'owner_name_normalized': owner_row.get('owner_name', ''),
                'owner_type': owner_row.get('owner_type', 'UNKNOWN'),
                'facilities': facilities,
                'num_facilities': len(facilities),
                'enrollment_ids': enrollment_ids,
                'is_equity_owner': owner_row.get('is_equity_owner', False) if 'is_equity_owner' in owner_row else False,
                'is_officer': owner_row.get('is_officer', False) if 'is_officer' in owner_row else False,
                'earliest_association': owner_row.get('earliest_association', '') if 'earliest_association' in owner_row else ''
            })
        
        return jsonify({
            'results': formatted, 
            'count': len(formatted),
            'provider_info': provider_info  # Include provider info for display
        })
    
    except Exception as e:
        print(f"Error in search_by_provider: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/owner/<owner_name>')
def get_owner_details(owner_name):
    """Get detailed information about a specific owner"""
    if owners_df is None:
        return jsonify({'error': 'Owners database not loaded'}), 500
    
    query_upper = owner_name.upper().strip()
    # Find owner - prioritize normalized name (more reliable)
    owner = owners_df[owners_df['owner_name'].str.upper().str.strip() == query_upper]
    if owner.empty:
        owner = owners_df[owners_df['owner_name_original'].astype(str).str.upper().str.strip() == query_upper]
    
    # Fallback: entity view sends "FIRST LAST" but DB may have "LAST, FIRST" or "LAST FIRST"
    if owner.empty and query_upper:
        def name_col_match(col, val):
            return owners_df[col].fillna('').astype(str).str.upper().str.strip() == val.upper()
        parts = query_upper.split()
        if len(parts) == 2:
            for alt in (f"{parts[1]} {parts[0]}", f"{parts[1]}, {parts[0]}"):
                owner = owners_df[name_col_match('owner_name', alt)]
                if not owner.empty:
                    break
                owner = owners_df[name_col_match('owner_name_original', alt)]
                if not owner.empty:
                    break
        elif len(parts) >= 3:
            alt1 = f"{parts[-1]} {' '.join(parts[:-1])}".strip()
            alt2 = f"{parts[-1]}, {' '.join(parts[:-1])}".strip()
            for alt in (alt1, alt2):
                owner = owners_df[name_col_match('owner_name', alt)]
                if not owner.empty:
                    break
                owner = owners_df[name_col_match('owner_name_original', alt)]
                if not owner.empty:
                    break
    
    if owner.empty:
        return jsonify({'error': 'Owner not found'}), 404
    
    owner_row = owner.iloc[0]
    
    # Use normalized name for display if it matches the query, otherwise use original
    display_name = owner_row.get('owner_name', owner_name)
    if owner_name.upper() not in display_name.upper():
        # If normalized name doesn't match, try original
        orig_name = owner_row.get('owner_name_original', '')
        if orig_name and owner_name.upper() in orig_name.upper():
            display_name = orig_name
        # Otherwise keep normalized name (it's more reliable)
    
    # Get facilities (use comma split + strip to match rest of codebase and handle "A,B" or "A, B")
    facilities = []
    if pd.notna(owner_row['facilities']):
        facility_names = [f.strip() for f in owner_row['facilities'].split(',') if f.strip()]
        enrollment_ids_str = owner_row.get('enrollment_ids', '')
        enrollment_ids = [e.strip() for e in enrollment_ids_str.split(',') if e.strip()] if pd.notna(enrollment_ids_str) else []
        
        for i, name in enumerate(facility_names):
            facility_info = {'name': name.strip()}
            if i < len(enrollment_ids):
                facility_info['enrollment_id'] = enrollment_ids[i].strip()
            
            # Get provider info if available - MATCH Legal Business Name with ORGANIZATION NAME
            prov_info = pd.DataFrame()
            matched = False
            
            # FIRST: Try pre-computed mapping (FASTEST)
            if facility_name_mapping_df is not None and not facility_name_mapping_df.empty:
                normalized_facility_name = str(name.strip()).upper().strip()
                mapping_match = facility_name_mapping_df[
                    facility_name_mapping_df['ORGANIZATION NAME'].astype(str).str.upper().str.strip() == normalized_facility_name
                ]
                if not mapping_match.empty:
                    # Get CCN from mapping and look up in provider_info_latest_df
                    try:
                        mapping_row = mapping_match.iloc[0]
                        if mapping_row is not None and hasattr(mapping_row, 'get'):
                            ccn_from_mapping = str(mapping_row.get('CCN', '')).strip().replace('O', '').replace(' ', '').replace('-', '')
                            if ccn_from_mapping and ccn_from_mapping.isdigit() and len(ccn_from_mapping) <= 6:
                                ccn_from_mapping = ccn_from_mapping.zfill(6)
                                if provider_info_latest_df is not None and not provider_info_latest_df.empty:
                                    ccn_col = 'CMS Certification Number (CCN)' if 'CMS Certification Number (CCN)' in provider_info_latest_df.columns else 'ccn'
                                    if ccn_col in provider_info_latest_df.columns:
                                        prov_info = provider_info_latest_df[
                                            provider_info_latest_df[ccn_col].astype(str).str.replace('O', '').str.replace(' ', '').str.replace('-', '').str.strip().str.zfill(6) == ccn_from_mapping
                                        ]
                                        if not prov_info.empty:
                                            matched = True
                    except Exception as e:
                        print(f"[WARNING] Error processing mapping_row for facility {name}: {e}")
                        # Continue to fallback matching
            
            # FALLBACK: Live matching using Legal Business Name (slower but works if mapping doesn't exist)
            if not matched and provider_info_latest_df is not None and not provider_info_latest_df.empty:
                # PRIMARY MATCH: Legal Business Name (provider_info_latest) with ORGANIZATION NAME (ownership file)
                if 'Legal Business Name' in provider_info_latest_df.columns:
                    normalized_facility_name = str(name.strip()).upper().strip()
                    
                    # STEP 1: Try exact match: Legal Business Name == ORGANIZATION NAME
                    prov_info = provider_info_latest_df[
                        provider_info_latest_df['Legal Business Name'].astype(str).str.upper().str.strip() == normalized_facility_name
                    ]
                    
                    # STEP 2: Try partial match if exact fails (remove common suffixes)
                    if prov_info.empty:
                        name_clean = normalized_facility_name.replace(' LLC', '').replace(' INC', '').replace(' CORP', '').replace(' LP', '').replace(' L.L.C.', '').replace(' INC.', '').strip()
                        prov_info = provider_info_latest_df[
                            provider_info_latest_df['Legal Business Name'].astype(str).str.upper().str.strip().str.replace(' LLC', '').str.replace(' INC', '').str.replace(' CORP', '').str.replace(' LP', '').str.replace(' L.L.C.', '').str.replace(' INC.', '').str.strip() == name_clean
                        ]
                    
                    # STEP 3: Try fuzzy matching - remove punctuation and extra spaces
                    if prov_info.empty:
                        # Normalize both sides: remove commas, periods, hyphens, normalize spaces
                        name_fuzzy = normalized_facility_name.replace(',', '').replace('.', '').replace('-', ' ').replace('  ', ' ').replace('  ', ' ').strip()
                        prov_info = provider_info_latest_df[
                            provider_info_latest_df['Legal Business Name'].astype(str).str.upper().str.replace(',', '').str.replace('.', '').str.replace('-', ' ').str.replace('  ', ' ').str.replace('  ', ' ').str.strip() == name_fuzzy
                        ]
                    
                    # STEP 4: Try contains match for longer names (if still empty)
                    if prov_info.empty and len(normalized_facility_name) > 10:
                        # Try matching first 15 characters
                        name_prefix = normalized_facility_name[:15]
                        prov_info = provider_info_latest_df[
                            provider_info_latest_df['Legal Business Name'].astype(str).str.upper().str.strip().str[:15] == name_prefix
                        ]
                    
                    if not prov_info.empty:
                        matched = True
            
            # ONLY use data from provider_info if we have a confirmed match
            if matched and not prov_info.empty:
                try:
                    row = prov_info.iloc[0]
                    # Defensive check: ensure row is not None and is a valid Series
                    if row is None or not hasattr(row, 'get'):
                        print(f"[WARNING] Invalid row from prov_info for facility {name}")
                        matched = False
                    else:
                        # Get state/city - handle both provider_info_combined.csv and NH_ProviderInfo_Dec2025.csv column names
                        facility_info['state'] = row.get('State', row.get('state', '')) if 'State' in row.index or 'state' in row.index else ''
                        facility_info['city'] = row.get('City/Town', row.get('City', row.get('city', ''))) if any(col in row.index for col in ['City/Town', 'City', 'city']) else ''
                        facility_info['beds'] = row.get('Average Number of Residents per Day', row.get('Number of Certified Beds', row.get('avg_residents_per_day', ''))) if any(col in row.index for col in ['Average Number of Residents per Day', 'Number of Certified Beds', 'avg_residents_per_day']) else ''
                        facility_info['rating'] = row.get('Overall Rating', row.get('overall_rating', '')) if any(col in row.index for col in ['Overall Rating', 'overall_rating']) else ''
                        facility_info['staffing_rating'] = row.get('Staffing Rating', row.get('staffing_rating', '')) if any(col in row.index for col in ['Staffing Rating', 'staffing_rating']) else ''
                        facility_info['health_rating'] = row.get('Health Inspection Rating', row.get('health_inspection_rating', '')) if any(col in row.index for col in ['Health Inspection Rating', 'health_inspection_rating']) else ''
                        facility_info['ownership_type'] = row.get('Ownership Type', row.get('ownership_type', '')) if any(col in row.index for col in ['Ownership Type', 'ownership_type']) else ''
                        
                        # Store Legal Business Name from provider_info (confirmed match)
                        facility_info['legal_business_name'] = row.get('Legal Business Name', '') if 'Legal Business Name' in row.index else ''
                        
                        # Store Provider Name from provider_info (confirmed match)
                        facility_info['provider_name'] = row.get('Provider Name', '') if 'Provider Name' in row.index else ''
                        
                        # Get CCN from provider_info (NOT from enrollment ID - they're different!)
                        ccn_col = None
                        for col in ['CMS Certification Number (CCN)', 'ccn', 'CCN', 'PROVNUM']:
                            if col in row.index and pd.notna(row.get(col)):
                                ccn_val = str(row.get(col)).strip().replace('O', '').replace(' ', '').replace('-', '')
                                # Only use if it's a valid numeric CCN (6 digits)
                                if ccn_val and ccn_val.isdigit() and len(ccn_val) <= 6:
                                    facility_info['ccn'] = ccn_val.zfill(6)
                                    break
                        if 'ccn' not in facility_info:
                            facility_info['ccn'] = None
                except Exception as e:
                    print(f"[ERROR] Error processing provider info row for facility {name}: {e}")
                    import traceback
                    traceback.print_exc()
                    matched = False
                
                # Get entity ID for linking (only if we have a match)
                entity_id = None
                for col in ['Chain ID', 'chain_id', 'Chain_ID', 'Entity ID', 'entity_id', 'affiliated_entity_id']:
                    if col in row.index and pd.notna(row.get(col)):
                        try:
                            entity_id = str(int(float(str(row.get(col)))))
                            break
                        except (ValueError, TypeError):
                            continue
                facility_info['entity_id'] = entity_id
            else:
                # NO MATCH FOUND - Only use what we have from ownership file
                # DO NOT default to Legal Business Name or enrollment ID
                facility_info['legal_business_name'] = name.strip()  # This is the ORGANIZATION NAME from ownership file
                facility_info['provider_name'] = name.strip()  # This is the ORGANIZATION NAME from ownership file
                facility_info['ccn'] = None  # No CCN - no match found
                facility_info['entity_id'] = None
                # Leave other fields empty (state, city, beds, rating, etc.) - no match means no data
            
            # Get performance metrics if available (use CCN from provider_info, not enrollment ID)
            global facility_metrics_df
            if facility_metrics_df is not None and not facility_metrics_df.empty and facility_info.get('ccn'):
                provnum = facility_info['ccn']
                if 'PROVNUM' in facility_metrics_df.columns:
                    metrics = facility_metrics_df[facility_metrics_df['PROVNUM'].astype(str).str.zfill(6) == provnum.zfill(6)]
                    if not metrics.empty:
                        # Get latest quarter data
                        latest = metrics.iloc[-1] if len(metrics) > 0 else None
                        if latest is not None:
                            # Handle both CY_QTR and CY_Qtr column names
                            facility_info['latest_quarter'] = latest.get('CY_Qtr', latest.get('CY_QTR', ''))
                            # Get HPRD - handle both string and numeric types
                            hprd_val = latest.get('Total_Nurse_HPRD', '')
                            if pd.notna(hprd_val) and hprd_val != '':
                                try:
                                    facility_info['avg_hprd'] = float(hprd_val)
                                except (ValueError, TypeError):
                                    facility_info['avg_hprd'] = ''
                            else:
                                facility_info['avg_hprd'] = ''
                            facility_info['contract_pct'] = latest.get('Contract_Percentage', '')
                            facility_info['avg_census'] = latest.get('Census', '')
            
            facilities.append(facility_info)
    
    # Get donations from pre-processed database (FAST)
    # NOTE: This does NOT call FEC API - just loads previously queried donations
    # FEC API is only called via /api/query-fec endpoint (when user clicks "Query FEC API (Live)" button)
    donations = []
    if donations_df is not None and not donations_df.empty:
        # Match by normalized owner name or original name
        owner_donations = donations_df[
            (donations_df['owner_name'] == owner_row['owner_name']) |
            (donations_df['owner_name_original'] == owner_row['owner_name_original'])
        ]
        if not owner_donations.empty:
            for _, d in owner_donations.iterrows():
                try:
                    donation_amt = d.get('donation_amount', 0)
                    if pd.notna(donation_amt) and donation_amt != '':
                        amount = float(str(donation_amt))
                    else:
                        amount = 0.0
                except (ValueError, TypeError):
                    amount = 0.0
                # Fix corrupted dates (2033, 2034, 2035 etc. - likely Excel corruption)
                date_str = str(d.get('donation_date', '')).strip()
                if date_str:
                    # Check if year is in the future (likely corrupted)
                    import re
                    year_match = re.match(r'^(\d{4})-', date_str)
                    if year_match:
                        year = int(year_match.group(1))
                        # If year is 2030-2040, it's likely corrupted (subtract 10 years)
                        # This fixes Excel's common date corruption issue
                        if 2030 <= year <= 2040:
                            # Try to fix by subtracting 10 years (common Excel corruption)
                            fixed_year = year - 10
                            date_str = date_str.replace(f'{year}-', f'{fixed_year}-', 1)
                            print(f"[FIXED] Corrected date from {year_match.group(0)} to {fixed_year}-{date_str.split('-', 1)[1] if '-' in date_str else ''}")
                
                # FEC docquery link: use file_number (e.g. 1930534) from Schedule A. Stored or from /filings/.
                fec_link = (d.get('fec_docquery_url') or '').strip()
                if fec_link and not is_valid_docquery_schedule_a_url(fec_link):
                    fec_link = ""
                if not fec_link and d.get('committee_id'):
                    file_num = d.get('fec_file_number') or None
                    if file_num:
                        result = build_schedule_a_docquery_link(committee_id=d.get('committee_id'), image_number=file_num)
                        fec_link = result.get('url', '').strip() if result.get('image_number') else ""
                    elif d.get('donation_date'):
                        result = build_schedule_a_docquery_link(
                            committee_id=d.get('committee_id'),
                            schedule_a_record={"contribution_receipt_date": d.get('donation_date')},
                        )
                        fec_link = result.get('url', '').strip() if result.get('image_number') else ""
                committee_display = get_committee_display_name(d.get('committee_id'), d.get('committee_name', '')) or d.get('committee_name', '')
                donations.append({
                    'amount': amount,
                    'date': date_str,
                    'committee': committee_display,
                    'committee_id': d.get('committee_id', ''),
                    'candidate': d.get('candidate_name', ''),
                    'office': d.get('candidate_office', ''),
                    'party': d.get('candidate_party', ''),
                    'employer': d.get('employer', ''),
                    'occupation': d.get('occupation', ''),
                    'donor_city': d.get('donor_city', ''),
                    'donor_state': d.get('donor_state', ''),
                    'fec_link': fec_link,
                })
    
    # Calculate portfolio summary
    portfolio_summary = {
        'total_facilities': len(facilities),
        'states': list(set([f.get('state', '') for f in facilities if f.get('state')])),
        'avg_rating': None,
        'facilities_with_ratings': 0,
        'total_beds': 0
    }
    
    ratings = [float(f.get('rating', 0)) for f in facilities if f.get('rating') and str(f.get('rating')).replace('.', '').isdigit()]
    if ratings:
        portfolio_summary['avg_rating'] = sum(ratings) / len(ratings)
        portfolio_summary['facilities_with_ratings'] = len(ratings)
    
    beds = [float(f.get('beds', 0)) for f in facilities if f.get('beds') and str(f.get('beds')).replace('.', '').isdigit()]
    if beds:
        portfolio_summary['total_beds'] = sum(beds)
    
    # Sort donations by date (most recent first)
    donations.sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)
    
    response_data = {
        'owner_name': display_name,
        'owner_type': owner_row['owner_type'],
        'facilities': facilities,
        'portfolio_summary': portfolio_summary,
        'donations': donations,
        'total_donated': sum(d['amount'] for d in donations),
        'donation_count': len(donations),
        'has_preprocessed_donations': len(donations) > 0,
        'is_equity_owner': owner_row.get('is_equity_owner', False) if 'is_equity_owner' in owner_row else False,
        'is_officer': owner_row.get('is_officer', False) if 'is_officer' in owner_row else False,
        'earliest_association': owner_row.get('earliest_association', '') if 'earliest_association' in owner_row else ''
    }
    return jsonify(sanitize_for_json(response_data))


@app.route('/api/query-fec', methods=['POST'])
def query_fec():
    """
    Query FEC API for a specific owner (live query) with multiple strategies
    
    THIS IS THE ONLY PLACE FEC API IS CALLED.
    Called on-demand when user clicks "Query FEC API (Live)" button.
    NOT called during initial load or when viewing owner details.
    """
    try:
        # Handle both direct requests and proxied requests
        if request.is_json:
            data = request.json
        else:
            # Try to parse JSON from raw data
            try:
                data = json.loads(request.get_data(as_text=True))
            except:
                return jsonify({'error': 'Invalid JSON in request body'}), 400
        
        if not data:
            return jsonify({'error': 'Request body required'}), 400
            
        owner_name = data.get('owner_name', '').strip()
        owner_type = data.get('owner_type', 'ORGANIZATION')
        
        if not owner_name:
            return jsonify({'error': 'Owner name required'}), 400
    except Exception as e:
        print(f"Error parsing request in query_fec: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error parsing request: {str(e)}'}), 400
    
    try:
        all_donations = []
        
        # Generate name variations for comprehensive search
        name_variations = normalize_name_for_search(owner_name)
        name_variations.append(owner_name.upper())  # Add original
        
        # Determine FEC API contributor type
        fec_type = "individual" if owner_type == "INDIVIDUAL" else None
        
        # Query with each name variation
        seen_ids = set()
        for name_var in name_variations[:5]:  # Limit to 5 variations to avoid rate limits
            try:
                donations = query_donations_by_name(
                    contributor_name=name_var,
                    contributor_type=fec_type,
                    per_page=100
                )
                
                # Deduplicate by sub_id
                if donations:  # Ensure donations is not None
                    for donation in donations:
                        if donation and isinstance(donation, dict):  # Safety check
                            record_id = donation.get('sub_id')
                            if record_id and record_id not in seen_ids:
                                seen_ids.add(record_id)
                                all_donations.append(donation)
            except Exception as e:
                # Continue with next variation if one fails
                continue
        
        # Also try by employer/occupation if individual
        if owner_type == "INDIVIDUAL" and len(all_donations) < 10:
            # Try searching by employer if we have that info
            try:
                # Query by employer (if owner has facilities, search by facility names as employer)
                # This is a fallback strategy
                pass  # Can implement later if needed
            except:
                pass
        
        # Normalize all donations; filter out FEC fuzzy-match false positives
        normalized = []
        for donation in all_donations:
            if not donation or not isinstance(donation, dict):
                continue  # Skip invalid donations
            try:
                norm = normalize_fec_donation(donation)
                if not norm or not isinstance(norm, dict):
                    continue  # Skip if normalization failed
                # Exclude false positives: FEC fuzzy matching can return CAPITAL ONE when
                # searching CORPORATE INTERFACE; require contributor to plausibly match owner
                donor_name_fec = norm.get('donor_name', '') or donation.get('contributor_name', '')
                if not _fec_contributor_matches_owner(donor_name_fec, owner_name, owner_type):
                    continue  # Skip - likely wrong entity
                # Get and validate date
                date_str = str(norm.get('donation_date', '') or '').strip()
                # Check for corrupted dates (2030-2040 range - likely should be 2020-2030)
                if date_str:
                    import re
                    year_match = re.match(r'^(\d{4})-', date_str)
                    if year_match:
                        year = int(year_match.group(1))
                        # If year is 2030-2040, it's likely corrupted (subtract 10 years)
                        if 2030 <= year <= 2040:
                            fixed_year = year - 10
                            date_str = date_str.replace(f'{year}-', f'{fixed_year}-', 1)
                            print(f"[FIXED DATE] Corrected {year_match.group(0)} to {fixed_year}-{date_str.split('-', 1)[1] if '-' in date_str else ''} for {owner_name}")
                
                committee_display = get_committee_display_name(norm.get('committee_id'), norm.get('committee_name', '') or '') or norm.get('committee_name', '') or ''
                fec_link = norm.get('fec_docquery_url', '') or ''
                if (not fec_link or fec_link.startswith("https://www.fec.gov/data/receipts")) and norm.get("committee_id") and date_str:
                    result = build_schedule_a_docquery_link(
                        committee_id=norm.get("committee_id"),
                        schedule_a_record={"contribution_receipt_date": date_str, "committee_id": norm.get("committee_id")},
                    )
                    if result.get("image_number"):
                        fec_link = result.get("url", "")
                normalized.append({
                    'amount': float(norm.get('donation_amount', 0)) if norm.get('donation_amount') and pd.notna(norm.get('donation_amount')) else 0,
                    'date': date_str,
                    'committee': committee_display,
                    'committee_id': norm.get('committee_id', '') or '',
                    'candidate': norm.get('candidate_name', '') or '',
                    'office': norm.get('candidate_office', '') or '',
                    'party': norm.get('candidate_party', '') or '',
                    'employer': norm.get('employer', '') or '',
                    'occupation': norm.get('occupation', '') or '',
                    'donor_city': norm.get('donor_city', '') or '',
                    'donor_state': norm.get('donor_state', '') or '',
                    'fec_link': fec_link,
                    'donor_name': norm.get('donor_name', '') or '',  # Actual FEC contributor - critical for verification
                })
            except Exception as e:
                print(f"[WARNING] Error normalizing donation: {e}")
                continue  # Skip this donation and continue
        
        # Sort by date (most recent first)
        normalized.sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)
        
        return jsonify({
            'donations': normalized,
            'total': sum(d['amount'] for d in normalized),
            'count': len(normalized),
            'searches_performed': len(name_variations)
        })
    
    except Exception as e:
        print(f"[ERROR] Error in query_fec: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/entity/<entity_id>')
def get_entity_owners(entity_id):
    """Get all owners affiliated with an entity and their donations"""
    try:
        print(f"[DEBUG] get_entity_owners: entity_id='{entity_id}'")
        if owners_df is None or owners_df.empty:
            return jsonify({'error': 'Owners database not loaded'}), 500
        
        if provider_info_df is None or provider_info_df.empty:
            return jsonify({'error': 'Provider info not loaded'}), 500
        
        if ownership_df is None or ownership_df.empty:
            return jsonify({'error': 'Ownership data not loaded'}), 500
        
        # Find entity ID column in provider info
        entity_id_col = None
        for col in ['Chain ID', 'chain_id', 'Chain_ID', 'Entity ID', 'entity_id', 'affiliated_entity_id']:
            if col in provider_info_df.columns:
                entity_id_col = col
                break
        
        if not entity_id_col:
            return jsonify({'error': 'Entity ID column not found in provider info'}), 500
        
        # Convert entity_id to float for comparison
        try:
            entity_id_float = float(str(entity_id))
        except ValueError:
            return jsonify({'error': f'Invalid entity ID: {entity_id}'}), 400
        
        # Find all facilities in this entity
        entity_facilities = provider_info_df[
            pd.to_numeric(provider_info_df[entity_id_col], errors='coerce') == entity_id_float
        ]
        
        if entity_facilities.empty:
            return jsonify({'error': f'No facilities found for entity ID: {entity_id}'}), 404
        
        # Get entity name if available
        entity_name = None
        for col in ['Chain Name', 'chain_name', 'Chain_Name', 'Entity Name', 'entity_name', 'affiliated_entity_name']:
            if col in entity_facilities.columns:
                entity_name_val = entity_facilities[col].iloc[0] if len(entity_facilities) > 0 else None
                if pd.notna(entity_name_val) and str(entity_name_val).strip().upper() not in ['NAN', 'NONE', '']:
                    entity_name = str(entity_name_val).strip()
                    break
        
        # Get CCNs of facilities in this entity
        ccn_col = None
        for col in ['ccn', 'CCN', 'CMS Certification Number (CCN)', 'PROVNUM']:
            if col in entity_facilities.columns:
                ccn_col = col
                break
        
        if not ccn_col:
            return jsonify({'error': 'CCN column not found in provider info'}), 500
        
        # Get all CCNs (normalize to 6 digits)
        facility_ccns = []
        for _, row in entity_facilities.iterrows():
            ccn_val = row.get(ccn_col)
            if pd.notna(ccn_val):
                ccn = str(ccn_val).strip().replace('O', '').zfill(6)
                facility_ccns.append(ccn)
        
        if not facility_ccns:
            return jsonify({'error': 'No valid CCNs found for entity facilities'}), 404
        
        # Find all owners of these facilities from ownership data
        # Match by ENROLLMENT ID (which should match CCN)
        # Normalize CCNs for matching (remove leading zeros, handle 'O' prefix)
        normalized_ccns = set()
        for ccn in facility_ccns:
            # Remove leading zeros and 'O' prefix
            normalized = ccn.lstrip('0')
            normalized_ccns.add(normalized)
            normalized_ccns.add(ccn)  # Also keep original
            normalized_ccns.add(f"O{ccn}")  # With O prefix
        
        # Get unique owners from owners database who own these facilities
        # Match by enrollment_ids in the owners database
        matching_owners = []
        for _, owner_row in owners_df.iterrows():
            enrollment_ids_str = owner_row.get('enrollment_ids', '')
            if pd.notna(enrollment_ids_str):
                owner_enrollments = [e.strip() for e in str(enrollment_ids_str).split(',') if e.strip()]
                # Check if any of this owner's facilities match our entity facilities
                for eid in owner_enrollments:
                    # Normalize enrollment ID for comparison
                    eid_normalized = eid.replace('O', '').lstrip('0')
                    # Check if it matches any of our entity CCNs
                    if any(eid_normalized == ccn.lstrip('0') or eid.replace('O', '').zfill(6) == ccn.zfill(6) for ccn in facility_ccns):
                        matching_owners.append(owner_row)
                        break  # Found a match, no need to check other enrollments
        
        if not matching_owners:
            return jsonify({
                'entity_id': entity_id,
                'entity_name': entity_name,
                'facility_count': len(facility_ccns),
                'owners': [],
                'total_donated': 0,
                'donation_count': 0,
                'message': 'No owners found in database for facilities in this entity'
            })
        
        # Get donations for these owners
        owners_with_donations = []
        total_donated = 0
        total_donation_count = 0
        
        for owner_row in matching_owners:
            owner_name = owner_row.get('owner_name', '')
            owner_name_original = owner_row.get('owner_name_original', owner_name)
            
            # Get donations from pre-processed database
            owner_donations = []
            if donations_df is not None and not donations_df.empty:
                owner_donations_data = donations_df[
                    (donations_df['owner_name'] == owner_name) |
                    (donations_df['owner_name_original'] == owner_name_original)
                ]
                
                for _, d in owner_donations_data.iterrows():
                    try:
                        donation_amt = d.get('donation_amount', 0)
                        if pd.notna(donation_amt) and donation_amt != '':
                            amount = float(str(donation_amt))
                        else:
                            amount = 0.0
                    except (ValueError, TypeError):
                        amount = 0.0
                    
                    # FEC docquery link: use file_number from Schedule A; else get from /filings/.
                    fec_link = (d.get('fec_docquery_url') or '').strip()
                    if fec_link and not is_valid_docquery_schedule_a_url(fec_link):
                        fec_link = ""
                    if not fec_link and d.get('committee_id'):
                        file_num = d.get('fec_file_number') or None
                        if file_num:
                            result = build_schedule_a_docquery_link(committee_id=d.get('committee_id'), image_number=file_num)
                            fec_link = result.get('url', '').strip() if result.get('image_number') else ""
                        elif d.get('donation_date'):
                            result = build_schedule_a_docquery_link(
                                committee_id=d.get('committee_id'),
                                schedule_a_record={"contribution_receipt_date": d.get('donation_date')},
                            )
                            fec_link = result.get('url', '').strip() if result.get('image_number') else ""
                    committee_display = get_committee_display_name(d.get('committee_id'), d.get('committee_name', '')) or d.get('committee_name', '')
                    owner_donations.append({
                        'amount': amount,
                        'date': d.get('donation_date', ''),
                        'committee': committee_display,
                        'committee_id': d.get('committee_id', ''),
                        'candidate': d.get('candidate_name', ''),
                        'office': d.get('candidate_office', ''),
                        'party': d.get('candidate_party', ''),
                        'employer': d.get('employer', ''),
                        'occupation': d.get('occupation', ''),
                        'donor_city': d.get('donor_city', ''),
                        'donor_state': d.get('donor_state', ''),
                        'fec_link': fec_link,
                    })
            
            owner_total = sum(d['amount'] for d in owner_donations)
            total_donated += owner_total
            total_donation_count += len(owner_donations)
            
            # Get facilities for this owner
            facilities_str = owner_row.get('facilities', '')
            facilities = [f.strip() for f in facilities_str.split(',') if f.strip()] if pd.notna(facilities_str) else []
            
            owners_with_donations.append({
                'owner_name': owner_name_original,
                'owner_name_normalized': owner_name,
                'owner_type': owner_row.get('owner_type', 'UNKNOWN'),
                'facilities': facilities,
                'num_facilities': len(facilities),
                'donations': owner_donations,
                'total_donated': owner_total,
                'donation_count': len(owner_donations)
            })
        
        # Sort by total donated (highest first)
        owners_with_donations.sort(key=lambda x: x['total_donated'], reverse=True)
        
        # Create combined donations list (all donations from all owners)
        combined_donations = []
        for owner in owners_with_donations:
            for donation in owner['donations']:
                donation_copy = donation.copy()
                donation_copy['owner_name'] = owner['owner_name']
                donation_copy['owner_type'] = owner['owner_type']
                combined_donations.append(donation_copy)
        
        # Sort combined donations by date (most recent first)
        combined_donations.sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)
        
        # Group donations by recipient for summary; keep one committee_id per committee name for links
        by_committee = {}
        by_candidate = {}
        for donation in combined_donations:
            if donation.get('committee'):
                committee = donation['committee']
                prev = by_committee.get(committee, {'total': 0, 'committee_id': ''})
                by_committee[committee] = {
                    'total': prev['total'] + donation['amount'],
                    'committee_id': prev['committee_id'] or donation.get('committee_id', ''),
                }
            if donation.get('candidate'):
                candidate_key = f"{donation['candidate']} ({donation.get('office', 'Unknown')})"
                by_candidate[candidate_key] = by_candidate.get(candidate_key, 0) + donation['amount']
        
        top_committees = sorted(
            [{'name': n, 'total': v['total'], 'committee_id': v['committee_id']} for n, v in by_committee.items()],
            key=lambda x: x['total'],
            reverse=True,
        )
        top_candidates = sorted(by_candidate.items(), key=lambda x: x[1], reverse=True)
        
        return jsonify({
            'entity_id': entity_id,
            'entity_name': entity_name,
            'facility_count': len(facility_ccns),
            'owners': owners_with_donations,
            'total_donated': total_donated,
            'donation_count': total_donation_count,
            'owner_count': len(owners_with_donations),
            'combined_donations': combined_donations,
            'top_committees': top_committees,
            'top_candidates': [{'name': name, 'total': total} for name, total in top_candidates]
        })
    
    except Exception as e:
        print(f"Error in get_entity_owners: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def get_stats():
    """Get overall statistics"""
    if owners_df is None or owners_df.empty:
        return jsonify({
            'total_owners': 0,
            'total_individuals': 0,
            'total_organizations': 0,
            'total_donations': 0,
            'total_donated': 0.0
        })
    
    total_owners = len(owners_df)
    total_individuals = len(owners_df[owners_df['owner_type'] == 'INDIVIDUAL']) if 'owner_type' in owners_df.columns else 0
    total_organizations = len(owners_df[owners_df['owner_type'] == 'ORGANIZATION']) if 'owner_type' in owners_df.columns else 0
    
    total_donations = 0
    total_donated = 0.0
    if donations_df is not None and not donations_df.empty and 'donation_amount' in donations_df.columns:
        total_donations = len(donations_df)
        try:
            numeric_series = pd.to_numeric(donations_df['donation_amount'], errors='coerce')
            sum_value = numeric_series.sum()
            if pd.notna(sum_value) and isinstance(sum_value, (int, float)):
                total_donated = float(sum_value)
            else:
                total_donated = 0.0
        except (ValueError, TypeError, AttributeError):
            total_donated = 0.0
    
    stats = {
        'total_owners': total_owners,
        'total_individuals': total_individuals,
        'total_organizations': total_organizations,
        'total_donations': total_donations,
        'total_donated': total_donated
    }
    return jsonify(stats)


if __name__ == '__main__':
    import logging
    import sys
    
    # Disable Flask's default request logging to prevent PowerShell parsing errors
    # The log format includes brackets and dashes that PowerShell interprets as commands
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    log.disabled = True
    
    print("Loading data...")
    load_data()
    print("Starting server...")
    print("Open your browser to: http://127.0.0.1:5001")
    print("Press CTRL+C to stop the server\n")
    
    # Run with request logging disabled
    app.run(debug=True, port=5001, use_reloader=False)
