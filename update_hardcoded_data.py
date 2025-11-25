"""
Script to automatically update hardcoded data in HTML/JS files from CSV sources.

This script:
1. Reads state_quarterly_metrics.csv and national_quarterly_metrics.csv
2. Generates JavaScript data arrays/objects for:
   - nationalData: Array of national HPRD values (all quarters)
   - realStateData: Object with state arrays of HPRD values (all quarters)
   - quarters: Array of quarter strings (Q1 2017, Q2 2017, etc.)
   - stateData: Object with latest quarter HPRD values by state name
3. Automatically updates:
   - index.html
   - index-render.html
   - real_mobile_data.js

Usage: python update_hardcoded_data.py

Run this script whenever you update the CSV files with new quarterly data.
"""

import csv
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

# Read all historical data
with open('state_quarterly_metrics.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    all_state_data = list(reader)

with open('national_quarterly_metrics.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    all_national_data = list(reader)

# Get latest quarter
latest_quarter = all_national_data[-1]['CY_Qtr']
print(f"Latest quarter: {latest_quarter}")

# Parse quarter to get year and quarter number
quarter_match = re.match(r'(\d{4})Q(\d)', latest_quarter)
if quarter_match:
    year = int(quarter_match.group(1))
    q_num = int(quarter_match.group(2))
    latest_quarter_display = f"Q{q_num} {year}"
else:
    latest_quarter_display = latest_quarter

# State abbreviations in order (excluding USA for stateData, but including for realStateData)
state_abbrs = ['AK', 'AL', 'AR', 'AZ', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'GA', 'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MI', 'MN', 'MO', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'PR', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VA', 'VT', 'WA', 'WI', 'WV', 'WY']
state_abbrs_with_usa = state_abbrs + ['USA']

# Build national data array
national_array = []
for row in all_national_data:
    hprd = float(row['Total_Nurse_HPRD'])
    national_array.append(round(hprd, 3))

# Build quarters array
quarters = []
for row in all_national_data:
    q = row['CY_Qtr']
    q_match = re.match(r'(\d{4})Q(\d)', q)
    if q_match:
        year = int(q_match.group(1))
        q_num = int(q_match.group(2))
        quarters.append(f"Q{q_num} {year}")

# Build state data arrays for realStateData
real_state_data = {}
for abbr in state_abbrs_with_usa:
    if abbr == 'USA':
        state_array = national_array
    else:
        state_array = []
        for row in all_state_data:
            if row['STATE'] == abbr:
                hprd = float(row['Total_Nurse_HPRD'])
                state_array.append(round(hprd, 3))
    
    if state_array:
        real_state_data[abbr] = state_array

# Build latest quarter state data (stateData object with full names)
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

# Generate JavaScript code strings
def generate_national_data_js():
    return f"        const nationalData = [{','.join(map(str, national_array))}];"

def generate_real_state_data_js():
    lines = ["        const realStateData = {"]
    for abbr in state_abbrs_with_usa:
        if abbr in real_state_data:
            array_str = ','.join(map(str, real_state_data[abbr]))
            lines.append(f"          '{abbr}': [{array_str}],")
    lines.append("        };")
    return '\n'.join(lines)

def generate_quarters_js():
    lines = ["        const quarters = ["]
    for i, q in enumerate(quarters):
        lines.append(f"          '{q}',")
    lines.append("        ];")
    return '\n'.join(lines)

def generate_state_data_js():
    lines = [f"      // Real HPRD data from state_lite_metrics ({latest_quarter_display} - most recent quarter)"]
    lines.append("      const stateData = {")
    for state_name in sorted(latest_state_data.keys()):
        data = latest_state_data[state_name]
        lines.append(f"        '{state_name}': {{ hprd: {data['hprd']}, name: '{state_name}' }},")
    lines.append("      };")
    return '\n'.join(lines)

# Function to update a file
def update_file(filepath, patterns_replacements):
    # Try different encodings
    encodings = ['utf-8-sig', 'utf-8', 'latin-1']
    content = None
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    
    if content is None:
        print(f"[ERROR] Could not read {filepath}")
        return False
    
    original_content = content
    for pattern, replacement in patterns_replacements:
        # Use multiline and dotall flags for better matching
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[OK] Updated {filepath}")
        return True
    else:
        print(f"[SKIP] No changes needed in {filepath}")
        return False

# Update index.html - use more flexible patterns
# Pattern for nationalData - match the entire line
national_data_pattern = r'        const nationalData = \[[^\]]+\];'
# Pattern for realStateData - match from const to closing brace with proper indentation
real_state_data_pattern = r'        const realStateData = \{[\s\S]*?        \};'
# Pattern for quarters - match from const to closing bracket
quarters_pattern = r'        const quarters = \[[\s\S]*?        \];'
# Pattern for stateData - match from comment to closing brace
state_data_pattern = r'      // Real HPRD data from state_lite_metrics[^\n]*\n      const stateData = \{[\s\S]*?      \};'

index_patterns = [
    (national_data_pattern, generate_national_data_js()),
    (real_state_data_pattern, generate_real_state_data_js()),
    (quarters_pattern, generate_quarters_js()),
    (state_data_pattern, generate_state_data_js())
]

update_file('index.html', index_patterns)

# Update index-render.html (same patterns)
update_file('index-render.html', index_patterns)

# Update real_mobile_data.js (only realStateData, no indentation)
mobile_real_state_pattern = r'const realStateData = \{[\s\S]*?\};'
mobile_real_state_replacement = generate_real_state_data_js().replace('        ', '')
mobile_patterns = [
    (mobile_real_state_pattern, mobile_real_state_replacement)
]
update_file('real_mobile_data.js', mobile_patterns)

print("\n[SUCCESS] All files updated successfully!")
