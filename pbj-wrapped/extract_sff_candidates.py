#!/usr/bin/env python3
"""
Extract SFF candidate months data from PDF
"""
import sys
import os

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

if __name__ == "__main__":
    pdf_path = os.path.join("public", "sff-posting-with-candidate-list-november-2025.pdf")
    
    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF file not found at {pdf_path}")
        sys.exit(1)
    
    text = extract_text_from_pdf(pdf_path)
    if text:
        print(text)
    else:
        sys.exit(1)

