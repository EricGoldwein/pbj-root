#!/usr/bin/env python3
"""
Date utilities for PBJ data processing
Provides functions to get the latest data periods and date information
"""
from datetime import datetime


def get_latest_data_periods():
    """
    Get the latest data periods information for PBJ data.
    
    Returns:
        dict: Dictionary containing:
            - data_range: String range like '2017-2025'
            - quarter_count: Integer count of quarters
            - provider_info_latest: Latest provider info date (e.g., 'September 2025')
            - provider_info_previous: Previous provider info date (e.g., 'June 2025')
            - affiliated_entity_latest: Latest affiliated entity date (e.g., 'July 2025')
            - current_year: Current year as integer
    """
    # Calculate current year
    current_year = datetime.now().year
    
    # Default/fallback dates - these can be updated as needed
    # TODO: Consider making this dynamic based on actual data files
    return {
        'data_range': '2017-2025',
        'quarter_count': 33,
        'provider_info_latest': 'September 2025',
        'provider_info_previous': 'June 2025',
        'affiliated_entity_latest': 'July 2025',
        'current_year': current_year
    }

