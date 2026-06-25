#!/usr/bin/env python3
"""
Extract SFF candidate months data from PDF
"""
import sys
import os
import re
from pathlib import Path

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    try:
        import pypdf
        HAS_PYPDF2 = True
        PyPDF2 = pypdf
    except ImportError:
        HAS_PYPDF2 = False

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    if not HAS_PYPDF2:
        print("ERROR: PyPDF2 or pypdf not available. Install with: pip install PyPDF2 or pip install pypdf")
        return None
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
    except Exception as e:
        print(f"ERROR reading PDF: {e}")
        return None


MONTH_TO_NUM = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
}


def _extract_pdf_date_parts(filename: str):
    match = re.search(r'candidate-list-([a-z]+)-(\d{4})', filename.lower())
    if not match:
        return None
    month_num = MONTH_TO_NUM.get(match.group(1))
    if not month_num:
        return None
    return (int(match.group(2)), month_num)


def _find_latest_sff_pdf(public_dir: Path) -> Path | None:
    candidates = [p for p in public_dir.glob('sff-posting*candidate-list*.pdf') if p.is_file()]
    if not candidates:
        return None
    parsed = [(p, _extract_pdf_date_parts(p.name)) for p in candidates]
    valid = [(p, parts) for p, parts in parsed if parts is not None]
    if valid:
        return max(valid, key=lambda x: x[1])[0]
    return max(candidates, key=lambda p: p.stat().st_mtime)

if __name__ == "__main__":
    latest = _find_latest_sff_pdf(Path("public"))
    if latest is None:
        print("ERROR: No matching SFF PDF found in ./public")
        sys.exit(1)
    pdf_path = str(latest)
    
    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF file not found at {pdf_path}")
        sys.exit(1)
    
    text = extract_text_from_pdf(pdf_path)
    if text:
        print(text)
    else:
        sys.exit(1)

