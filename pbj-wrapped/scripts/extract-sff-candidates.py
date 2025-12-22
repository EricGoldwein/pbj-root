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
    
    # Extract months (usually the last number 1-200, as some facilities have >100 months)
    numbers = re.findall(r'\b\d+\b', line_without_ccn)
    for num_str in reversed(numbers):
        num = int(num_str)
        # Allow numbers 1-200 (some facilities have >100 months as SFF)
        if 1 <= num <= 200 and num_str != ccn:
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

def extract_facility_data_improved(lines: List[str], start_idx: int, end_idx: int, table_type: str = '') -> List[Dict]:
    """Improved facility extraction that properly parses table rows, handling repeated headers across pages."""
    facilities = []
    ccn_pattern = r'\b\d{6}\b'
    i = start_idx
    processed_ccns = set()  # Track CCNs to avoid duplicates
    
    # Skip initial header rows - look for the actual data rows
    # Headers usually contain "Provider Number", "Facility Name", etc.
    while i < end_idx and i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line or len(line) < 5:
            i += 1
            continue
        
        # Check if this line is a table header
        # BUT: if the line starts with a CCN, it's a facility row (even if it contains table header text)
        line_lower_for_table = line.lower()
        line_starts_with_ccn = bool(re.match(ccn_pattern, line.strip()))
        
        if 'table' in line_lower_for_table and not line_starts_with_ccn:
            # Check if it's a different table (should break)
            if table_type == 'a' and ('table b' in line_lower_for_table or 'table c' in line_lower_for_table or 'table d' in line_lower_for_table):
                break
            elif table_type == 'b' and ('table c' in line_lower_for_table or 'table d' in line_lower_for_table):
                break
            elif table_type == 'c' and 'table d' in line_lower_for_table:
                break
            # If it's the same table header repeated (page break), skip it and continue
            elif (table_type == 'a' and ('table a' in line_lower_for_table or 'current sff' in line_lower_for_table)) or \
                 (table_type == 'b' and ('table b' in line_lower_for_table or 'graduated' in line_lower_for_table)) or \
                 (table_type == 'c' and ('table c' in line_lower_for_table or 'no longer participating' in line_lower_for_table)) or \
                 (table_type == 'd' and ('table d' in line_lower_for_table or 'candidate' in line_lower_for_table)):
                # Skip the table header line
                i += 1
                # Skip next few lines if they look like column headers
                while i < end_idx and i < len(lines):
                    header_line = lines[i].strip()
                    if not header_line or len(header_line) < 5:
                        i += 1
                        continue
                    header_line_lower = header_line.lower()
                    if any(word in header_line_lower for word in ['provider number', 'facility name', 'address', 'city', 'state', 'zip', 'phone', 'inspection', 'met survey', 'months as', 'date of termination']):
                        i += 1
                    else:
                        break
                continue
        
        # Skip header rows (column headers) - but continue processing after them
        line_lower = line.lower()
        if any(word in line_lower for word in ['provider number', 'facility name', 'address', 'city', 'state', 'zip', 'phone', 'inspection', 'met survey', 'months as', 'date of termination']):
            i += 1
            continue
        
        # Look for CCN in this line
        ccns = re.findall(ccn_pattern, line)
        if not ccns:
            i += 1
            continue
        
        # Find the first valid 6-digit CCN
        ccn = None
        for candidate_ccn in ccns:
            if len(candidate_ccn) == 6 and candidate_ccn.isdigit():
                ccn_pos = line.find(candidate_ccn)
                if ccn_pos >= 0:
                    # CCN should be followed by text (facility name) or be at start of line
                    after_ccn = line[ccn_pos + 6:].strip()
                    # If there's substantial text after, it's likely a facility row
                    if len(after_ccn) > 3:
                        ccn = candidate_ccn
                        break
                    # Or if CCN is at start of line (might be followed by more on next line)
                    elif ccn_pos == 0 or (ccn_pos > 0 and line[ccn_pos - 1] in [' ', '\t', '|']):
                        ccn = candidate_ccn
                        break
        
        if not ccn:
            i += 1
            continue
        
        # Get the full row - might span multiple lines
        # First, check if this line contains a table header (which would be at the end)
        # If so, extract the facility data before the header
        full_row = line
        # Check if line contains table header text - if so, extract only the part before it
        if 'table' in line_lower:
            # Find where the table header starts
            table_header_patterns = [
                r'table\s+[a-d]:?\s+',
                r'table\s+[a-d]:?\s+facilities',
                r'table\s+[a-d]:?\s+.*no longer participating',
                r'table\s+[a-d]:?\s+.*candidate',
                r'table\s+[a-d]:?\s+.*graduated',
                r'table\s+[a-d]:?\s+.*current sff'
            ]
            for pattern in table_header_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    # Extract only the part before the table header
                    full_row = line[:match.start()].strip()
                    break
        
        # Check next few lines to see if this is a multi-line entry
        # BUT: be careful not to merge the last row of one page with the first row of next page
        j = i + 1
        continuation_limit = 2  # Only look ahead 2 lines max to avoid page break confusion
        while j < min(i + continuation_limit + 1, len(lines)) and j < end_idx:
            next_line = lines[j].strip()
            
            # If next line starts with a CCN, it's a new facility - stop here
            if next_line and re.match(ccn_pattern, next_line):
                break
            
            # If next line is a table header, stop here (we're at a page break)
            next_line_lower = next_line.lower()
            if 'table' in next_line_lower and any(x in next_line_lower for x in ['a', 'b', 'c', 'd']):
                break
            
            # If next line looks like column headers, stop here (page break with headers)
            if any(word in next_line_lower for word in ['provider number', 'facility name', 'address', 'city', 'state', 'zip', 'phone', 'inspection', 'met survey', 'months as', 'date of termination']):
                break
            
            # If next line is empty or very short, might be a page break - be cautious
            if not next_line or len(next_line) < 3:
                # Only continue if we haven't added much yet (might be mid-entry)
                if len(full_row) - len(line) < 50:
                    j += 1
                    continue
                else:
                    break
            
            # Check if it looks like continuation (has address parts, city, etc.)
            if re.search(r'[A-Za-z]', next_line) and len(next_line) > 10:
                # Additional check: if next line starts with a number that looks like a CCN, don't merge
                if not re.match(r'^\d{6}', next_line):
                    full_row += ' ' + next_line
                    j += 1
                else:
                    break
            else:
                break
        
        # Parse the row
        facility = parse_table_row(full_row, ccn)
        
        # Only add if we got a valid facility (has at least CCN and some data) and haven't seen this CCN before
        if facility['provider_number'] and facility['provider_number'] not in processed_ccns:
            facilities.append(facility)
            processed_ccns.add(facility['provider_number'])
        
        # Move past any continuation lines we consumed
        i = j if j > i + 1 else i + 1
    
    return facilities

def detect_table_boundaries(pages: List[Dict]) -> Dict[str, tuple]:
    """Automatically detect table boundaries by finding first occurrence of each table header."""
    # Find first occurrence of each table
    table_starts = {
        'a': None,  # Current SFF
        'b': None,  # Graduated
        'c': None,  # No longer participating
        'd': None   # Candidates
    }
    
    # Patterns to identify each table (more specific)
    table_patterns = {
        'a': [r'table\s+a:?\s+.*current\s+sff\s+facilities', r'table\s+a\s*[—\-]\s*current\s+sff'],
        'b': [r'table\s+b:?\s+.*graduated\s+from\s+the\s+sff', r'table\s+b\s*[—\-]\s*facilities\s+that\s+have\s+graduated'],
        'c': [r'table\s+c:?\s+.*no\s+longer\s+participating', r'table\s+c\s*[—\-]\s*facilities\s+no\s+longer'],
        'd': [r'table\s+d:?\s+.*sff\s+candidate\s+list', r'table\s+d\s*[—\-]\s*sff\s+candidate']
    }
    
    for page_num, page in enumerate(pages):
        page_text = page['text'].lower()
        for table_type, patterns in table_patterns.items():
            if table_starts[table_type] is None:  # Only find first occurrence
                for pattern in patterns:
                    if re.search(pattern, page_text, re.IGNORECASE):
                        table_starts[table_type] = page_num  # 0-indexed
                        break
    
    # Determine page ranges: each table continues until the next table starts
    # If not found, use fallback ranges
    result = {}
    
    if table_starts['a'] is not None:
        end = table_starts['b'] if table_starts['b'] is not None else (table_starts['c'] if table_starts['c'] is not None else (table_starts['d'] if table_starts['d'] is not None else len(pages)))
        result['a'] = (table_starts['a'], end)
    else:
        result['a'] = (3, 5)  # fallback: pages 4-5
    
    if table_starts['b'] is not None:
        end = table_starts['c'] if table_starts['c'] is not None else (table_starts['d'] if table_starts['d'] is not None else len(pages))
        result['b'] = (table_starts['b'], end)
    else:
        result['b'] = (5, 8)  # fallback: pages 6-8
    
    if table_starts['c'] is not None:
        end = table_starts['d'] if table_starts['d'] is not None else len(pages)
        result['c'] = (table_starts['c'], end)
    else:
        result['c'] = (8, 9)  # fallback: page 9
    
    if table_starts['d'] is not None:
        result['d'] = (table_starts['d'], len(pages))
    else:
        result['d'] = (9, len(pages))  # fallback: pages 10-end
    
    return result

def extract_table_data(pages: List[Dict]) -> Dict:
    """Extract all table data from PDF pages using page-based boundaries."""
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
    
    # Use known page ranges as primary (user provided: A: 4-5, B: 6-8, C: 9, D: 10-18)
    # Detection can be enhanced later for future PDFs
    # Page indices are 0-based, so page 4 = index 3, page 5 = index 4, etc.
    table_a_pages = [3, 4]  # pages 4-5 (0-indexed: 3, 4)
    table_b_pages = [5, 6, 7]  # pages 6-8 (0-indexed: 5, 6, 7)
    table_c_pages = [8]  # page 9 (0-indexed: 8)
    table_d_pages = list(range(9, min(18, len(pages))))  # pages 10-18 (0-indexed: 9-17)
    
    print(f"\nExtracting from pages:")
    print(f"  Table A: pages {[p+1 for p in table_a_pages]}")
    print(f"  Table B: pages {[p+1 for p in table_b_pages]}")
    print(f"  Table C: page {table_c_pages[0]+1 if table_c_pages else 'N/A'}")
    print(f"  Table D: pages {[p+1 for p in table_d_pages]}")
    
    # Extract text from page ranges
    table_a_text = '\n'.join([pages[i]['text'] for i in table_a_pages if i < len(pages)])
    table_b_text = '\n'.join([pages[i]['text'] for i in table_b_pages if i < len(pages)])
    table_c_text = '\n'.join([pages[i]['text'] for i in table_c_pages if i < len(pages)])
    table_d_text = '\n'.join([pages[i]['text'] for i in table_d_pages if i < len(pages)])
    
    # Convert to lines
    table_a_lines = table_a_text.split('\n')
    table_b_lines = table_b_text.split('\n')
    table_c_lines = table_c_text.split('\n')
    table_d_lines = table_d_text.split('\n')
    
    # Extract facilities from each table
    print("\nExtracting Table A (Current SFF)...")
    table_a_facilities = extract_facility_data_improved(table_a_lines, 0, len(table_a_lines), 'a')
    
    print("Extracting Table B (Graduated)...")
    table_b_facilities = extract_facility_data_improved(table_b_lines, 0, len(table_b_lines), 'b')
    
    print("Extracting Table C (No Longer Participating)...")
    table_c_facilities = extract_facility_data_improved(table_c_lines, 0, len(table_c_lines), 'c')
    
    # Table C should only have these 8 specific facilities (user provided list)
    # Filter to only include these CCNs (handle leading zeros)
    table_c_expected_ccns = {'165344', '155857', '175172', '235187', '265857', '345008', '395414', '675764'}
    # Normalize CCNs (remove leading zeros) for matching
    def normalize_ccn(ccn):
        normalized = ccn.lstrip('0')
        return normalized if normalized else ccn
    
    # Create sets with and without leading zeros
    table_c_normalized_expected = {normalize_ccn(ccn) for ccn in table_c_expected_ccns}
    table_c_with_zeros = {ccn.zfill(6) for ccn in table_c_expected_ccns}
    
    # Debug: print what we found
    found_ccns = [f['provider_number'] for f in table_c_facilities]
    print(f"  Found {len(table_c_facilities)} facilities in Table C before filtering")
    print(f"  Sample CCNs found: {found_ccns[:10] if found_ccns else 'None'}")
    
    # Filter to only expected CCNs
    filtered = []
    for f in table_c_facilities:
        ccn = f['provider_number']
        normalized = normalize_ccn(ccn)
        if ccn in table_c_expected_ccns or ccn in table_c_with_zeros or normalized in table_c_normalized_expected:
            # Normalize to 6 digits without leading zeros (except for single digit)
            f['provider_number'] = normalized.zfill(6) if len(normalized) < 6 else normalized
            filtered.append(f)
    
    table_c_facilities = filtered
    print(f"  Filtered Table C to {len(table_c_facilities)} facilities (expected 8)")
    if len(table_c_facilities) < 8:
        print(f"  WARNING: Missing {8 - len(table_c_facilities)} facilities from Table C")
        print(f"  Expected CCNs: {sorted(table_c_expected_ccns)}")
        print(f"  Found CCNs: {sorted(found_ccns)}")
    
    print("Extracting Table D (Candidates)...")
    table_d_facilities = extract_facility_data_improved(table_d_lines, 0, len(table_d_lines), 'd')
    
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
