#!/usr/bin/env python3
"""
Dynamic utilities for pbj-root files
"""
import os
import sys
import re
from datetime import datetime

# Prefer local pbj-root date utilities.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from utils.date_utils import get_latest_data_periods
except ImportError:
    # Fallback if we can't import the date utilities
    def get_latest_data_periods():
        current_year = datetime.now().year
        return {
            'data_range': f'2017-{current_year}',
            'quarter_count': 33,
            'provider_info_latest': 'Latest available',
            'provider_info_previous': 'Prior available',
            'affiliated_entity_latest': 'Latest available',
            'current_year': current_year
        }

def get_dynamic_dates():
    """Get dynamic date information for pbj-root files"""
    try:
        periods = get_latest_data_periods()
        return periods
    except Exception as e:
        print(f"Warning: Could not get dynamic dates: {e}")
        # Return fallback dates
        current_year = datetime.now().year
        return {
            'data_range': f'2017-{current_year}',
            'quarter_count': 33,
            'provider_info_latest': 'Latest available',
            'provider_info_previous': 'Prior available',
            'affiliated_entity_latest': 'Latest available',
            'current_year': current_year
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
        'from 2017 to 2025': f'from {dates["data_range"]}',
        'from 2017-2025': f'from {dates["data_range"]}'
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

