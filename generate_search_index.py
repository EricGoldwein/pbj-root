#!/usr/bin/env python3
"""
Generate search_index.json for home page search (facility by name/ID, entity, state).
Reads provider_info_combined_latest.csv and states_list.json.
Output: search_index.json with facilities, entities, and states for client-side autocomplete.
"""
import csv
import json
import os
import re

# State full name to abbreviation (for states list and URLs)
STATE_NAME_TO_ABBR = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
    'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA',
    'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
    'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO',
    'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
    'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
    'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
    'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
    'District of Columbia': 'DC', 'Puerto Rico': 'PR', 'USA': 'USA',
}


def normalize_ccn(val):
    """Ensure CCN is 6-digit string."""
    if val is None or val == '':
        return ''
    s = str(val).strip()
    # Remove decimals if present (e.g. 419.0 -> 419)
    if '.' in s:
        s = s.split('.')[0]
    return s.zfill(6)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    provider_path = 'provider_info_combined_latest.csv'
    states_path = 'states_list.json'
    out_path = 'search_index.json'

    # Pass 1: count unique CCNs per chain_id (for entity NH count)
    entity_ccns = {}  # chain_id -> set of CCNs
    if os.path.exists(provider_path):
        with open(provider_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ccn = normalize_ccn(row.get('ccn', ''))
                chain_id_raw = row.get('chain_id') or row.get('affiliated_entity_id') or ''
                if not ccn or not chain_id_raw:
                    continue
                try:
                    eid = int(float(chain_id_raw))
                    entity_ccns.setdefault(eid, set()).add(ccn)
                except (ValueError, TypeError):
                    pass

    # Pass 2: collect all facility rows, then keep the LATEST row per CCN (by processing_date)
    # so name, city, abuse, rating, SFF reflect the most recent data
    facility_rows = []
    if os.path.exists(provider_path):
        with open(provider_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ccn = normalize_ccn(row.get('ccn', ''))
                name = (row.get('provider_name') or '').strip()
                if not ccn or not name:
                    continue
                processing_date = (row.get('processing_date') or '').strip()[:10]
                facility_rows.append((ccn, processing_date, row))

    # Keep one row per CCN: the one with the latest processing_date
    by_ccn = {}
    for ccn, processing_date, row in facility_rows:
        existing_date = by_ccn.get(ccn, ('', None))[0]
        if not existing_date or (processing_date and processing_date > existing_date):
            by_ccn[ccn] = (processing_date, row)

    facilities = []
    entities_seen = set()  # dedupe by chain id only (one entity per chain)
    entities = []

    for ccn, (_, row) in by_ccn.items():
        name = (row.get('provider_name') or '').strip()
        state = (row.get('state') or '').strip().upper()
        city = (row.get('city') or '').strip()[:40]
        if not name:
            continue

        abuse = (row.get('abuse_icon') or '').strip().upper()
        try:
            rating = float(row.get('overall_rating') or 0)
        except (TypeError, ValueError):
            rating = 0
        sff_status = (row.get('sff_status') or '').strip()
        reasons = []
        if abuse == 'Y':
            reasons.append('Abuse')
        if rating == 1:
            reasons.append('1 star')
        if sff_status and ('SFF' in sff_status.upper() or 'Candidate' in sff_status):
            reasons.append('SFF')
        high_risk = 1 if reasons else 0
        high_risk_reason = ', '.join(reasons) if reasons else ''

        facilities.append({
            'n': name[:80], 'c': ccn, 's': state[:2],
            'y': city, 'r': high_risk, 'h': high_risk_reason[:40]
        })

        chain_id_raw = row.get('chain_id') or row.get('affiliated_entity_id') or ''
        chain_name = (row.get('chain_name') or row.get('affiliated_entity_name') or '').strip()
        if chain_name and chain_id_raw:
            try:
                eid = int(float(chain_id_raw))
                if eid not in entities_seen:
                    entities_seen.add(eid)
                    fc = len(entity_ccns.get(eid, set()))
                    entities.append({'n': chain_name[:80], 'id': eid, 'fc': fc})
            except (ValueError, TypeError):
                pass

    # States: from states_list.json (full names) -> add abbr
    states = []
    if os.path.exists(states_path):
        with open(states_path, 'r', encoding='utf-8') as f:
            state_names = json.load(f)
        for name in state_names:
            if name == 'USA':
                continue
            abbr = STATE_NAME_TO_ABBR.get(name, name[:2].upper() if len(name) >= 2 else '')
            if abbr:
                states.append({'n': name, 'abbr': abbr})

    payload = {
        'f': facilities,
        'e': entities,
        's': states,
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, separators=(',', ':'))

    print(f"Wrote {out_path}: {len(facilities)} facilities, {len(entities)} entities, {len(states)} states.")


if __name__ == '__main__':
    main()
