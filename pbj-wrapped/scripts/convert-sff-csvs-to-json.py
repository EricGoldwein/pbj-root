#!/usr/bin/env python3
"""
Convert SFF CSV files to a combined JSON file with category field.
This creates a single, efficient JSON file for fast loading.
"""

import csv
import json
import os
from pathlib import Path
from typing import Dict, List, Any

def parse_csv_file(csv_path: str, category: str) -> List[Dict[str, Any]]:
    """Parse a CSV file and return list of facilities with category."""
    facilities = []
    
    if not os.path.exists(csv_path):
        print(f"Warning: {csv_path} not found")
        return facilities
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            provider_number = row.get('Provider Number', '').strip()
            if not provider_number:
                continue
            
            facility = {
                'provider_number': provider_number,
                'facility_name': row.get('Facility Name', '').strip() or None,
                'address': row.get('Address', '').strip() or None,
                'city': row.get('City', '').strip() or None,
                'state': row.get('State', '').strip() or None,
                'zip': row.get('Zip', '').strip() or None,
                'phone_number': row.get('Phone Number', '').strip() or None,
                'category': category,  # SFF, Graduate, Terminated, or Candidate
                'months_as_sff': None,
                'most_recent_inspection': None,
                'met_survey_criteria': None,
                'date_of_graduation': None,
                'date_of_termination': None
            }
            
            # Extract months based on category
            if category == 'SFF':
                # Table A: Most Recent Inspection, Met Survey Criteria, Months as an SFF
                facility['most_recent_inspection'] = row.get('Most Recent Inspection', '').strip() or None
                facility['met_survey_criteria'] = row.get('Met Survey Criteria', '').strip() or None
                months_str = row.get('Months as an SFF', '').strip()
            elif category == 'Graduate':
                # Table B: Date of Graduation, Months as an SFF
                facility['date_of_graduation'] = row.get('Date of Graduation', '').strip() or None
                months_str = row.get('Months as an SFF', '').strip()
            elif category == 'Terminated':
                # Table C: Date of Termination, Months as an SFF
                facility['date_of_termination'] = row.get('Date of Termination', '').strip() or None
                months_str = row.get('Months as an SFF', '').strip()
            else:  # Candidate
                # Table D: Months as an SFF Candidate
                months_str = row.get('Months as an SFF Candidate', '').strip()
            
            # Parse months
            if months_str:
                try:
                    months = int(months_str)
                    if 1 <= months <= 200:
                        facility['months_as_sff'] = months
                except ValueError:
                    pass
            
            facilities.append(facility)
    
    return facilities

def main():
    """Convert all SFF CSV files to a single JSON file."""
    script_dir = Path(__file__).parent
    public_dir = script_dir.parent / 'public'
    
    # Define CSV files and their categories
    csv_files = {
        'sff_table_a.csv': 'SFF',
        'sff_table_b.csv': 'Graduate',
        'sff_table_c.csv': 'Terminated',
        'sff_table_d.csv': 'Candidate'
    }
    
    all_facilities = []
    counts = {
        'SFF': 0,
        'Graduate': 0,
        'Terminated': 0,
        'Candidate': 0
    }
    
    # Parse each CSV file
    for csv_file, category in csv_files.items():
        csv_path = public_dir / csv_file
        facilities = parse_csv_file(str(csv_path), category)
        all_facilities.extend(facilities)
        counts[category] = len(facilities)
        print(f"Loaded {csv_file}: {len(facilities)} facilities ({category})")
    
    # Create combined JSON structure
    output_data = {
        'document_date': {
            'month': 12,
            'year': 2025,
            'month_name': 'December'
        },
        'facilities': all_facilities,
        'summary': {
            'current_sff_count': counts['SFF'],
            'graduated_count': counts['Graduate'],
            'no_longer_participating_count': counts['Terminated'],
            'candidates_count': counts['Candidate'],
            'total_count': len(all_facilities)
        }
    }
    
    # Write JSON file
    output_path = public_dir / 'sff-facilities.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nCreated {output_path}")
    print(f"   Total facilities: {len(all_facilities)}")
    print(f"   SFF: {counts['SFF']}, Graduate: {counts['Graduate']}, Terminated: {counts['Terminated']}, Candidate: {counts['Candidate']}")

if __name__ == '__main__':
    main()

