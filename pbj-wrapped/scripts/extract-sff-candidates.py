"""
Extract SFF data from PDF with all columns and proper categorization.
Tables:
- Table A: Current SFF Facilities
- Table B: Facilities That Have Graduated from the SFF Program
- Table C: Facilities No Longer Participating in the Medicare and Medicaid Program
- Table D: SFF Candidate List
"""
import PyPDF2
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# US State abbreviations
US_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
}

def extract_text_from_pdf(pdf_path):
    """Extract all text from PDF, preserving page structure."""
    pages = []
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        print(f"PDF has {len(pdf_reader.pages)} pages")
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            pages.append({
                'number': page_num + 1,
                'text': page_text
            })
    return pages

def parse_table_row(line: str, ccn: str) -> Dict:
    """Parse a single table row into structured data."""
    facility = {
        'provider_number': ccn,
        'facility_name': None,
        'address': None,
        'city': None,
        'state': None,
        'zip': None,
        'phone_number': None,
        'most_recent_inspection': None,
        'met_survey_criteria': None,
        'months_as_sff': None
    }
    
    # Remove the CCN from the line to get the rest
    line_without_ccn = line.replace(ccn, '', 1).strip()
    
    # Extract months (usually the last number 1-100)
    numbers = re.findall(r'\b\d+\b', line_without_ccn)
    for num_str in reversed(numbers):
        num = int(num_str)
        if 1 <= num <= 100 and num_str != ccn:
            facility['months_as_sff'] = num
            # Remove months from line
            line_without_ccn = re.sub(r'\b' + num_str + r'\b', '', line_without_ccn, count=1)
            break
    
    # Extract date (MM/DD/YYYY)
    date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', line_without_ccn)
    if date_match:
        facility['most_recent_inspection'] = f"{date_match.group(1).zfill(2)}/{date_match.group(2).zfill(2)}/{date_match.group(3)}"
        # Remove date from line
        line_without_ccn = re.sub(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', '', line_without_ccn, count=1)
    
    # Extract "Met" or "Not Met"
    if re.search(r'\bnot\s+met\b', line_without_ccn, re.IGNORECASE):
        facility['met_survey_criteria'] = 'Not Met'
        line_without_ccn = re.sub(r'\bnot\s+met\b', '', line_without_ccn, flags=re.IGNORECASE, count=1)
    elif re.search(r'\bmet\b', line_without_ccn, re.IGNORECASE):
        facility['met_survey_criteria'] = 'Met'
        line_without_ccn = re.sub(r'\bmet\b', '', line_without_ccn, flags=re.IGNORECASE, count=1)
    
    # Extract phone number (format: XXX-XXX-XXXX or (XXX) XXX-XXXX)
    phone_match = re.search(r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', line_without_ccn)
    if phone_match:
        facility['phone_number'] = phone_match.group(1).strip()
        # Remove phone from line
        line_without_ccn = re.sub(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '', line_without_ccn, count=1)
    
    # Extract ZIP (5 digits, sometimes with -4)
    zip_match = re.search(r'\b(\d{5}(-\d{4})?)\b', line_without_ccn)
    if zip_match:
        facility['zip'] = zip_match.group(1)
        # Remove ZIP from line
        line_without_ccn = re.sub(r'\b\d{5}(-\d{4})?\b', '', line_without_ccn, count=1)
    
    # Extract state (2-letter abbreviation, must be valid US state)
    state_candidates = re.findall(r'\b([A-Z]{2})\b', line_without_ccn)
    for state_candidate in state_candidates:
        if state_candidate in US_STATES:
            facility['state'] = state_candidate
            # Remove state from line
            line_without_ccn = re.sub(r'\b' + state_candidate + r'\b', '', line_without_ccn, count=1)
            break
    
    # What's left should be: Facility Name, Address, City
    # Clean up the remaining text
    remaining = re.sub(r'\s+', ' ', line_without_ccn).strip()
    
    # Try to identify city (usually capitalized words before state, but we already removed state)
    # City is often the last capitalized word/phrase
    # For now, we'll extract facility name and address from what's left
    # Facility name is usually at the start, address in the middle
    
    # Split remaining text into parts
    parts = [p.strip() for p in remaining.split() if p.strip()]
    
    # Try to find facility name (usually starts with capital letters, may contain words like "Nursing", "Care", "Center")
    name_parts = []
    address_parts = []
    city_parts = []
    
    i = 0
    # Facility name usually comes first and contains words like Nursing, Care, Center, Home, etc.
    while i < len(parts):
        part = parts[i]
        # If we hit something that looks like an address (starts with number), stop collecting name
        if re.match(r'^\d+', part):
            break
        name_parts.append(part)
        i += 1
    
    # Address usually starts with a number
    while i < len(parts):
        part = parts[i]
        if re.match(r'^\d+', part):
            address_parts.append(part)
            i += 1
            # Continue until we hit something that looks like a city (all caps or capitalized words)
            while i < len(parts):
                next_part = parts[i]
                # If it's all caps and short, might be a state (but we already extracted that)
                # If it's a capitalized word, might be city
                if re.match(r'^[A-Z][a-z]+', next_part) and len(next_part) > 2:
                    city_parts.append(next_part)
                    i += 1
                elif re.match(r'^[A-Z]{2,}$', next_part) and next_part not in US_STATES:
                    # Might be part of address or city abbreviation
                    address_parts.append(next_part)
                    i += 1
                else:
                    break
            break
        i += 1
    
    # If we have name parts, join them
    if name_parts:
        facility['facility_name'] = ' '.join(name_parts)
    
    # If we have address parts, join them
    if address_parts:
        facility['address'] = ' '.join(address_parts)
    
    # If we have city parts, join them
    if city_parts:
        facility['city'] = ' '.join(city_parts)
    
    return facility

def extract_facility_data_improved(lines: List[str], start_idx: int, end_idx: int) -> List[Dict]:
    """Improved facility extraction that properly parses table rows."""
    facilities = []
    ccn_pattern = r'\b\d{6}\b'
    i = start_idx
    
    # Skip header rows - look for the actual data rows
    # Headers usually contain "Provider Number", "Facility Name", etc.
    while i < end_idx and i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line or len(line) < 5:
            i += 1
            continue
        
        # Check if we've hit the next table
        if i < len(lines) - 1:
            next_line_lower = lines[i + 1].lower() if i + 1 < len(lines) else ''
            if 'table' in next_line_lower and any(x in next_line_lower for x in ['a', 'b', 'c', 'd']):
                break
        
        # Skip header rows
        line_lower = line.lower()
        if any(word in line_lower for word in ['provider number', 'facility name', 'address', 'city', 'state', 'zip', 'phone', 'inspection', 'met survey', 'months']):
            i += 1
            continue
        
        # Look for CCN in this line
        ccns = re.findall(ccn_pattern, line)
        if not ccns:
            i += 1
            continue
        
        ccn = ccns[0]
        if len(ccn) != 6 or not ccn.isdigit():
            i += 1
            continue
        
        # Check if this CCN is actually part of a facility row (not a page number or other number)
        # Facility rows should have the CCN followed by text (facility name, address, etc.)
        ccn_pos = line.find(ccn)
        if ccn_pos == -1:
            i += 1
            continue
        
        # Get the full row - might span multiple lines
        full_row = line
        # Check next few lines to see if this is a multi-line entry
        j = i + 1
        while j < min(i + 3, len(lines)) and j < end_idx:
            next_line = lines[j].strip()
            # If next line doesn't start with a CCN, it might be continuation
            if next_line and not re.match(ccn_pattern, next_line):
                # Check if it looks like continuation (has address parts, city, etc.)
                if re.search(r'[A-Za-z]', next_line) and len(next_line) > 10:
                    full_row += ' ' + next_line
                    j += 1
                else:
                    break
            else:
                break
        
        # Parse the row
        facility = parse_table_row(full_row, ccn)
        
        # Only add if we got a valid facility (has at least CCN and some data)
        if facility['provider_number']:
            facilities.append(facility)
        
        # Move past any continuation lines we consumed
        i = j if j > i + 1 else i + 1
    
    return facilities

def extract_table_data(pages: List[Dict]) -> Dict:
    """Extract all table data from PDF pages."""
    full_text = '\n'.join([p['text'] for p in pages])
    lines = full_text.split('\n')
    
    # Extract document date
    doc_month = 12
    doc_year = 2025
    month_map = {
        'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
        'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
        'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
        'august': 8, 'aug': 8, 'september': 9, 'sep': 9,
        'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
        'december': 12, 'dec': 12
    }
    
    # Look for "December 10, 2025" or "December 2025" specifically first
    for page in pages[:5]:
        page_text = page['text']
        page_lower = page_text.lower()
        
        # Prioritize December 2025
        if 'december' in page_lower and '2025' in page_text:
            doc_month = 12
            year_match = re.search(r'2025', page_text)
            if year_match:
                doc_year = 2025
            break
        
        # Also check for "list updated Dec. 10, 2025" or similar
        dec_pattern = re.search(r'dec\.?\s+10,?\s+2025|december\s+10,?\s+2025', page_lower)
        if dec_pattern:
            doc_month = 12
            doc_year = 2025
            break
    
    # If not found, search for any month
    if doc_month == 0:
        for page in pages[:5]:
            page_lower = page['text'].lower()
            for month_name, month_num in month_map.items():
                if month_name in page_lower:
                    doc_month = month_num
                    break
            year_match = re.search(r'(\d{4})', page['text'])
            if year_match:
                year_candidate = int(year_match.group(1))
                if 2000 <= year_candidate <= 2100:
                    doc_year = year_candidate
    
    # Default to December 2025 if not found
    if doc_month == 0:
        doc_month = 12
    if doc_year == 0:
        doc_year = 2025
    
    month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June', 
                   'July', 'August', 'September', 'October', 'November', 'December']
    month_name = month_names[doc_month] if 1 <= doc_month <= 12 else 'December'
    
    # Find table boundaries
    table_a_start = -1
    table_b_start = -1
    table_c_start = -1
    table_d_start = -1
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if 'table a' in line_lower and ('current sff' in line_lower or 'facilities' in line_lower):
            table_a_start = i
        elif 'table b' in line_lower and ('graduated' in line_lower):
            table_b_start = i
        elif 'table c' in line_lower and ('no longer participating' in line_lower):
            table_c_start = i
        elif 'table d' in line_lower and ('candidate' in line_lower):
            table_d_start = i
    
    print(f"\nTable boundaries:")
    print(f"  Table A: line {table_a_start}")
    print(f"  Table B: line {table_b_start}")
    print(f"  Table C: line {table_c_start}")
    print(f"  Table D: line {table_d_start}")
    
    # Determine table end boundaries
    table_a_end = table_b_start if table_b_start > 0 else table_c_start if table_c_start > 0 else table_d_start if table_d_start > 0 else len(lines)
    table_b_end = table_c_start if table_c_start > 0 else table_d_start if table_d_start > 0 else len(lines)
    table_c_end = table_d_start if table_d_start > 0 else len(lines)
    table_d_end = len(lines)
    
    # Extract facilities from each table
    print("\nExtracting Table A (Current SFF)...")
    table_a_facilities = extract_facility_data_improved(lines, table_a_start, table_a_end) if table_a_start >= 0 else []
    
    print("Extracting Table B (Graduated)...")
    table_b_facilities = extract_facility_data_improved(lines, table_b_start, table_b_end) if table_b_start >= 0 else []
    
    print("Extracting Table C (No Longer Participating)...")
    table_c_facilities = extract_facility_data_improved(lines, table_c_start, table_c_end) if table_c_start >= 0 else []
    
    print("Extracting Table D (Candidates)...")
    table_d_facilities = extract_facility_data_improved(lines, table_d_start, table_d_end) if table_d_start >= 0 else []
    
    return {
        'document_date': {
            'month': doc_month,
            'year': doc_year,
            'month_name': month_name
        },
        'table_a_current_sff': table_a_facilities,
        'table_b_graduated': table_b_facilities,
        'table_c_no_longer_participating': table_c_facilities,
        'table_d_candidates': table_d_facilities,
        'summary': {
            'current_sff_count': len(table_a_facilities),
            'graduated_count': len(table_b_facilities),
            'no_longer_participating_count': len(table_c_facilities),
            'candidates_count': len(table_d_facilities),
            'total_count': len(table_a_facilities) + len(table_b_facilities) + len(table_c_facilities) + len(table_d_facilities)
        }
    }

def main():
    pdf_path = Path(__file__).parent.parent / 'public' / 'sff-posting-with-candidate-list-november-2025.pdf'
    
    if not pdf_path.exists():
        print(f"Error: PDF file not found at {pdf_path}")
        sys.exit(1)
    
    print(f"Extracting from {pdf_path.name}...")
    pages = extract_text_from_pdf(pdf_path)
    
    print("Extracting table data...")
    data = extract_table_data(pages)
    
    print(f"\nSummary:")
    print(f"  Table A (Current SFF): {data['summary']['current_sff_count']}")
    print(f"  Table B (Graduated): {data['summary']['graduated_count']}")
    print(f"  Table C (No Longer Participating): {data['summary']['no_longer_participating_count']}")
    print(f"  Table D (Candidates): {data['summary']['candidates_count']}")
    print(f"  Total: {data['summary']['total_count']}")
    print(f"  Date: {data['document_date']['month_name']} {data['document_date']['year']}")
    
    # Save to JSON
    output_path = Path(__file__).parent.parent / 'public' / 'sff-candidate-months.json'
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nSaved to {output_path}")
    
    # Show samples
    print("\nSamples:")
    for table_name, facilities, sample_idx in [
        ('Table A', data['table_a_current_sff'], 0),
        ('Table D', data['table_d_candidates'], 0)
    ]:
        if facilities and len(facilities) > sample_idx:
            f = facilities[sample_idx]
            print(f"\n{table_name} sample:")
            print(f"  CCN: {f['provider_number']}")
            print(f"  Name: {f.get('facility_name', 'N/A')}")
            print(f"  State: {f.get('state', 'N/A')}")
            print(f"  City: {f.get('city', 'N/A')}")
            print(f"  Months: {f.get('months_as_sff', 'N/A')}")
            print(f"  Inspection: {f.get('most_recent_inspection', 'N/A')}")
            print(f"  Met Criteria: {f.get('met_survey_criteria', 'N/A')}")
    
    return data

if __name__ == '__main__':
    main()
