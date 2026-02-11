"""
FEC API Client Module

This module provides functions to query the Federal Election Commission (FEC) API
to look up political donations by contributor name and to build docquery links for
Schedule A receipts.

USAGE:
1. Add your FEC API key to the FEC_API_KEY constant below, or set it as an environment variable
2. Use the query_donations_by_name() function to search for donations by contributor name
3. Use build_schedule_a_docquery_link() to reliably construct docquery URLs (uses
   image_number from Schedule A when present, else fetches from /filings/ for the same committee/period)
4. The module handles rate limiting and API response parsing

Docquery URL for Schedule A: https://docquery.fec.gov/cgi-bin/forms/{committee_id}/{file_number}/sa/ALL
Example: https://docquery.fec.gov/cgi-bin/forms/C00892471/1930534/sa/ALL
The path segment is file_number from OpenFEC: Schedule A returns file_number (e.g. 1930534); /filings/ returns file_number. Do NOT use image_number (long page id) or sub_id (long line-item id) from Schedule A.

FEC API Documentation: https://api.open.fec.gov/developers/
"""

import requests
import time
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import pandas as pd

# ---------------------------
# CONFIGURATION
# ---------------------------

# Try to load from .env file first (safer - not in git)
def load_env_file():
    """Load environment variables from .env file if it exists"""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
        except Exception as e:
            print(f"Warning: Could not load .env file: {e}")

# Load .env file if it exists
load_env_file()

# FEC API Key - Load from .env file, environment variable, or set here as last resort
# SAFEST: Create donor/.env file with: FEC_API_KEY=your_key_here
# The .env file is gitignored and won't be committed
FEC_API_KEY = os.getenv("FEC_API_KEY", "YOUR_API_KEY_HERE")

# Timeout in seconds for FEC API requests (env FEC_API_TIMEOUT)
FEC_API_TIMEOUT = int(os.getenv("FEC_API_TIMEOUT", "90"))

# FEC API Base URL
FEC_API_BASE_URL = "https://api.open.fec.gov/v1"

# Docquery base URL for Schedule A receipt viewer (no trailing slash)
DOCQUERY_BASE_URL = "https://docquery.fec.gov/cgi-bin/forms"

# Rate limiting: FEC API allows 120 requests per minute
REQUESTS_PER_MINUTE = 120
MIN_REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE  # ~0.5 seconds between requests

# Track last request time for rate limiting
_last_request_time = 0


def _rate_limit():
    """Enforce rate limiting between API requests"""
    global _last_request_time
    current_time = time.time()
    time_since_last = current_time - _last_request_time
    
    if time_since_last < MIN_REQUEST_INTERVAL:
        sleep_time = MIN_REQUEST_INTERVAL - time_since_last
        time.sleep(sleep_time)
    
    _last_request_time = time.time()


def query_donations_by_name(
    contributor_name: str,
    contributor_type: Optional[str] = None,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
    per_page: int = 100,
    max_pages: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Query FEC API for donations by contributor name.
    
    Args:
        contributor_name: Name of the contributor (individual or organization)
        contributor_type: Optional filter - "IND" for individual, "ORG" for organization
        min_date: Optional minimum date (YYYY-MM-DD format)
        max_date: Optional maximum date (YYYY-MM-DD format)
        per_page: Number of results per page (max 100)
        max_pages: Maximum number of pages to fetch (None for all)
    
    Returns:
        List of donation records as dictionaries
    """
    if FEC_API_KEY == "YOUR_API_KEY_HERE":
        raise ValueError(
            "FEC API key not set. Please set FEC_API_KEY environment variable "
            "or update FEC_API_KEY in fec_api_client.py"
        )
    
    all_results = []
    page = 1
    
    while True:
        _rate_limit()
        
        # Build API endpoint
        endpoint = f"{FEC_API_BASE_URL}/schedules/schedule_a"
        
        # Build query parameters
        # FEC API requires contributor_name to be at least 2 characters
        if len(contributor_name.strip()) < 2:
            break
            
        params = {
            "api_key": FEC_API_KEY,
            "contributor_name": contributor_name,
            "per_page": min(per_page, 100),  # API max is 100
            "page": page,
            "sort": "-contribution_receipt_date"  # Most recent first
        }
        
        # Add optional filters - FEC API requires "individual" or "committee" (not "IND"/"ORG")
        if contributor_type:
            # Map our values to FEC API values
            if contributor_type.upper() == "IND":
                params["contributor_type"] = "individual"
            elif contributor_type.upper() == "ORG":
                # For organizations, don't use contributor_type - it's for individuals/committees
                # Organizations are searched by name only
                pass
        
        if min_date:
            params["min_date"] = min_date
        
        if max_date:
            params["max_date"] = max_date
        
        try:
            response = requests.get(endpoint, params=params, timeout=FEC_API_TIMEOUT)
            
            # Check for errors and show details
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    # FEC API error format
                    if "error" in error_data:
                        error_obj = error_data["error"]
                        error_msg = error_obj.get("message", "Unknown error")
                        error_code = error_obj.get("code", "")
                        print(f"  API Error {response.status_code} ({error_code}): {error_msg}")
                    elif "message" in error_data:
                        print(f"  API Error {response.status_code}: {error_data['message']}")
                    else:
                        print(f"  API Error {response.status_code}: {error_data}")
                except Exception as e:
                    print(f"  API Error {response.status_code}: {response.text[:300]}")
                
                # 422 usually means invalid parameters - try without contributor_type
                if response.status_code == 422 and contributor_type:
                    # Retry without contributor_type filter
                    params_no_type = params.copy()
                    params_no_type.pop("contributor_type", None)
                    retry_response = requests.get(endpoint, params=params_no_type, timeout=FEC_API_TIMEOUT)
                    if retry_response.status_code == 200:
                        response = retry_response
                    else:
                        return []  # Invalid name or other issue
                elif response.status_code == 422:
                    return []  # Invalid name format
                else:
                    response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                break
            
            # Debug: Check for corrupted dates in FEC API response
            for r in results[:3]:  # Check first 3 results
                date_val = r.get("contribution_receipt_date", "")
                if date_val:
                    import re
                    year_match = re.match(r'^(\d{4})-', str(date_val))
                    if year_match:
                        year = int(year_match.group(1))
                        if 2030 <= year <= 2040:
                            print(f"[WARNING] FEC API returned suspicious date: {date_val} (year: {year})")
            
            all_results.extend(results)
            
            # Check if there are more pages
            pagination = data.get("pagination", {})
            if not pagination.get("has_more_pages", False):
                break
            
            # Check max_pages limit
            if max_pages and page >= max_pages:
                break
            
            page += 1
            
        except requests.exceptions.HTTPError as e:
            # Don't print here - let the calling code handle it
            break
        except requests.exceptions.RequestException as e:
            print(f"  Network error: {e}")
            break
    
    return all_results


def query_donations_by_committee(
    committee_id: str,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
    per_page: int = 100,
    max_pages: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Query FEC API for donations to a specific committee.
    
    Args:
        committee_id: FEC committee ID (e.g., "C00844440")
        min_date: Optional minimum date (YYYY-MM-DD format)
        max_date: Optional maximum date (YYYY-MM-DD format)
        per_page: Number of results per page (max 100)
        max_pages: Maximum number of pages to fetch (None for all)
    
    Returns:
        List of donation records as dictionaries
    """
    if FEC_API_KEY == "YOUR_API_KEY_HERE":
        raise ValueError(
            "FEC API key not set. Please set FEC_API_KEY environment variable "
            "or update FEC_API_KEY in fec_api_client.py"
        )
    
    all_results = []
    page = 1
    
    while True:
        _rate_limit()
        
        endpoint = f"{FEC_API_BASE_URL}/schedules/schedule_a"
        
        params = {
            "api_key": FEC_API_KEY,
            "committee_id": committee_id,
            "per_page": min(per_page, 100),
            "page": page,
            "sort": "-contribution_receipt_date"
        }
        
        if min_date:
            params["min_date"] = min_date
        
        if max_date:
            params["max_date"] = max_date
        
        try:
            response = requests.get(endpoint, params=params, timeout=FEC_API_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                break
            
            all_results.extend(results)
            
            pagination = data.get("pagination", {})
            if not pagination.get("has_more_pages", False):
                break
            
            if max_pages and page >= max_pages:
                break
            
            page += 1
            
        except requests.exceptions.RequestException as e:
            print(f"Error querying FEC API for committee '{committee_id}': {e}")
            break
    
    return all_results


def query_filings_by_committee(
    committee_id: str,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
    per_page: int = 100,
    max_pages: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Query OpenFEC /filings/ for a committee to obtain filing metadata including image_number.

    Use this when a Schedule A record does not include image_number: call this with the same
    committee_id and period (min_date/max_date) to get the filing's image_number for building
    the docquery URL.

    Args:
        committee_id: FEC committee ID (e.g. "C00892471").
        min_date: Optional minimum filing date (YYYY-MM-DD).
        max_date: Optional maximum filing date (YYYY-MM-DD).
        per_page: Results per page (max 100).
        max_pages: Max pages to fetch (None for all).

    Returns:
        List of filing dicts; each may include "file_number" (use for docquery), "image_number",
        "receipt_date", "report_type", etc. Prefer file_number for docquery when present.
    """
    if FEC_API_KEY == "YOUR_API_KEY_HERE":
        raise ValueError(
            "FEC API key not set. Set FEC_API_KEY environment variable or update fec_api_client.py"
        )

    all_filings = []
    page = 1

    while True:
        _rate_limit()

        endpoint = f"{FEC_API_BASE_URL}/filings"
        params = {
            "api_key": FEC_API_KEY,
            "committee_id": committee_id,
            "per_page": min(per_page, 100),
            "page": page,
            "sort": "-receipt_date",
        }
        if min_date:
            params["min_receipt_date"] = min_date
        if max_date:
            params["max_receipt_date"] = max_date

        try:
            response = requests.get(endpoint, params=params, timeout=FEC_API_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            if not results:
                break
            all_filings.extend(results)
            pagination = data.get("pagination", {})
            if not pagination.get("has_more_pages", False):
                break
            if max_pages and page >= max_pages:
                break
            page += 1
        except requests.exceptions.RequestException as e:
            break

    return all_filings


def build_schedule_a_docquery_link(
    committee_id: str,
    image_number: Optional[str] = None,
    schedule_a_record: Optional[Dict[str, Any]] = None,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
    verify_link: bool = False,
) -> Dict[str, Any]:
    """
    Reliably construct the FEC docquery URL for Schedule A receipts.

    URL format: https://docquery.fec.gov/cgi-bin/forms/{committee_id}/{image_number}/sa/ALL
    Example: https://docquery.fec.gov/cgi-bin/forms/C00892471/1930534/sa/ALL
    The path segment must be the filing image number (e.g. 1930534 from /filings/ file_number).
    Do not substitute sub_id or any other id—only the real filing image number.

    If image_number is not provided, use schedule_a_record.image_number only when it is the
    short format (4–12 digits). Otherwise fetch via OpenFEC /filings/ for the same committee
    and period and use that filing's file_number.

    Args:
        committee_id: FEC committee identifier (e.g. "C00892471").
        image_number: Optional numeric filing ID; if set, used directly.
        schedule_a_record: Optional Schedule A record from /schedules/schedule_a/; used for
            image_number (sub_id or image_number) and, if missing, for period (contribution_receipt_date).
        min_date: Optional min date for filings fallback (YYYY-MM-DD).
        max_date: Optional max date for filings fallback (YYYY-MM-DD).
        verify_link: If True, perform a HEAD request to confirm the URL loads.

    Returns:
        Dict with:
          - url: The constructed docquery URL (or fallback receipts search URL if no image_number).
          - committee_id: Normalized committee_id.
          - image_number: The image_number used (empty if none).
          - source: "argument" | "schedule_a" | "filings" | "none".
          - api_endpoint_used: OpenFEC endpoint used to obtain image_number, or "".
          - link_verified: True if verify_link was True and HEAD succeeded; else False/absent.
    """
    committee_id = str(committee_id).strip() if committee_id else ""
    if not committee_id:
        return {
            "url": "",
            "committee_id": "",
            "image_number": "",
            "source": "none",
            "api_endpoint_used": "",
        }

    # Resolve image_number: explicit arg > schedule_a record > filings API
    resolved_image_number = None
    source = "none"
    api_endpoint_used = ""

    # Only use the real filing image number (short, e.g. 1930534). Never use sub_id.
    if image_number and _is_valid_filing_image_id(image_number):
        raw = str(image_number).strip()
        if raw.upper().startswith("FEC-"):
            raw = raw[4:].strip()
        if raw:
            resolved_image_number = raw
            source = "argument"
    elif schedule_a_record and isinstance(schedule_a_record, dict):
        # Schedule A returns file_number (e.g. 1930534) — that's the docquery URL number
        candidate = schedule_a_record.get("file_number")
        if candidate and _is_valid_filing_image_id(candidate):
            raw = str(candidate).strip()
            if raw.upper().startswith("FEC-"):
                raw = raw[4:].strip()
            if raw:
                resolved_image_number = raw
                source = "schedule_a"
                api_endpoint_used = "/schedules/schedule_a/"

    if resolved_image_number is None and (min_date or max_date or (schedule_a_record and schedule_a_record.get("contribution_receipt_date"))):
        # No guess: fetch filings for this committee and period
        period_min = min_date
        period_max = max_date
        if not (period_min or period_max) and schedule_a_record and schedule_a_record.get("contribution_receipt_date"):
            rd = schedule_a_record.get("contribution_receipt_date")
            if rd:
                period_min = rd
                period_max = rd
        try:
            filings = query_filings_by_committee(
                committee_id,
                min_date=period_min,
                max_date=period_max,
                per_page=100,
                max_pages=1,
            )
            for f in filings:
                # OpenFEC filings return file_number (numeric filing ID); some docs say image_number
                im = f.get("file_number") or f.get("image_number")
                if im is not None:
                    raw = str(im).strip()
                    if raw:
                        resolved_image_number = raw
                        source = "filings"
                        api_endpoint_used = "/filings/"
                        break
        except Exception:
            pass

    # Build URL
    if resolved_image_number:
        url = f"{DOCQUERY_BASE_URL}/{committee_id}/{resolved_image_number}/sa/ALL"
    else:
        url = f"https://www.fec.gov/data/receipts/?committee_id={committee_id}"

    out = {
        "url": url,
        "committee_id": committee_id,
        "image_number": resolved_image_number or "",
        "source": source,
        "api_endpoint_used": api_endpoint_used,
    }

    if verify_link and url and resolved_image_number:
        out["link_verified"] = _verify_docquery_link(url)

    return out


def _is_valid_filing_image_id(val: Any) -> bool:
    """
    Docquery URLs use the filing image number (short, e.g. 1930534), not the Schedule A
    line-item sub_id (long, e.g. 4012020261302797845). Return True only for IDs that
    look like valid filing numbers (all digits, 4–12 chars).
    """
    if val is None:
        return False
    s = str(val).strip()
    if s.upper().startswith("FEC-"):
        s = s[4:].strip()
    if not s or not s.isdigit():
        return False
    return 4 <= len(s) <= 12


def is_valid_docquery_schedule_a_url(url: str) -> bool:
    """
    Return True only if the URL looks like a valid Schedule A docquery link (short
    filing image number in path). Rejects URLs built with long line-item sub_ids.
    """
    if not url or not isinstance(url, str) or "docquery.fec.gov" not in url or "/sa/ALL" not in url:
        return False
    # .../forms/{committee_id}/{image_number}/sa/ALL -> image_number must be 4-12 digits
    parts = url.rstrip("/").split("/")
    if len(parts) < 2:
        return False
    # image_number is the last part before "sa"
    try:
        idx = parts.index("sa")
        if idx < 1:
            return False
        image_part = parts[idx - 1]
        return _is_valid_filing_image_id(image_part)
    except ValueError:
        return False


def _verify_docquery_link(url: str, timeout: int = 5) -> bool:
    """Perform a HEAD request to confirm the docquery URL is reachable. Returns True if status is 2xx.
    Some servers may not support HEAD; the link may still load in a browser."""
    if not url or not url.startswith("https://docquery.fec.gov/"):
        return False
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        return 200 <= resp.status_code < 300
    except Exception:
        return False


def _build_docquery_url(committee_id: str, image_number: Any) -> str:
    """
    Build FEC docquery URL only when we have the real filing image number (e.g. 1930534).
    URL format: https://docquery.fec.gov/cgi-bin/forms/{committee_id}/{image_number}/sa/ALL
    Do not substitute sub_id or any other id—only the filing image number from /filings/ file_number
    or Schedule A image_number when it is that short format.
    """
    committee_id = str(committee_id).strip() if committee_id else ""
    if not committee_id:
        return ""
    if image_number and _is_valid_filing_image_id(image_number):
        raw = str(image_number).strip()
        if raw.upper().startswith("FEC-"):
            raw = raw[4:].strip()
        if raw:
            return f"{DOCQUERY_BASE_URL}/{committee_id}/{raw}/sa/ALL"
    return f"https://www.fec.gov/data/receipts/?committee_id={committee_id}"


def normalize_fec_donation(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a raw FEC API response record into a standardized format.
    
    Args:
        record: Raw record from FEC API
    
    Returns:
        Normalized dictionary with standard field names
    """
    # Safety check: ensure record is a dict
    if not record or not isinstance(record, dict):
        return {
            "donor_name": "", "donor_type": "", "donor_city": "", "donor_state": "", "donor_zip": "",
            "employer": "", "occupation": "", "donation_amount": 0, "donation_date": "",
            "committee_id": "", "committee_name": "", "committee_type": "",
            "candidate_id": "", "candidate_name": "", "candidate_office": "", "candidate_party": "",
            "fec_record_id": "", "fec_file_number": "", "fec_docquery_url": "", "memo_code": "", "memo_text": "", "receipt_type": "", "line_number": ""
        }
    
    # Safely get nested objects (committee and candidate can be None)
    committee = record.get("committee") or {}
    candidate = record.get("candidate") or {}
    
    # Ensure they're dicts
    if not isinstance(committee, dict):
        committee = {}
    if not isinstance(candidate, dict):
        candidate = {}
    
    # Committee ID: API can return in committee object or at top level
    committee_id = (committee.get("committee_id", "") or record.get("committee_id", "")) if isinstance(committee, dict) else (record.get("committee_id", "") or "")
    # Docquery URL uses file_number from Schedule A (e.g. 1930534). Live API returns it.
    # Do NOT use image_number (long page id) or sub_id (long line-item id).
    file_num = record.get("file_number")
    url_id = file_num if _is_valid_filing_image_id(file_num) else None
    fec_record_id = record.get("sub_id") or record.get("image_number") or ""
    
    return {
        "donor_name": record.get("contributor_name", ""),
        "donor_type": record.get("contributor_type", ""),
        "donor_city": record.get("contributor_city", ""),
        "donor_state": record.get("contributor_state", ""),
        "donor_zip": record.get("contributor_zip", ""),
        "employer": record.get("contributor_employer", ""),
        "occupation": record.get("contributor_occupation", ""),
        "donation_amount": record.get("contribution_receipt_amount", 0),
        "donation_date": record.get("contribution_receipt_date", ""),
        "committee_id": committee_id,
        "committee_name": committee.get("name", "") if isinstance(committee, dict) else "",
        "committee_type": committee.get("committee_type", "") if isinstance(committee, dict) else "",
        "candidate_id": candidate.get("candidate_id", "") if isinstance(candidate, dict) else "",
        "candidate_name": candidate.get("name", "") if isinstance(candidate, dict) else "",
        "candidate_office": candidate.get("office", "") if isinstance(candidate, dict) else "",
        "candidate_party": candidate.get("party", "") if isinstance(candidate, dict) else "",
        "fec_record_id": fec_record_id,
        "fec_file_number": str(file_num) if file_num is not None else "",
        "fec_docquery_url": _build_docquery_url(committee_id, url_id),
        "memo_code": record.get("memo_code", ""),
        "memo_text": record.get("memo_text", ""),
        "receipt_type": record.get("receipt_type", ""),
        "line_number": record.get("line_number", ""),
    }


def donations_to_dataframe(donations: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convert a list of normalized donation records to a pandas DataFrame.
    
    Args:
        donations: List of normalized donation dictionaries
    
    Returns:
        pandas DataFrame
    """
    if not donations:
        return pd.DataFrame()
    
    normalized = [normalize_fec_donation(d) for d in donations]
    return pd.DataFrame(normalized)


# ---------------------------
# EXAMPLE USAGE
# ---------------------------

if __name__ == "__main__":
    # Example: Query donations by a specific name
    print("Example: Querying donations for 'JOHN SMITH'...")
    donations = query_donations_by_name("JOHN SMITH", contributor_type="IND")
    print(f"Found {len(donations)} donations")
    
    if donations:
        df = donations_to_dataframe(donations)
        print("\nFirst few results:")
        print(df.head())
