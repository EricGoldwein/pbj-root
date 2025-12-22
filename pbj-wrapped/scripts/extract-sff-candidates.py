"""
Extract SFF candidate months from PDF and create a mapping file.
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
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
    return text

def extract_sff_candidates(text, pdf_path=None):
    """
    Extract SFF candidate CCNs and their months from the PDF text.
    Looks for patterns like:
    - CCN numbers (6 digits)
    - Month references (e.g., "November 2025", "Nov 2025", "11/2025")
    """
    # Pattern to match CCN (6-digit number)
    ccn_pattern = r'\b\d{6}\b'
    
    # Pattern to match months
    month_patterns = [
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\s\.]+\s*(\d{4})',
        r'(\d{1,2})[/-](\d{4})',  # MM/YYYY or M/YYYY
    ]
    
    # Month name to number mapping
    month_map = {
        'january': 1, 'jan': 1,
        'february': 2, 'feb': 2,
        'march': 3, 'mar': 3,
        'april': 4, 'apr': 4,
        'may': 5,
        'june': 6, 'jun': 6,
        'july': 7, 'jul': 7,
        'august': 8, 'aug': 8,
        'september': 9, 'sep': 9,
        'october': 10, 'oct': 10,
        'november': 11, 'nov': 11,
        'december': 12, 'dec': 12,
    }
    
    # Find all CCNs
    ccns = re.findall(ccn_pattern, text)
    
    # Extract date from filename (sff-posting-with-candidate-list-november-2025.pdf)
    doc_month = 11  # Default to November
    doc_year = 2025  # Default to 2025
    
    if pdf_path:
        pdf_path_obj = Path(pdf_path)
        filename = pdf_path_obj.stem.lower()
        
        # Try to extract from filename
        if 'november' in filename or 'nov' in filename:
            doc_month = 11
        elif 'december' in filename or 'dec' in filename:
            doc_month = 12
        elif 'october' in filename or 'oct' in filename:
            doc_month = 10
        # ... add more months as needed
        
        # Extract year from filename (look for 4-digit year)
        year_match = re.search(r'(\d{4})', filename)
        if year_match:
            year_candidate = int(year_match.group(1))
            if 2000 <= year_candidate <= 2100:  # Reasonable year range
                doc_year = year_candidate
    
    # Also try to find in text (but be more careful)
    for pattern in month_patterns:
        matches = re.finditer(pattern, text[:5000], re.IGNORECASE)  # Only check first 5000 chars
        for match in matches:
            if len(match.groups()) == 2:
                month_str = match.group(1).lower()
                year_str = match.group(2)
                if month_str in month_map:
                    year_candidate = int(year_str)
                    if 2000 <= year_candidate <= 2100:
                        doc_month = month_map[month_str]
                        doc_year = year_candidate
                        break
                elif month_str.isdigit() and len(month_str) <= 2:
                    month_candidate = int(month_str)
                    year_candidate = int(year_str)
                    if 1 <= month_candidate <= 12 and 2000 <= year_candidate <= 2100:
                        doc_month = month_candidate
                        doc_year = year_candidate
                        break
        if doc_year != 2025:  # If we found a valid year, break
            break
    
    # Create mapping: CCN -> {month, year}
    candidate_months = {}
    
    # Look for candidate list section
    lines = text.split('\n')
    in_candidate_section = False
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if 'candidate' in line_lower and ('list' in line_lower or 'sff' in line_lower):
            in_candidate_section = True
            continue
        
        if in_candidate_section:
            # Look for CCNs in this line
            ccns_in_line = re.findall(ccn_pattern, line)
            for ccn in ccns_in_line:
                # Only add if it's a valid 6-digit CCN
                if len(ccn) == 6 and ccn.isdigit():
                    candidate_months[ccn] = {
                        'month': doc_month,
                        'year': doc_year,
                        'month_name': 'November',  # Default
                        'source': 'pdf_extraction'
                    }
    
    return candidate_months, doc_month, doc_year

def main():
    pdf_path = Path(__file__).parent.parent / 'public' / 'sff-posting-with-candidate-list-november-2025.pdf'
    
    if not pdf_path.exists():
        print(f"Error: PDF file not found at {pdf_path}")
        sys.exit(1)
    
    print(f"Extracting text from {pdf_path}...")
    text = extract_text_from_pdf(pdf_path)
    
    print("Extracting SFF candidate data...")
    candidate_months, doc_month, doc_year = extract_sff_candidates(text, pdf_path)
    
    print(f"\nFound {len(candidate_months)} SFF candidates")
    print(f"Document date: {doc_month}/{doc_year}")
    
    # Save to JSON
    output_path = Path(__file__).parent.parent / 'public' / 'sff-candidate-months.json'
    with open(output_path, 'w') as f:
        json.dump({
            'document_date': {
                'month': doc_month,
                'year': doc_year,
                'month_name': 'November'
            },
            'candidates': candidate_months,
            'total_count': len(candidate_months)
        }, f, indent=2)
    
    print(f"\nSaved to {output_path}")
    
    # Print first few for verification
    print("\nFirst 10 candidates:")
    for i, (ccn, data) in enumerate(list(candidate_months.items())[:10]):
        print(f"  {ccn}: {data['month_name']} {data['year']}")
    
    return candidate_months

if __name__ == '__main__':
    main()

