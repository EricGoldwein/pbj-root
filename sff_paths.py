"""Canonical paths for CMS Special Focus Facility (SFF) raw sources and derived artifacts."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent

SFF_RAW_ROOT = REPO_ROOT / "data_sources" / "cms" / "sff" / "raw"
SFF_DERIVED_ROOT = REPO_ROOT / "data" / "derived" / "sff"
SFF_TABLES_DIR = SFF_DERIVED_ROOT / "tables"
SFF_FACILITIES_JSON = SFF_DERIVED_ROOT / "sff_facilities.json"
SFF_FACILITIES_CSV = SFF_DERIVED_ROOT / "sff_facilities.csv"
SFF_CURRENT_RELEASE_FILE = REPO_ROOT / "data_sources" / "cms" / "sff" / "current_release.json"

SFF_PUBLIC_DIR = REPO_ROOT / "pbj-wrapped" / "public"
SFF_PUBLIC_JSON = SFF_PUBLIC_DIR / "sff-facilities.json"
SFF_PUBLIC_CANDIDATE_MONTHS_JSON = SFF_PUBLIC_DIR / "sff-candidate-months.json"

MONTH_TO_NUM = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
NUM_TO_MONTH_NAME = {v: k.capitalize() for k, v in MONTH_TO_NUM.items()}

_PDF_DATE_RE = re.compile(r"candidate-list-([a-z]+)-(\d{4})", re.IGNORECASE)


def extract_pdf_release_parts(filename: str) -> Optional[Tuple[int, int, str]]:
    """Return (year, month_num, month_name) from an SFF posting PDF filename."""
    match = _PDF_DATE_RE.search((filename or "").lower())
    if not match:
        return None
    month_name = match.group(1).lower()
    month_num = MONTH_TO_NUM.get(month_name)
    if not month_num:
        return None
    return int(match.group(2)), month_num, month_name.capitalize()


def release_dir_for_pdf(filename: str) -> str:
    """Folder name YYYY-MM for a posting PDF filename."""
    parts = extract_pdf_release_parts(filename)
    if not parts:
        raise ValueError(f"Cannot derive release folder from SFF PDF filename: {filename}")
    year, month_num, _ = parts
    return f"{year:04d}-{month_num:02d}"


def list_raw_release_dirs() -> list[Path]:
    """All versioned raw release directories under SFF_RAW_ROOT."""
    if not SFF_RAW_ROOT.is_dir():
        return []
    return sorted(p for p in SFF_RAW_ROOT.iterdir() if p.is_dir())


def find_raw_pdfs() -> list[Path]:
    """All CMS SFF posting PDFs in the raw archive."""
    pdfs: list[Path] = []
    for release_dir in list_raw_release_dirs():
        pdfs.extend(
            p
            for p in release_dir.glob("sff-posting-with-candidate-list*.pdf")
            if p.is_file()
        )
    return pdfs


def find_latest_raw_pdf() -> Optional[Path]:
    """Newest SFF posting PDF by YYYY-MM in filename."""
    parsed: list[tuple[Path, Tuple[int, int]]] = []
    for pdf in find_raw_pdfs():
        parts = extract_pdf_release_parts(pdf.name)
        if parts:
            year, month_num, _ = parts
            parsed.append((pdf, (year, month_num)))
    if not parsed:
        return None
    return max(parsed, key=lambda item: item[1])[0]


def sff_facilities_json_candidates() -> list[Path]:
    """Load order for app-facing SFF JSON (canonical derived first)."""
    return [
        SFF_FACILITIES_JSON,
        SFF_PUBLIC_JSON,
        REPO_ROOT / "pbj-wrapped" / "dist" / "sff-facilities.json",
        REPO_ROOT / "sff-facilities.json",
    ]


def sff_pdf_serve_candidates(filename: str) -> list[Path]:
    """Resolve a hosted SFF PDF filename for Flask static download."""
    safe = Path(filename).name
    candidates = [
        SFF_PUBLIC_DIR / safe,
        REPO_ROOT / "pbj-wrapped" / "public" / safe,
    ]
    parts = extract_pdf_release_parts(safe)
    if parts:
        year, month_num, _ = parts
        release_dir = SFF_RAW_ROOT / f"{year:04d}-{month_num:02d}"
        candidates.insert(0, release_dir / safe)
    return candidates
