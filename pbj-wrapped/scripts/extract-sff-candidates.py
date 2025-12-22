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

def extract_facility_data_improved(lines: List[str], start_idx: int, end_idx: int) -> List[Dict]:
    """Improved facility extraction that handles multi-line entries."""
    facilities = []
    ccn_pattern = r'\b\d{6}\b'
    i = start_idx
    
    while i < end_idx and i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines and headers
        if not line or len(line) < 5:
            i += 1
            continue
        
        # Check if we've hit the next table
        if i < len(lines) - 1:
            next_line_lower = lines[i + 1].lower() if i + 1 < len(lines) else ''
            if 'table' in next_line_lower and any(x in next_line_lower for x in ['a', 'b', 'c', 'd']):
                break
        
        # Look for CCN in this line
        ccns = re.findall(ccn_pattern, line)
        if not ccns:
            i += 1
            continue
        
        ccn = ccns[0]
        if len(ccn) != 6 or not ccn.isdigit():
            i += 1
            continue
        
        # Build facility data from this line and next few lines
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
        
        # Get context from this line and next 2-3 lines
        context_lines = [line]
        for j in range(1, 4):
            if i + j < len(lines):
                context_lines.append(lines[i + j].strip())
        
        combined_text = ' '.join(context_lines)
        
        # Extract months (1-100, typically the last reasonable number)
        numbers = re.findall(r'\b\d+\b', combined_text)
        for num_str in reversed(numbers):
            if num_str == ccn:
                continue
            num = int(num_str)
            if 1 <= num <= 100:
                facility['months_as_sff'] = num
                break
        
        # Extract date (MM/DD/YYYY)
        date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', combined_text)
        if date_match:
            facility['most_recent_inspection'] = f"{date_match.group(1).zfill(2)}/{date_match.group(2).zfill(2)}/{date_match.group(3)}"
        
        # Extract "Met" or "Not Met"
        if re.search(r'\bmet\s+survey\s+criteria\b', combined_text, re.IGNORECASE):
            facility['met_survey_criteria'] = 'Met'
        elif re.search(r'\bnot\s+met\b', combined_text, re.IGNORECASE):
            facility['met_survey_criteria'] = 'Not Met'
        elif re.search(r'\bmet\b', combined_text, re.IGNORECASE) and 'not' not in combined_text.lower():
            facility['met_survey_criteria'] = 'Met'
        
        # Extract phone number
        phone_match = re.search(r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', combined_text)
        if phone_match:
            facility['phone_number'] = phone_match.group(1)
        
        # Extract ZIP (5 digits, sometimes with -4)
        zip_match = re.search(r'\b(\d{5}(-\d{4})?)\b', combined_text)
        if zip_match:
            facility['zip'] = zip_match.group(1)
        
        # Extract state (2-letter abbreviation, must be valid US state)
        # Look for state pattern before ZIP or after city
        state_candidates = re.findall(r'\b([A-Z]{2})\b', combined_text)
        for state_candidate in state_candidates:
            if state_candidate in US_STATES:
                facility['state'] = state_candidate
                break
        
        # Extract facility name - text before CCN, but after any previous CCN
        # Facility name is usually the first substantial text on the line
        name_part = line.split(ccn)[0].strip()
        
        # Clean up name - remove common prefixes/suffixes
        name_part = re.sub(r'^\d+\s*', '', name_part)  # Remove leading numbers
        name_part = re.sub(r'\s+', ' ', name_part)  # Normalize whitespace
        
        # If name part looks reasonable (has letters, not just numbers/symbols)
        if name_part and len(name_part) > 3 and re.search(r'[A-Za-z]', name_part):
            # Limit length and clean
            facility['facility_name'] = name_part[:150].strip()
        
        # If we still don't have a name, try the previous line
        if not facility['facility_name'] and i > 0:
            prev_line = lines[i - 1].strip()
            if prev_line and len(prev_line) > 3 and not re.search(ccn_pattern, prev_line):
                if re.search(r'[A-Za-z]', prev_line):
                    facility['facility_name'] = prev_line[:150].strip()
        
        # Extract address - usually contains street number and name
        # Address is typically between name and city/state
        address_pattern = r'(\d+\s+[A-Za-z0-9\s,.#-]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Court|Ct|Way|Circle|Cir))'
        address_match = re.search(address_pattern, combined_text, re.IGNORECASE)
        if address_match:
            facility['address'] = address_match.group(1).strip()[:100]
        else:
            # Try simpler pattern - number followed by text
            simple_address = re.search(r'(\d+\s+[A-Za-z0-9\s,.-]{10,50})', combined_text)
            if simple_address and not facility['facility_name']:
                addr_text = simple_address.group(1).strip()
                # Don't use if it looks like a name
                if not re.search(r'\b(Inc|LLC|Corp|Ltd|Nursing|Care|Center|Home)\b', addr_text, re.IGNORECASE):
                    facility['address'] = addr_text[:100]
        
        # Extract city - usually before state, after address
        # City names are typically capitalized words
        if facility['state']:
            # Look for text before state that could be a city
            state_pos = combined_text.find(facility['state'])
            if state_pos > 0:
                before_state = combined_text[:state_pos]
                # City is usually the last capitalized word/phrase before state
                city_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+' + facility['state'], before_state)
                if city_match:
                    city_candidate = city_match.group(1).strip()
                    # Make sure it's not too long and looks like a city name
                    if len(city_candidate) < 50 and re.match(r'^[A-Z][a-z]+', city_candidate):
                        facility['city'] = city_candidate
        
        facilities.append(facility)
        i += 1
    
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
            'total_count': len(table_a_facilities) + len(table_b_facilities) + 
                          len(table_c_facilities) + len(table_d_facilities)
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
