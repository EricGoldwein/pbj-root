#!/usr/bin/env python3
"""
Extract SFF tables A, B, C, and D from PDF and export to CSV files.
Handles repeated headers across page breaks.
Uses pdfplumber for better table extraction.
"""
import pdfplumber
import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

def extract_tables_from_pdf(pdf_path: Path) -> Dict[str, List[List[str]]]:
    """Extract all tables from PDF using pdfplumber."""
    tables = {'a': [], 'b': [], 'c': [], 'd': []}
    
    # Known page ranges (1-indexed for pdfplumber)
    # Table A: pages 4-5
    # Table B: pages 6-8
    # Table C: page 9
    # Table D: pages 10-18
    page_ranges = {
        'a': (4, 5),
        'b': (6, 8),
        'c': (9, 9),
        'd': (10, 18)
    }
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"PDF has {len(pdf.pages)} pages")
        
        for table_type, (start_page, end_page) in page_ranges.items():
            print(f"\nExtracting Table {table_type.upper()} from pages {start_page}-{end_page}...")
            
            all_rows = []
            headers_set = False
            headers = None
            
            for page_num in range(start_page - 1, min(end_page, len(pdf.pages))):  # Convert to 0-indexed
                page = pdf.pages[page_num]
                
                # Try to extract tables from the page
                page_tables = page.extract_tables()
                
                if page_tables:
                    for table in page_tables:
                        if not table or len(table) == 0:
                            continue
                        
                        # Check if this table has multi-line cells (common in PDF tables)
                        # If so, we need to split by newlines and combine row by row
                        has_multiline = False
                        for row in table:
                            if row:
                                for cell in row:
                                    if cell and '\n' in str(cell):
                                        has_multiline = True
                                        break
                                if has_multiline:
                                    break
                        
                        if has_multiline:
                            # Parse multi-line table structure
                            # Each column contains multiple values separated by newlines
                            num_cols = len(table[0]) if table else 0
                            if num_cols == 0:
                                continue
                            
                            # Find the header row
                            header_row_idx = None
                            for row_idx, row in enumerate(table):
                                if not row:
                                    continue
                                row_text = ' '.join([str(c) for c in row if c]).lower()
                                if any(keyword in row_text for keyword in [
                                    'provider number', 'facility name', 'address', 'city', 'state', 
                                    'zip', 'phone', 'inspection', 'met survey', 'months as', 
                                    'date of termination', 'most recent'
                                ]) and 'table' not in row_text:
                                    header_row_idx = row_idx
                                    break
                            
                            if header_row_idx is None:
                                continue
                            
                            # Extract headers
                            if not headers_set:
                                headers = []
                                for col_idx in range(num_cols):
                                    cell = table[header_row_idx][col_idx] if col_idx < len(table[header_row_idx]) else None
                                    if cell:
                                        # Clean header - join all lines with spaces (headers can span multiple lines)
                                        header_lines = [line.strip() for line in str(cell).split('\n') if line.strip()]
                                        header_text = ' '.join(header_lines)
                                        header_text = re.sub(r'\s+', ' ', header_text)
                                        headers.append(header_text)
                                    else:
                                        headers.append('')
                                all_rows.append(headers)
                                headers_set = True
                            
                            # Extract data rows - split each column by newlines and combine
                            # Start from row after header
                            for row_idx in range(header_row_idx + 1, len(table)):
                                row = table[row_idx]
                                if not row:
                                    continue
                                
                                # Check if this is a table title row
                                row_text = ' '.join([str(c) for c in row if c]).lower()
                                is_table_title = False
                                if table_type == 'a':
                                    is_table_title = 'table a' in row_text and 'current sff' in row_text
                                elif table_type == 'b':
                                    is_table_title = 'table b' in row_text and 'graduated' in row_text
                                elif table_type == 'c':
                                    is_table_title = 'table c' in row_text and 'no longer participating' in row_text
                                elif table_type == 'd':
                                    is_table_title = 'table d' in row_text and 'candidate' in row_text
                                
                                if is_table_title:
                                    continue
                                
                                # Split each column by newlines
                                column_values = []
                                max_rows = 0
                                for col_idx in range(num_cols):
                                    cell = row[col_idx] if col_idx < len(row) else None
                                    if cell:
                                        values = [v.strip() for v in str(cell).split('\n') if v.strip()]
                                        column_values.append(values)
                                        max_rows = max(max_rows, len(values))
                                    else:
                                        column_values.append([''])
                                
                                # Combine into rows (each index across columns forms a row)
                                for i in range(max_rows):
                                    data_row = []
                                    for col_values in column_values:
                                        if i < len(col_values):
                                            # Clean the value
                                            value = col_values[i].strip()
                                            value = re.sub(r'\s+', ' ', value)
                                            data_row.append(value)
                                        else:
                                            data_row.append('')
                                    
                                    # Only add if first column looks like a CCN
                                    if data_row and data_row[0] and re.match(r'^\d{6}', data_row[0]):
                                        all_rows.append(data_row)
                        else:
                            # Standard table structure - process row by row
                            for row_idx, row in enumerate(table):
                                if not row:
                                    continue
                                
                                # Clean the row - remove None values and strip whitespace
                                clean_row = []
                                for cell in row:
                                    if cell is None:
                                        clean_row.append('')
                                    else:
                                        # Clean up the cell text
                                        cell_text = str(cell).strip()
                                        # Remove extra whitespace
                                        cell_text = re.sub(r'\s+', ' ', cell_text)
                                        clean_row.append(cell_text)
                                
                                # Skip empty rows
                                if not any(clean_row):
                                    continue
                                
                                # Check if this is a header row
                                row_text = ' '.join(clean_row).lower()
                                is_header = any(keyword in row_text for keyword in [
                                    'provider number', 'facility name', 'address', 'city', 'state', 
                                    'zip', 'phone', 'inspection', 'met survey', 'months as', 
                                    'date of termination', 'most recent'
                                ])
                                
                                # Check if this is a table title
                                is_table_title = False
                                if table_type == 'a':
                                    is_table_title = 'table a' in row_text and 'current sff' in row_text
                                elif table_type == 'b':
                                    is_table_title = 'table b' in row_text and 'graduated' in row_text
                                elif table_type == 'c':
                                    is_table_title = 'table c' in row_text and 'no longer participating' in row_text
                                elif table_type == 'd':
                                    is_table_title = 'table d' in row_text and 'candidate' in row_text
                                
                                if is_table_title:
                                    continue  # Skip table titles
                                
                                if is_header:
                                    # Use the first header row we encounter
                                    if not headers_set:
                                        headers = clean_row
                                        all_rows.append(headers)
                                        headers_set = True
                                    # Skip subsequent header rows (page breaks)
                                    continue
                                
                                # Check if this looks like a data row (starts with a 6-digit CCN)
                                first_cell = clean_row[0] if clean_row else ''
                                if re.match(r'^\d{6}', first_cell):
                                    all_rows.append(clean_row)
            
            # If no tables were extracted, try text extraction as fallback
            if not all_rows or len(all_rows) <= 1:
                print(f"  No tables found with pdfplumber, trying text extraction...")
                all_rows = extract_table_from_text(pdf, table_type, start_page - 1, min(end_page, len(pdf.pages)))
            
            tables[table_type] = all_rows
            print(f"  Found {len(all_rows) - 1} data rows (plus header)")
    
    return tables

def extract_table_from_text(pdf, table_type: str, start_page: int, end_page: int) -> List[List[str]]:
    """Fallback: Extract table from text if pdfplumber table extraction fails."""
    rows = []
    headers_set = False
    
    # Define headers based on table type
    if table_type == 'a':
        headers = ['Provider Number', 'Facility Name', 'Address', 'City', 'State', 'ZIP', 
                   'Phone Number', 'Most Recent Inspection', 'Met Survey Criteria', 'Months as SFF']
    elif table_type == 'b':
        headers = ['Provider Number', 'Facility Name', 'Address', 'City', 'State', 'ZIP', 
                   'Phone Number', 'Most Recent Inspection', 'Met Survey Criteria', 'Months as SFF']
    elif table_type == 'c':
        headers = ['Provider Number', 'Facility Name', 'Address', 'City', 'State', 'ZIP', 
                   'Phone Number', 'Date of Termination', '', '']
    elif table_type == 'd':
        headers = ['Provider Number', 'Facility Name', 'Address', 'City', 'State', 'ZIP', 
                   'Phone Number', 'Most Recent Inspection', 'Met Survey Criteria', '']
    else:
        headers = ['Provider Number', 'Facility Name', 'Address', 'City', 'State', 'ZIP', 
                   'Phone Number', 'Most Recent Inspection', 'Met Survey Criteria', 'Months as SFF']
    
    rows.append(headers)
    headers_set = True
    
    ccn_pattern = r'\b\d{6}\b'
    processed_ccns = set()
    
    for page_num in range(start_page, end_page):
        page = pdf.pages[page_num]
        text = page.extract_text()
        if not text:
            continue
        
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue
            
            # Check for table title
            line_lower = line.lower()
            if table_type == 'a' and 'table a' in line_lower and 'current sff' in line_lower:
                continue
            elif table_type == 'b' and 'table b' in line_lower and 'graduated' in line_lower:
                continue
            elif table_type == 'c' and 'table c' in line_lower and 'no longer participating' in line_lower:
                continue
            elif table_type == 'd' and 'table d' in line_lower and 'candidate' in line_lower:
                continue
            
            # Check for header row
            if any(keyword in line_lower for keyword in ['provider number', 'facility name', 'address']):
                continue
            
            # Look for CCN
            ccns = re.findall(ccn_pattern, line)
            if not ccns:
                continue
            
            ccn = None
            for candidate_ccn in ccns:
                if len(candidate_ccn) == 6 and candidate_ccn.isdigit():
                    ccn_pos = line.find(candidate_ccn)
                    if ccn_pos >= 0:
                        after_ccn = line[ccn_pos + 6:].strip()
                        if len(after_ccn) > 3:
                            ccn = candidate_ccn
                            break
            
            if not ccn or ccn in processed_ccns:
                continue
            
            # Parse the row (simplified - this is a fallback)
            row = parse_text_row(line, ccn, table_type)
            if row:
                rows.append(row)
                processed_ccns.add(ccn)
    
    return rows

def parse_text_row(line: str, ccn: str, table_type: str) -> Optional[List[str]]:
    """Parse a text row into a list of values (fallback method)."""
    # This is a simplified parser - the pdfplumber table extraction should work better
    # But this provides a fallback
    row = [''] * 10
    row[0] = ccn
    
    # Remove CCN from line
    line = line.replace(ccn, '', 1).strip()
    
    # Extract common patterns
    # Date
    date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', line)
    if date_match:
        date_str = f"{date_match.group(1).zfill(2)}/{date_match.group(2).zfill(2)}/{date_match.group(3)}"
        row[7] = date_str
        line = re.sub(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', '', line, count=1)
    
    # Met/Not Met
    if re.search(r'\bnot\s+met\b', line, re.IGNORECASE):
        row[8] = 'Not Met'
        line = re.sub(r'\bnot\s+met\b', '', line, flags=re.IGNORECASE, count=1)
    elif re.search(r'\bmet\b', line, re.IGNORECASE):
        row[8] = 'Met'
        line = re.sub(r'\bmet\b', '', line, flags=re.IGNORECASE, count=1)
    
    # Phone
    phone_match = re.search(r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', line)
    if phone_match:
        row[6] = phone_match.group(1).strip()
        line = re.sub(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '', line, count=1)
    
    # ZIP
    zip_match = re.search(r'\b(\d{5}(-\d{4})?)\b', line)
    if zip_match:
        row[5] = zip_match.group(1)
        line = re.sub(r'\b\d{5}(-\d{4})?\b', '', line, count=1)
    
    # State
    US_STATES = {'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'}
    state_candidates = re.findall(r'\b([A-Z]{2})\b', line)
    for state_candidate in state_candidates:
        if state_candidate in US_STATES:
            row[4] = state_candidate
            line = re.sub(r'\b' + state_candidate + r'\b', '', line, count=1)
            break
    
    # Months (last number 1-200)
    numbers = re.findall(r'\b\d+\b', line)
    for num_str in reversed(numbers):
        num = int(num_str)
        if 1 <= num <= 200:
            row[9] = num_str
            line = re.sub(r'\b' + num_str + r'\b', '', line, count=1)
            break
    
    # Remaining text is facility name, address, city
    remaining = re.sub(r'\s+', ' ', line).strip()
    parts = remaining.split()
    
    # Simple parsing - facility name first, then address, then city
    if parts:
        # Try to identify where address starts (usually a number)
        name_end = 0
        for i, part in enumerate(parts):
            if re.match(r'^\d+', part):
                name_end = i
                break
            name_end = i + 1
        
        if name_end > 0:
            row[1] = ' '.join(parts[:name_end])
        
        # Rest is address and city (simplified)
        if name_end < len(parts):
            remaining_parts = parts[name_end:]
            # Last capitalized word before state is usually city
            # But we already extracted state, so just put everything as address
            if remaining_parts:
                row[2] = ' '.join(remaining_parts)
    
    return row

def main():
    pdf_path = Path('pbj-wrapped/public/sff-posting-with-candidate-list-november-2025.pdf')
    
    if not pdf_path.exists():
        print(f"Error: PDF file not found at {pdf_path}")
        sys.exit(1)
    
    print(f"Extracting tables from {pdf_path.name}...")
    tables = extract_tables_from_pdf(pdf_path)
    
    # Write CSV files
    output_dir = Path('pbj-wrapped/public')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for table_type, rows in tables.items():
        if not rows:
            print(f"\nWarning: Table {table_type.upper()} is empty!")
            continue
        
        csv_path = output_dir / f'sff_table_{table_type}.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        print(f"  Saved {csv_path} ({len(rows)} rows)")
    
    print("\nExtraction complete!")
    
    # Print summary
    print("\nSummary:")
    for table_type, rows in tables.items():
        data_rows = len(rows) - 1 if rows else 0
        print(f"  Table {table_type.upper()}: {data_rows} facilities")
    
    return tables

if __name__ == '__main__':
    main()
