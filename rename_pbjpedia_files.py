#!/usr/bin/env python3
"""
Rename PBJpedia markdown files based on their content/titles.
"""
import re
from pathlib import Path

# Mapping based on content analysis
FILE_MAPPINGS = {
    "pbjpedia-creation-guide.md": "pbjpedia-data-limitations.md",  # "# Data Limitations"
    "pbjpedia-creation-guide-3.md": "pbjpedia-history.md",  # "# History of PBJ"
    "pbjpedia-creation-guide-4.md": "pbjpedia-metrics.md",  # "# PBJ Metrics"
    "pbjpedia-creation-guide-5.md": "pbjpedia-non-nursing-staff.md",  # "# Non‑Nursing Staff in PBJ"
    "pbjpedia-creation-guide-6.md": "pbjpedia-state-standards.md",  # "# State Staffing Standards"
    "pbjpedia-creation-guide-7.md": "pbjpedia-methodology.md",  # "# PBJ Methodology"
    "pbjpedia-creation-guide-8.md": "pbjpedia-overview.md",  # "# PBJ Overview"
    "pbjpedianonnurse.md": None,  # Duplicate of non-nursing-staff, will be deleted
}

def get_file_title(file_path: Path) -> str:
    """Extract the main title from a markdown file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Look for the first # heading after frontmatter
            lines = content.split('\n')
            in_frontmatter = False
            for line in lines:
                if line.strip() == '---':
                    in_frontmatter = not in_frontmatter
                    continue
                if not in_frontmatter and line.strip().startswith('# '):
                    # Remove markdown heading and clean up
                    title = line.strip()[2:].strip()
                    # Remove anchor tags
                    title = re.sub(r'<a[^>]*></a>', '', title)
                    # Replace non-breaking hyphens with regular hyphens for display
                    title_display = title.replace('\u2011', '-').replace('\u2010', '-')
                    return title_display
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return ""

def rename_files(pbjpedia_dir: Path):
    """Rename files according to their content."""
    print("Renaming PBJpedia markdown files based on content...\n")
    
    renamed_count = 0
    deleted_count = 0
    
    for old_name, new_name in FILE_MAPPINGS.items():
        old_path = pbjpedia_dir / old_name
        
        if not old_path.exists():
            print(f"[SKIP] {old_name} not found")
            continue
        
        # Get actual title for verification
        title = get_file_title(old_path)
        print(f"File: {old_name}")
        print(f"  Title: {title}")
        
        if new_name is None:
            # Delete duplicate
            try:
                old_path.unlink()
                print(f"  [DELETE] Removed duplicate file")
                deleted_count += 1
            except Exception as e:
                print(f"  [ERROR] Could not delete: {e}")
        else:
            new_path = pbjpedia_dir / new_name
            
            if new_path.exists() and new_path != old_path:
                print(f"  [WARNING] Target file {new_name} already exists, skipping")
                continue
            
            try:
                old_path.rename(new_path)
                print(f"  [RENAME] {old_name} -> {new_name}")
                renamed_count += 1
            except Exception as e:
                print(f"  [ERROR] Could not rename: {e}")
        
        print()
    
    print(f"Summary: {renamed_count} file(s) renamed, {deleted_count} duplicate(s) deleted")

if __name__ == "__main__":
    pbjpedia_dir = Path(r"C:\Users\egold\PycharmProjects\pbj-root\PBJPedia")
    
    if not pbjpedia_dir.exists():
        print(f"ERROR: Directory not found: {pbjpedia_dir}")
        exit(1)
    
    rename_files(pbjpedia_dir)

