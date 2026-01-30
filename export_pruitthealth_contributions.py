"""
Export contributions data for PRUITTHEALTH CONSULTING SERVICES INC
This script queries the FEC API and exports results to a markdown file
"""

import sys
from pathlib import Path

# Add donor directory to path
donor_dir = Path(__file__).parent / "donor"
if str(donor_dir) not in sys.path:
    sys.path.insert(0, str(donor_dir))

from fec_api_client import query_donations_by_name, normalize_fec_donation
import pandas as pd
from datetime import datetime

def export_contributions_to_markdown(organization_name, output_file):
    """Query FEC API and export results to markdown"""
    
    print(f"Querying FEC API for: {organization_name}")
    print("=" * 60)
    
    # Query FEC API
    try:
        donations = query_donations_by_name(
            contributor_name=organization_name,
            contributor_type=None,  # No filter for organizations
            per_page=100,
            max_pages=None  # Get all pages
        )
        
        if not donations:
            print(f"No contributions found for {organization_name}")
            return
        
        print(f"Found {len(donations)} raw donation records")
        
        # Normalize donations
        normalized = []
        for donation in donations:
            try:
                norm = normalize_fec_donation(donation)
                if norm and isinstance(norm, dict):
                    normalized.append({
                        'amount': float(norm.get('donation_amount', 0)) if norm.get('donation_amount') and pd.notna(norm.get('donation_amount')) else 0,
                        'date': norm.get('donation_date', '') or '',
                        'committee': norm.get('committee_name', '') or '',
                        'committee_id': norm.get('committee_id', '') or '',
                        'candidate': norm.get('candidate_name', '') or '',
                        'candidate_id': norm.get('candidate_id', '') or '',
                        'office': norm.get('candidate_office', '') or '',
                        'party': norm.get('candidate_party', '') or '',
                        'employer': norm.get('employer', '') or '',
                        'occupation': norm.get('occupation', '') or '',
                        'donor_city': norm.get('donor_city', '') or '',
                        'donor_state': norm.get('donor_state', '') or '',
                        'sub_id': donation.get('sub_id', '') if isinstance(donation, dict) else ''
                    })
            except Exception as e:
                print(f"Warning: Error normalizing donation: {e}")
                continue
        
        # Sort by date (most recent first)
        normalized.sort(key=lambda x: x['date'] if x['date'] else '', reverse=True)
        
        # Calculate totals
        total_amount = sum(d['amount'] for d in normalized)
        donation_count = len(normalized)
        
        # Group by year
        import re
        by_year = {}
        for d in normalized:
            if d['date'] and isinstance(d['date'], str):
                year_match = re.match(r'^(\d{4})', d['date'])
                if year_match:
                    year = int(year_match.group(1))
                    by_year[year] = by_year.get(year, 0) + d['amount']
        
        # Group by committee
        by_committee = {}
        for d in normalized:
            if d['committee']:
                by_committee[d['committee']] = by_committee.get(d['committee'], 0) + d['amount']
        
        # Group by candidate
        by_candidate = {}
        for d in normalized:
            if d['candidate']:
                key = f"{d['candidate']} ({d['office'] or 'Unknown'})"
                by_candidate[key] = by_candidate.get(key, 0) + d['amount']
        
        # Generate markdown
        md_content = f"""# FEC Contributions Data: {organization_name}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary

- **Total Contributions:** ${total_amount:,.2f}
- **Number of Contributions:** {donation_count}
- **Date Range:** {min([d['date'] for d in normalized if d['date']], default='N/A')} to {max([d['date'] for d in normalized if d['date']], default='N/A')}

## Year Breakdown

"""
        
        # Add year breakdown
        current_year = datetime.now().year
        years = sorted([y for y in by_year.keys() if y >= 2020], reverse=True)
        for year in years[:5]:  # Last 5 years
            amount = by_year[year]
            md_content += f"- **{year}:** ${amount:,.2f}\n"
        
        md_content += f"""
## Top Recipients

### Top Committees

"""
        
        # Top committees
        top_committees = sorted(by_committee.items(), key=lambda x: x[1], reverse=True)[:10]
        for committee, amount in top_committees:
            md_content += f"- **{committee}:** ${amount:,.2f}\n"
        
        md_content += f"""
### Top Candidates

"""
        
        # Top candidates
        top_candidates = sorted(by_candidate.items(), key=lambda x: x[1], reverse=True)[:10]
        for candidate, amount in top_candidates:
            md_content += f"- **{candidate}:** ${amount:,.2f}\n"
        
        md_content += f"""
## All Contributions

| Date | Amount | Committee | Candidate | Office | Party | Employer | Location |
|------|--------|-----------|-----------|--------|-------|----------|----------|
"""
        
        # Add all contributions
        for d in normalized:
            date = d['date'] or 'N/A'
            amount = f"${d['amount']:,.2f}" if d['amount'] > 0 else 'N/A'
            committee = d['committee'] or 'N/A'
            candidate = d['candidate'] or 'N/A'
            office = d['office'] or 'N/A'
            party = d['party'] or 'N/A'
            employer = d['employer'] or 'N/A'
            location = f"{d['donor_city']}, {d['donor_state']}" if d['donor_city'] and d['donor_state'] else 'N/A'
            
            # Escape pipes in markdown table
            for field in [date, amount, committee, candidate, office, party, employer, location]:
                if '|' in str(field):
                    field = str(field).replace('|', '\\|')
            
            md_content += f"| {date} | {amount} | {committee} | {candidate} | {office} | {party} | {employer} | {location} |\n"
        
        md_content += f"""
## Search Details

- **Search Name:** {organization_name}
- **FEC API Endpoint:** `/schedules/schedule_a`
- **Search Parameters:** `contributor_name={organization_name}` (no contributor_type filter for organizations)
- **Total Records Found:** {donation_count}
- **FEC Data Source:** https://www.fec.gov/data/receipts/

## Notes

- This data is from the Federal Election Commission (FEC) Schedule A database
- The FEC API uses fuzzy matching, so results may include contributions from similar names
- Always verify data independently on the FEC website
- For organizations, the API searches without a `contributor_type` filter
- All amounts are in USD

## Verification Links

- [FEC Receipts Database](https://www.fec.gov/data/receipts/) - Search manually
- [FEC API Documentation](https://api.open.fec.gov/developers/)
"""
        
        # Write to file
        output_path = Path(output_file)
        output_path.write_text(md_content, encoding='utf-8')
        
        dates = [d['date'] for d in normalized if d['date']]
        min_date = min(dates) if dates else 'N/A'
        max_date = max(dates) if dates else 'N/A'
        
        print(f"\nSuccessfully exported {donation_count} contributions to: {output_file}")
        print(f"   Total Amount: ${total_amount:,.2f}")
        print(f"   Date Range: {min_date} to {max_date}")
        
    except Exception as e:
        print(f"Error querying FEC API: {e}")
        import traceback
        traceback.print_exc()
        return

if __name__ == "__main__":
    # Try multiple name variations
    name_variations = [
        "PRUITTHEALTH CONSULTING SERVICES INC",
        "PRUITTHEALTH CONSULTING SERVICES",
        "PRUITTHEALTH",
        "PRUITT HEALTH CONSULTING SERVICES",
        "PRUITT HEALTH"
    ]
    
    output_file = "PRUITTHEALTH_CONSULTING_SERVICES_INC_contributions.md"
    
    # Try each variation
    found_results = False
    for name in name_variations:
        print(f"\nTrying: {name}")
        try:
            # Check if we get results before writing
            from fec_api_client import query_donations_by_name
            test_donations = query_donations_by_name(
                contributor_name=name,
                contributor_type=None,
                per_page=10  # Just check if we get any results
            )
            if test_donations and len(test_donations) > 0:
                print(f"Found {len(test_donations)} records with: {name}")
                export_contributions_to_markdown(name, output_file)
                found_results = True
                break
        except Exception as e:
            print(f"Error with {name}: {e}")
            continue
    else:
        print("\nNo contributions found with any name variation")
        print("This could mean:")
        print("  1. The FEC API key is not set (check donor/.env file)")
        print("  2. There are no contributions for this organization")
        print("  3. The name format doesn't match FEC records")
