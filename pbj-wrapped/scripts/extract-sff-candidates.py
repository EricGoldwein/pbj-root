"""
Extract SFF candidate months from PDF and create a mapping file.
Improved version that extracts ALL CCNs and months data more thoroughly.
"""
import PyPDF2
import json
import re
import sys
from pathlib import Path

def extract_text_from_pdf(pdf_path):
    """Extract all text from PDF."""
    text = ""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        print(f"PDF has {len(pdf_reader.pages)} pages")
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            text += page_text + "\n"
            if page_num < 3:  # Debug: print first few pages
                print(f"Page {page_num + 1} preview (first 200 chars): {page_text[:200]}")
    return text

def extract_sff_candidates(text, pdf_path=None):
    """
    Extract SFF candidate CCNs and their months as SFF from the PDF text.
    More thorough extraction that:
    1. Finds ALL tables with CCNs
    2. Extracts months data from multiple column positions
    3. Handles both SFF and Candidate tables
    """
    # Pattern to match CCN (6-digit number)
    ccn_pattern = r'\b\d{6}\b'
    
    # Extract date from filename
    doc_month = 12  # Default to December
    doc_year = 2025  # Default to 2025
    
    if pdf_path:
        pdf_path_obj = Path(pdf_path)
        filename = pdf_path_obj.stem.lower()
        
        # Try to extract from filename
        month_map = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
            'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
            'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
            'august': 8, 'aug': 8, 'september': 9, 'sep': 9,
            'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }
        
        for month_name, month_num in month_map.items():
            if month_name in filename:
                doc_month = month_num
                break
        
        # Extract year from filename
        year_match = re.search(r'(\d{4})', filename)
        if year_match:
            year_candidate = int(year_match.group(1))
            if 2000 <= year_candidate <= 2100:
                doc_year = year_candidate
    
    # Create mapping: CCN -> {months_as_sff, month, year}
    candidate_months = {}
    
    lines = text.split('\n')
    print(f"Total lines in PDF: {len(lines)}")
    
    # Strategy 1: Look for table sections with headers
    # Find all potential table headers
    table_headers = []
    for i, line in enumerate(lines):
        line_lower = line.lower()
        # Look for various table header patterns
        if any(keyword in line_lower for keyword in [
            'provider number', 'facility name', 'months as', 'months as an sff',
            'table d', 'sff candidate', 'special focus facility'
        ]):
            table_headers.append((i, line))
    
    print(f"Found {len(table_headers)} potential table headers")
    
    # Strategy 2: Find ALL 6-digit numbers that could be CCNs
    all_ccns = set()
    for line in lines:
        ccns = re.findall(ccn_pattern, line)
        for ccn in ccns:
            if len(ccn) == 6 and ccn.isdigit():
                all_ccns.add(ccn)
    
    print(f"Found {len(all_ccns)} unique 6-digit numbers (potential CCNs)")
    
    # Strategy 3: For each potential CCN, try to find months value on same line or nearby
    for ccn in all_ccns:
        months_value = None
        
        # Search for this CCN in the text
        for i, line in enumerate(lines):
            if ccn in line:
                # Extract all numbers from this line
                numbers = re.findall(r'\b\d+\b', line)
                
                # Find the months value (should be 1-100, and not the CCN itself)
                for num_str in numbers:
                    if num_str == ccn:
                        continue
                    num = int(num_str)
                    # Months as SFF should be between 1 and 100
                    if 1 <= num <= 100:
                        months_value = num
                        break
                
                # If not found on same line, check next few lines
                if months_value is None:
                    for j in range(i + 1, min(i + 5, len(lines))):
                        next_line = lines[j]
                        numbers = re.findall(r'\b\d+\b', next_line)
                        for num_str in numbers:
                            num = int(num_str)
                            if 1 <= num <= 100:
                                months_value = num
                                break
                        if months_value:
                            break
                
                if months_value:
                    break
        
        # If we found a months value, store it
        if months_value is not None:
            candidate_months[ccn] = {
                'months_as_sff': months_value,
                'month': doc_month,
                'year': doc_year,
                'month_name': ['', 'January', 'February', 'March', 'April', 'May', 'June', 
                              'July', 'August', 'September', 'October', 'November', 'December'][doc_month],
                'source': 'pdf_extraction'
            }
        else:
            # Store even without months value (we'll try to match later)
            candidate_months[ccn] = {
                'months_as_sff': None,
                'month': doc_month,
                'year': doc_year,
                'month_name': ['', 'January', 'February', 'March', 'April', 'May', 'June', 
                              'July', 'August', 'September', 'October', 'November', 'December'][doc_month],
                'source': 'pdf_extraction'
            }
    
    # Strategy 4: More targeted table parsing
    # Look for structured table patterns
    in_table = False
    table_start = -1
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        
        # Detect table start
        if not in_table and ('provider number' in line_lower or 'table' in line_lower):
            if 'months' in line_lower or 'facility' in line_lower:
                in_table = True
                table_start = i
                continue
        
        # If in table, look for CCN rows
        if in_table:
            # Check if this line has a CCN
            ccns_in_line = re.findall(ccn_pattern, line)
            if ccns_in_line:
                ccn = ccns_in_line[0]
                if len(ccn) == 6 and ccn.isdigit():
                    # Extract numbers from this line
                    numbers = re.findall(r'\b\d+\b', line)
                    
                    # Find months value (last reasonable number that's not the CCN)
                    for num_str in reversed(numbers):
                        if num_str == ccn:
                            continue
                        num = int(num_str)
                        if 1 <= num <= 100:
                            if ccn not in candidate_months or candidate_months[ccn]['months_as_sff'] is None:
                                candidate_months[ccn] = {
                                    'months_as_sff': num,
                                    'month': doc_month,
                                    'year': doc_year,
                                    'month_name': ['', 'January', 'February', 'March', 'April', 'May', 'June', 
                                                  'July', 'August', 'September', 'October', 'November', 'December'][doc_month],
                                    'source': 'pdf_extraction'
                                }
                            break
            
            # Check if we've left the table (blank line or new section)
            if not line.strip() and i > table_start + 10:
                in_table = False
    
    # Filter out entries without months values for final output
    # But keep them for debugging
    final_candidates = {ccn: data for ccn, data in candidate_months.items() if data.get('months_as_sff') is not None}
    
    print(f"\nExtraction summary:")
    print(f"  Total CCNs found: {len(candidate_months)}")
    print(f"  CCNs with months data: {len(final_candidates)}")
    print(f"  CCNs without months data: {len(candidate_months) - len(final_candidates)}")
    
    return final_candidates, doc_month, doc_year

def main():
    pdf_path = Path(__file__).parent.parent / 'public' / 'sff-posting-with-candidate-list-november-2025.pdf'
    
    if not pdf_path.exists():
        print(f"Error: PDF file not found at {pdf_path}")
        sys.exit(1)
    
    print(f"Extracting text from {pdf_path}...")
    text = extract_text_from_pdf(pdf_path)
    
    print(f"\nText length: {len(text)} characters")
    print("Extracting SFF candidate data...")
    candidate_months, doc_month, doc_year = extract_sff_candidates(text, pdf_path)
    
    print(f"\nFound {len(candidate_months)} SFF candidates with months data")
    print(f"Document date: {doc_month}/{doc_year}")
    
    month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June', 
                   'July', 'August', 'September', 'October', 'November', 'December']
    month_name = month_names[doc_month] if 1 <= doc_month <= 12 else 'December'
    
    # Save to JSON
    output_path = Path(__file__).parent.parent / 'public' / 'sff-candidate-months.json'
    with open(output_path, 'w') as f:
        json.dump({
            'document_date': {
                'month': doc_month,
                'year': doc_year,
                'month_name': month_name
            },
            'candidates': candidate_months,
            'total_count': len(candidate_months)
        }, f, indent=2)
    
    print(f"\nSaved to {output_path}")
    
    # Print first few for verification
    print("\nFirst 10 candidates:")
    for i, (ccn, data) in enumerate(list(candidate_months.items())[:10]):
        print(f"  {ccn}: {data.get('months_as_sff', 'N/A')} months")
    
    return candidate_months

if __name__ == '__main__':
    main()
