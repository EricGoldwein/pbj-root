"""
FEC API Client Module

This module provides functions to query the Federal Election Commission (FEC) API
to look up political donations by contributor name.

USAGE:
1. Add your FEC API key to the FEC_API_KEY constant below, or set it as an environment variable
2. Use the query_donations_by_name() function to search for donations by contributor name
3. The module handles rate limiting and API response parsing

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

# FEC API Base URL
FEC_API_BASE_URL = "https://api.open.fec.gov/v1"

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
            response = requests.get(endpoint, params=params, timeout=30)
            
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
                    retry_response = requests.get(endpoint, params=params_no_type, timeout=30)
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
            response = requests.get(endpoint, params=params, timeout=30)
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


def normalize_fec_donation(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a raw FEC API response record into a standardized format.
    
    Args:
        record: Raw record from FEC API
    
    Returns:
        Normalized dictionary with standard field names
    """
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
        "committee_id": record.get("committee", {}).get("committee_id", ""),
        "committee_name": record.get("committee", {}).get("name", ""),
        "committee_type": record.get("committee", {}).get("committee_type", ""),
        "candidate_id": record.get("candidate", {}).get("candidate_id", ""),
        "candidate_name": record.get("candidate", {}).get("name", ""),
        "candidate_office": record.get("candidate", {}).get("office", ""),
        "candidate_party": record.get("candidate", {}).get("party", ""),
        "fec_record_id": record.get("sub_id", ""),
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
