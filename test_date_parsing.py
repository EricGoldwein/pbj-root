"""
Test script to understand date parsing issue
"""
import sys
from pathlib import Path

# Add donor directory to path
donor_dir = Path(__file__).parent / "donor"
if str(donor_dir) not in sys.path:
    sys.path.insert(0, str(donor_dir))

from fec_api_client import query_donations_by_name, normalize_fec_donation

# Get a sample donation
donations = query_donations_by_name('PRUITTHEALTH', per_page=1)

if donations:
    raw_donation = donations[0]
    print("=" * 60)
    print("RAW FEC API RESPONSE:")
    print("=" * 60)
    print(f"contribution_receipt_date (raw): {raw_donation.get('contribution_receipt_date', 'N/A')}")
    print(f"Type: {type(raw_donation.get('contribution_receipt_date', ''))}")
    print()
    
    # Normalize it
    normalized = normalize_fec_donation(raw_donation)
    print("=" * 60)
    print("AFTER NORMALIZATION:")
    print("=" * 60)
    print(f"donation_date: {normalized.get('donation_date', 'N/A')}")
    print(f"Type: {type(normalized.get('donation_date', ''))}")
    print()
    
    # Test JavaScript Date parsing behavior
    print("=" * 60)
    print("JAVASCRIPT DATE PARSING SIMULATION:")
    print("=" * 60)
    date_str = normalized.get('donation_date', '')
    if date_str:
        # Simulate what JavaScript new Date() would do
        print(f"Date string: '{date_str}'")
        
        # Check if it's in YYYY-MM-DD format
        import re
        match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', date_str)
        if match:
            year, month, day = match.groups()
            print(f"  Parsed as YYYY-MM-DD: Year={year}, Month={month}, Day={day}")
        else:
            print(f"  WARNING: Not in YYYY-MM-DD format!")
            # Try to see what format it might be
            if '-' in date_str:
                parts = date_str.split('-')
                print(f"  Parts: {parts}")
                if len(parts) == 3:
                    # Could be MM-DD-YYYY or DD-MM-YYYY
                    print(f"  If MM-DD-YYYY: Month={parts[0]}, Day={parts[1]}, Year={parts[2]}")
                    print(f"  If DD-MM-YYYY: Day={parts[0]}, Month={parts[1]}, Year={parts[2]}")
                    # If year is 2 digits, JavaScript might interpret it as 20XX
                    if len(parts[2]) == 2:
                        year_2digit = int(parts[2])
                        if year_2digit < 50:
                            interpreted_year = 2000 + year_2digit
                            print(f"  JavaScript might interpret '{parts[2]}' as year {interpreted_year}")
                        else:
                            interpreted_year = 1900 + year_2digit
                            print(f"  JavaScript might interpret '{parts[2]}' as year {interpreted_year}")
else:
    print("No donations found")
