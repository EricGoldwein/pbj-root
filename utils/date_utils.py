#!/usr/bin/env python3
"""
Date utilities for PBJ data processing
Provides functions to get the latest data periods and date information
"""
import csv
import os
import re
from datetime import datetime


def get_latest_data_periods():
    """
    Get the latest data periods information for PBJ data.
    Reads from CSV files to determine actual data range and quarter count.
    
    Returns:
        dict: Dictionary containing:
            - data_range: String range like '2017-2025' (from actual data)
            - quarter_count: Integer count of quarters (from actual data)
            - provider_info_latest: Latest provider info date (e.g., 'September 2025')
            - provider_info_previous: Previous provider info date (e.g., 'June 2025')
            - affiliated_entity_latest: Latest affiliated entity date (e.g., 'July 2025')
            - current_year: Current year as integer
    """
    # Calculate current year
    current_year = datetime.now().year
    
    # Try to read from CSV files to get actual data range
    data_range = '2017-2025'  # Default fallback
    quarter_count = 33  # Default fallback
    
    try:
        # Read national quarterly metrics to get data range
        csv_path = 'national_quarterly_metrics.csv'
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
    
    # Provider info and affiliated entity dates are not in CSV files
    # These may need to be updated manually or stored in a separate config file
    # For now, keeping them as fallback values
    return {
        'data_range': data_range,
        'quarter_count': quarter_count,
        'provider_info_latest': 'September 2025',  # TODO: Move to config file if needed
        'provider_info_previous': 'June 2025',  # TODO: Move to config file if needed
        'affiliated_entity_latest': 'July 2025',  # TODO: Move to config file if needed
        'current_year': current_year
    }


def get_latest_update_month_year():
    """
    Get the month and year of the latest data update.
    This is currently hardcoded but could be made dynamic by reading the latest quarter.
    """
    # For now, return a hardcoded value as per user request.
    # In a real application, this would be derived from the latest data available.
    return "January 2026"
