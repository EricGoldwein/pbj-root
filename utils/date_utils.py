#!/usr/bin/env python3
"""
Date utilities for PBJ data processing
Provides functions to get the latest data periods and date information
"""
import csv
import os
import re
from datetime import datetime
from pathlib import Path


MONTH_LOOKUP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _format_month_year(year, month):
    try:
        return datetime(int(year), int(month), 1).strftime("%B %Y")
    except Exception:
        return None


def _parse_provider_filename(path_obj):
    """Parse provider info date from filename patterns."""
    stem = path_obj.stem
    lower = stem.lower()
    # ProviderInfoNorm_2026_04
    m_norm = re.search(r'providerinfonorm[_-](\d{4})[_-](\d{1,2})', lower)
    if m_norm:
        y, mo = int(m_norm.group(1)), int(m_norm.group(2))
        if 1 <= mo <= 12:
            return y, mo
    # NH_ProviderInfo_Mar2026 / NH_ProviderInfo_March_2026 / ..._2026_03
    m_word = re.search(r'providerinfo[_-]?([a-z]+)[_-]?(\d{4})', lower)
    if m_word:
        mo = MONTH_LOOKUP.get(m_word.group(1))
        if mo:
            return int(m_word.group(2)), mo
    m_num = re.search(r'providerinfo[_-]?(\d{4})[_-]?(\d{1,2})', lower)
    if m_num:
        y, mo = int(m_num.group(1)), int(m_num.group(2))
        if 1 <= mo <= 12:
            return y, mo
    return None


def _parse_ownership_filename(path_obj):
    """Parse ownership date from filename patterns."""
    stem = path_obj.stem
    lower = stem.lower()
    # SNF_All_Owners_2026.04.01 / ..._2026_04_01
    m_iso = re.search(r'(\d{4})[._-](\d{1,2})(?:[._-](\d{1,2}))?', lower)
    if m_iso:
        y, mo = int(m_iso.group(1)), int(m_iso.group(2))
        if 1 <= mo <= 12:
            return y, mo
    # SNF_All_Owners_Jan_2026 / ..._January2026
    m_word = re.search(r'owners[_-]?([a-z]+)[_-]?(\d{4})', lower)
    if m_word:
        mo = MONTH_LOOKUP.get(m_word.group(1))
        if mo:
            return int(m_word.group(2)), mo
    return None


def _provider_info_month_candidates(base_dir: Path) -> list[tuple[int, int]]:
    """Months present in deployed Norm snapshots and/or local NH CMS extracts."""
    candidates: set[tuple[int, int]] = set()
    provider_dir = base_dir / "provider_info"
    for pattern in ("ProviderInfoNorm_*.csv", "NH_ProviderInfo_*.csv"):
        for p in provider_dir.glob(pattern):
            parsed = _parse_provider_filename(p)
            if parsed:
                candidates.add(parsed)
    return sorted(candidates, reverse=True)


def _latest_two_provider_info_months(base_dir):
    candidates = _provider_info_month_candidates(base_dir)
    if not candidates:
        return None, None
    latest = _format_month_year(candidates[0][0], candidates[0][1])
    previous = (
        _format_month_year(candidates[1][0], candidates[1][1])
        if len(candidates) > 1
        else latest
    )
    return latest, previous


def newest_provider_snapshot_path(base_dir: Path) -> Path | None:
    """Best provider snapshot file for the newest processing month (NH preferred, else Norm)."""
    candidates = _provider_info_month_candidates(base_dir)
    if not candidates:
        return None
    year, month = candidates[0]
    month_names = (
        "",
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    )
    if month < 1 or month > 12:
        return None
    provider_dir = base_dir / "provider_info"
    for name in (
        f"NH_ProviderInfo_{month_names[month]}{year}.csv",
        f"NH_ProviderInfo_{month_names[month]}_{year}.csv",
        f"ProviderInfoNorm_{year}_{month:02d}.csv",
    ):
        path = provider_dir / name
        if path.is_file():
            return path
    return None


def _latest_affiliated_entity_month(base_dir):
    """Month label for the newest SNF_All_Owners*.csv (same file as owner profiles)."""
    del base_dir  # discovery uses repo ownership/ via owner_profile
    try:
        from ownership.owner_profile import snf_owners_release_month_year
    except ImportError:
        return None
    ym = snf_owners_release_month_year()
    if not ym:
        return None
    return _format_month_year(ym[0], ym[1])


def get_latest_data_periods():
    """
    Get the latest data periods information for PBJ data.
    Reads from CSV files to determine actual data range and quarter count.
    
    Returns:
        dict: Dictionary containing:
            - data_range: String range like '2017-2025' (from actual data)
            - quarter_count: Integer count of quarters (from actual data)
            - provider_info_latest: Latest provider info date (e.g., 'February 2026')
            - provider_info_previous: Previous provider info date (e.g., 'June 2025')
            - affiliated_entity_latest: Latest affiliated entity date (e.g., 'July 2025')
            - current_year: Current year as integer
    """
    # Calculate current year
    current_year = datetime.now().year
    base_dir = Path(__file__).resolve().parent.parent
    
    # Try to read from CSV files to get actual data range
    data_range = '2017-2025'  # Default fallback
    quarter_count = 33  # Default fallback
    
    try:
        # Read national quarterly metrics to get data range
        csv_path = base_dir / 'national_quarterly_metrics.csv'
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                quarters = []
                for row in reader:
                    if row.get('CY_Qtr'):
                        quarters.append(row['CY_Qtr'])
                
                if quarters:
                    # Sort quarters
                    quarters.sort()
                    first_quarter = quarters[0]
                    last_quarter = quarters[-1]
                    
                    # Extract years
                    first_match = re.match(r'(\d{4})Q\d', first_quarter)
                    last_match = re.match(r'(\d{4})Q\d', last_quarter)
                    
                    if first_match and last_match:
                        first_year = first_match.group(1)
                        last_year = last_match.group(1)
                        data_range = f'{first_year}-{last_year}'
                        quarter_count = len(quarters)
    except Exception as e:
        # If reading CSV fails, use defaults
        print(f"Warning: Could not read CSV files for date range: {e}")
    
    provider_latest, provider_previous = _latest_two_provider_info_months(base_dir)
    affiliated_latest = _latest_affiliated_entity_month(base_dir)

    return {
        'data_range': data_range,
        'quarter_count': quarter_count,
        'provider_info_latest': provider_latest or 'February 2026',
        'provider_info_previous': provider_previous or 'January 2026',
        'affiliated_entity_latest': affiliated_latest or 'July 2025',
        'current_year': current_year
    }


def get_latest_update_month_year():
    """
    Get the month and year of the latest data update.
    This is currently hardcoded but could be made dynamic by reading the latest quarter.
    """
    periods = get_latest_data_periods()
    return periods.get("provider_info_latest") or "February 2026"
