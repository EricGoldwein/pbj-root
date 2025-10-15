#!/usr/bin/env python3
"""
Dynamic utilities for pbj-root files
"""
import os
import sys
import re
from datetime import datetime

# Add the PBJapp directory to the path so we can import the date utilities
sys.path.append(r'C:\Users\egold\PycharmProjects\PBJapp')

try:
    from utils.date_utils import get_latest_data_periods
except ImportError:
    # Fallback if we can't import the date utilities
    def get_latest_data_periods():
        return {
            'data_range': '2017-2025',
            'quarter_count': 33,
            'provider_info_latest': 'September 2025',
            'provider_info_previous': 'June 2025',
            'affiliated_entity_latest': 'July 2025',
            'current_year': 2025
        }

def get_dynamic_dates():
    """Get dynamic date information for pbj-root files"""
    try:
        periods = get_latest_data_periods()
        return periods
    except Exception as e:
        print(f"Warning: Could not get dynamic dates: {e}")
        # Return fallback dates
        return {
            'data_range': '2017-2025',
            'quarter_count': 33,
            'provider_info_latest': 'September 2025',
            'provider_info_previous': 'June 2025',
            'affiliated_entity_latest': 'July 2025',
            'current_year': 2025
        }

def update_html_file(file_path, replacements):
    """Update an HTML file with dynamic replacements"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Apply replacements
        for old, new in replacements.items():
            content = content.replace(old, new)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Updated {file_path}")
        return True
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False

def update_pbj_root_files():
    """Update all pbj-root files with dynamic dates"""
    dates = get_dynamic_dates()
    
    # Define replacements for index-render.html
    index_replacements = {
        'USA Nursing Home Staffing (2017-2025)': f'USA Nursing Home Staffing ({dates["data_range"]})',
        'Nursing Home Staffing (2017-2025)': f'Nursing Home Staffing ({dates["data_range"]})'
    }
    
    # Define replacements for about.html
    about_replacements = {
        '33 quarters of daily data': f'{dates["quarter_count"]} quarters of daily data',
        '(July 2025)': f'({dates["affiliated_entity_latest"]})',
        'from 2017 to 2025': f'from {dates["data_range"]}',
        '(September 2025, June 2025)': f'({dates["provider_info_latest"]}, {dates["provider_info_previous"]})',
        '(July 2025)': f'({dates["affiliated_entity_latest"]})'
    }
    
    # Update files
    files_to_update = [
        ('index-render.html', index_replacements),
        ('about.html', about_replacements)
    ]
    
    success_count = 0
    for file_path, replacements in files_to_update:
        if os.path.exists(file_path):
            if update_html_file(file_path, replacements):
                success_count += 1
        else:
            print(f"File not found: {file_path}")
    
    print(f"Successfully updated {success_count} files")
    return success_count > 0

if __name__ == '__main__':
    update_pbj_root_files()

