#!/usr/bin/env python3
"""
Convert Word documents (.docx) to Markdown (.md) files.
Detects duplicates and removes them while preserving all content.
"""
import os
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple
import sys

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False
    print("ERROR: python-docx not installed. Install with: pip install python-docx")

try:
    import mammoth
    HAS_MAMMOTH = True
except ImportError:
    HAS_MAMMOTH = False
    print("WARNING: mammoth not installed. Will use basic text extraction.")
    print("For better formatting, install with: pip install mammoth")


def extract_text_from_docx(docx_path: Path) -> str:
    """Extract text content from a Word document."""
    try:
        if HAS_MAMMOTH:
            # Use mammoth for better Markdown conversion
            with open(docx_path, "rb") as docx_file:
                result = mammoth.convert_to_markdown(docx_file)
                return result.value
        elif HAS_DOCX:
            # Fallback to python-docx for basic text extraction
            doc = Document(docx_path)
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
            return "\n\n".join(text_parts)
        else:
            raise ImportError("No docx library available")
    except Exception as e:
        print(f"ERROR reading {docx_path}: {e}")
        return ""


def calculate_content_hash(content: str) -> str:
    """Calculate a hash of the content to detect duplicates."""
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def sanitize_filename(filename: str, preserve_number: bool = False) -> str:
    """Convert filename to a clean markdown filename."""
    import re
    # Remove .docx extension
    name = filename.replace('.docx', '')
    
    # Extract number from parentheses if preserve_number is True
    number_match = re.search(r'\((\d+)\)', name)
    number = number_match.group(1) if number_match else None
    
    # Always remove numbers in parentheses first to get base name
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)
    
    # Replace spaces and special chars with hyphens
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[-\s]+', '-', name)
    base_name = name.strip('-').lower()
    
    # Add number suffix if preserving
    if preserve_number and number:
        return f"{base_name}-{number}.md"
    
    return base_name + '.md'


def convert_docx_to_markdown(docx_dir: Path) -> None:
    """Convert all .docx files in directory to .md files, removing duplicates."""
    docx_files = list(docx_dir.glob("*.docx"))
    
    if not docx_files:
        print(f"No .docx files found in {docx_dir}")
        return
    
    print(f"Found {len(docx_files)} Word document(s)")
    
    # Extract content and calculate hashes
    file_contents: Dict[Path, str] = {}
    content_hashes: Dict[str, List[Path]] = {}
    
    for docx_file in docx_files:
        print(f"Processing: {docx_file.name}")
        content = extract_text_from_docx(docx_file)
        if not content.strip():
            print(f"  WARNING: {docx_file.name} appears to be empty or could not be read")
            continue
        
        file_contents[docx_file] = content
        content_hash = calculate_content_hash(content)
        
        if content_hash not in content_hashes:
            content_hashes[content_hash] = []
        content_hashes[content_hash].append(docx_file)
    
    # Identify duplicates
    duplicates_to_delete: List[Path] = []
    files_to_convert: List[Tuple[Path, str]] = []
    
    print(f"\nAnalyzing {len(content_hashes)} unique content hash(es)...")
    for content_hash, files in content_hashes.items():
        if len(files) > 1:
            print(f"\n[DUPLICATE DETECTED] Found {len(files)} file(s) with identical content:")
            for f in files:
                print(f"  - {f.name}")
            
            # Keep the first file (or the one without a number in parentheses)
            # Sort to prefer files without numbers, then by name
            files_sorted = sorted(files, key=lambda f: ('(' in f.name, f.name))
            keep_file = files_sorted[0]
            
            print(f"  [KEEP] {keep_file.name}")
            files_to_convert.append((keep_file, file_contents[keep_file]))
            
            # Mark others for deletion
            for dup_file in files_sorted[1:]:
                duplicates_to_delete.append(dup_file)
                print(f"  [DELETE] {dup_file.name}")
        else:
            # Unique file, convert it
            files_to_convert.append((files[0], file_contents[files[0]]))
    
    # Convert to Markdown
    print(f"\nConverting {len(files_to_convert)} unique file(s) to Markdown...")
    used_filenames = set()
    
    for docx_file, content in files_to_convert:
        # Try base filename first
        md_filename = sanitize_filename(docx_file.name, preserve_number=False)
        
        # If filename collision, preserve number or add hash
        if md_filename in used_filenames:
            md_filename = sanitize_filename(docx_file.name, preserve_number=True)
            # If still collision, add content hash
            if md_filename in used_filenames:
                content_hash_short = calculate_content_hash(content)[:8]
                base_name = md_filename.replace('.md', '')
                md_filename = f"{base_name}-{content_hash_short}.md"
        
        used_filenames.add(md_filename)
        md_path = docx_dir / md_filename
        
        # Add frontmatter with original filename
        markdown_content = f"""---
original_file: {docx_file.name}
---

{content}
"""
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        print(f"  [OK] Created: {md_filename} (from {docx_file.name})")
    
    # Delete duplicate files
    if duplicates_to_delete:
        print(f"\nDeleting {len(duplicates_to_delete)} duplicate file(s)...")
        for dup_file in duplicates_to_delete:
            try:
                dup_file.unlink()
                print(f"  [OK] Deleted: {dup_file.name}")
            except Exception as e:
                print(f"  [ERROR] Error deleting {dup_file.name}: {e}")
    else:
        print("\nNo duplicates found.")
    
    print(f"\n[SUCCESS] Conversion complete! {len(files_to_convert)} Markdown file(s) created.")


if __name__ == "__main__":
    pbjpedia_dir = Path(r"C:\Users\egold\PycharmProjects\pbj-root\PBJPedia")
    
    if not pbjpedia_dir.exists():
        print(f"ERROR: Directory not found: {pbjpedia_dir}")
        sys.exit(1)
    
    convert_docx_to_markdown(pbjpedia_dir)

