"""
Script to generate comprehensive JSON files for dynamic data loading in index.html.

This script:
1. Reads state_quarterly_metrics.csv and national_quarterly_metrics.csv
2. Generates JSON files with all historical data:
   - state_historical_data.json: All state HPRD values by quarter
   - national_historical_data.json: All national HPRD values by quarter
   - quarters_list.json: List of all quarters
   - latest_quarter_data.json: Latest quarter statistics and top states
3. These JSON files can be loaded dynamically in index.html

Usage: python generate_dynamic_data_json.py

Run this script whenever you update the CSV files with new quarterly data.
"""

import csv
import json
import re
from datetime import datetime

# State abbreviation to full name mapping
STATE_NAMES = {
    'AK': 'Alaska', 'AL': 'Alabama', 'AR': 'Arkansas', 'AZ': 'Arizona', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DC': 'District of Columbia', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'IA': 'Iowa', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana',
    'MA': 'Massachusetts', 'MD': 'Maryland', 'ME': 'Maine', 'MI': 'Michigan', 'MN': 'Minnesota',
    'MO': 'Missouri', 'MS': 'Mississippi', 'MT': 'Montana', 'NC': 'North Carolina',
    'ND': 'North Dakota', 'NE': 'Nebraska', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NV': 'Nevada', 'NY': 'New York', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'PR': 'Puerto Rico', 'RI': 'Rhode Island',
    'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas',
    'UT': 'Utah', 'VA': 'Virginia', 'VT': 'Vermont', 'WA': 'Washington', 'WI': 'Wisconsin',
    'WV': 'West Virginia', 'WY': 'Wyoming'
}

# Reverse mapping: full name to abbreviation
NAME_TO_ABBR = {v: k for k, v in STATE_NAMES.items()}

def parse_quarter(quarter_str):
    """Parse quarter string like '2025Q2' to display format 'Q2 2025'"""
    match = re.match(r'(\d{4})Q(\d)', quarter_str)
    if match:
        year = int(match.group(1))
        q_num = int(match.group(2))
        return f"Q{q_num} {year}"
    return quarter_str

def main():
    print("Generating dynamic data JSON files...")
    
    # Read all historical data
    print("Reading CSV files...")
    with open('state_quarterly_metrics.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_state_data = list(reader)
    
    with open('national_quarterly_metrics.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_national_data = list(reader)
    
    # Get latest quarter
    latest_quarter = all_national_data[-1]['CY_Qtr']
    latest_quarter_display = parse_quarter(latest_quarter)
    print(f"Latest quarter: {latest_quarter_display}")
    
    # Build quarters array
    quarters = []
    for row in all_national_data:
        q = row['CY_Qtr']
        quarters.append(parse_quarter(q))
    
    # Build national data array
    national_array = []
    for row in all_national_data:
        hprd = float(row['Total_Nurse_HPRD'])
        national_array.append(round(hprd, 3))
    
    # Build state historical data (all quarters for each state)
    state_historical = {}
    state_abbrs = list(STATE_NAMES.keys())
    
    for abbr in state_abbrs + ['USA']:
        if abbr == 'USA':
            state_historical[abbr] = national_array
        else:
            state_array = []
            for row in all_state_data:
                if row['STATE'] == abbr:
                    hprd = float(row['Total_Nurse_HPRD'])
                    state_array.append(round(hprd, 3))
            if state_array:
                state_historical[abbr] = state_array
    
    # Build latest quarter state data (for map and statistics)
    latest_state_data = {}
    for abbr in state_abbrs:
        if abbr in STATE_NAMES:
            state_name = STATE_NAMES[abbr]
            # Find latest quarter data for this state
            latest_row = None
            for row in reversed(all_state_data):
                if row['STATE'] == abbr and row['CY_Qtr'] == latest_quarter:
                    latest_row = row
                    break
            
            if latest_row:
                hprd = float(latest_row['Total_Nurse_HPRD'])
                latest_state_data[state_name] = {
                    'hprd': round(hprd, 3),
                    'name': state_name
                }
    
    # Get latest national data
    latest_national_hprd = float(all_national_data[-1]['Total_Nurse_HPRD'])
    
    # Calculate top 5 states
    top_states = sorted(
        [(name, data['hprd']) for name, data in latest_state_data.items()],
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    # Find highest and lowest states
    all_states_sorted = sorted(
        [(name, data['hprd']) for name, data in latest_state_data.items()],
        key=lambda x: x[1],
        reverse=True
    )
    highest_state = all_states_sorted[0] if all_states_sorted else None
    lowest_state = all_states_sorted[-1] if all_states_sorted else None
    
    # Count total quarters
    total_quarters = len(quarters)
    
    # Generate JSON files
    print("\nWriting JSON files...")
    
    # 1. State historical data (all quarters for all states)
    with open('state_historical_data.json', 'w', encoding='utf-8') as f:
        json.dump(state_historical, f, indent=2)
    print(f"[OK] Created state_historical_data.json ({len(state_historical)} states)")
    
    # 2. National historical data
    national_data_obj = {
        'quarters': quarters,
        'hprd_values': national_array,
        'latest_quarter': latest_quarter,
        'latest_quarter_display': latest_quarter_display,
        'latest_hprd': round(latest_national_hprd, 3)
    }
    with open('national_historical_data.json', 'w', encoding='utf-8') as f:
        json.dump(national_data_obj, f, indent=2)
    print(f"[OK] Created national_historical_data.json ({len(quarters)} quarters)")
    
    # 3. Quarters list
    with open('quarters_list.json', 'w', encoding='utf-8') as f:
        json.dump(quarters, f, indent=2)
    print(f"[OK] Created quarters_list.json ({len(quarters)} quarters)")
    
    # 4. Latest quarter data (for statistics and map)
    latest_data = {
        'quarter': latest_quarter,
        'quarter_display': latest_quarter_display,
        'national_hprd': round(latest_national_hprd, 3),
        'highest_state': {
            'name': highest_state[0] if highest_state else None,
            'hprd': round(highest_state[1], 3) if highest_state else None
        },
        'lowest_state': {
            'name': lowest_state[0] if lowest_state else None,
            'hprd': round(lowest_state[1], 3) if lowest_state else None
        },
        'top_5_states': [
            {'name': name, 'hprd': round(hprd, 3)} for name, hprd in top_states
        ],
        'state_data': latest_state_data,
        'total_quarters': total_quarters
    }
    with open('latest_quarter_data.json', 'w', encoding='utf-8') as f:
        json.dump(latest_data, f, indent=2)
    print(f"[OK] Created latest_quarter_data.json (Q2 2025 data)")
    
    # 5. States list for dropdown
    states_list = ['USA'] + sorted([STATE_NAMES[abbr] for abbr in state_abbrs])
    with open('states_list.json', 'w', encoding='utf-8') as f:
        json.dump(states_list, f, indent=2)
    print(f"[OK] Created states_list.json ({len(states_list)} states)")
    
    print(f"\n[SUCCESS] Successfully generated all JSON files!")
    print(f"   Latest quarter: {latest_quarter_display}")
    print(f"   National HPRD: {round(latest_national_hprd, 3)}")
    print(f"   Total quarters: {total_quarters}")

if __name__ == '__main__':
    main()
