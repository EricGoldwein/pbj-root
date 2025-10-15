#!/usr/bin/env python3
"""
Simple script to make pbj-root files dynamic
Run this when you want to update the dates in the static files
"""
import os
import sys

# Add the PBJapp directory to the path so we can import the date utilities
sys.path.append(r'C:\Users\egold\PycharmProjects\PBJapp')

try:
    from utils.date_utils import get_latest_data_periods
    print("SUCCESS: Successfully imported date utilities from PBJapp")
    
    # Get the dynamic dates
    dates = get_latest_data_periods()
    print(f"Current dynamic dates:")
    print(f"   Data range: {dates['data_range']}")
    print(f"   Quarter count: {dates['quarter_count']}")
    print(f"   Provider info latest: {dates['provider_info_latest']}")
    print(f"   Provider info previous: {dates['provider_info_previous']}")
    print(f"   Affiliated entity latest: {dates['affiliated_entity_latest']}")
    
    print("\nTo make the pbj-root files dynamic, you need to manually update:")
    print(f"   1. index-render.html: Change '2017-2025' to '{dates['data_range']}' in chart titles")
    print(f"   2. about.html: Update quarter count from '33' to '{dates['quarter_count']}'")
    print(f"   3. about.html: Update provider info dates to '{dates['provider_info_latest']}, {dates['provider_info_previous']}'")
    print(f"   4. about.html: Update affiliated entity date to '{dates['affiliated_entity_latest']}'")
    print(f"   5. about.html: Update methodology data range to '{dates['data_range']}'")
    
    print("\nFor now, the files are manually updated. In the future, you could:")
    print("   - Set up a build process that runs this script")
    print("   - Use server-side rendering to inject dynamic dates")
    print("   - Create a simple web interface to update these values")
    
except ImportError as e:
    print(f"ERROR: Could not import date utilities: {e}")
    print("   Make sure the PBJapp directory is accessible")
    print("   Fallback dates: 2017-2025, 33 quarters")
