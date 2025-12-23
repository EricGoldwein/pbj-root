"""SEO metadata helper functions for Flask templates"""

STATE_ABBR_TO_NAME = {
    'al': 'Alabama', 'ak': 'Alaska', 'az': 'Arizona', 'ar': 'Arkansas', 'ca': 'California',
    'co': 'Colorado', 'ct': 'Connecticut', 'de': 'Delaware', 'fl': 'Florida', 'ga': 'Georgia',
    'hi': 'Hawaii', 'id': 'Idaho', 'il': 'Illinois', 'in': 'Indiana', 'ia': 'Iowa',
    'ks': 'Kansas', 'ky': 'Kentucky', 'la': 'Louisiana', 'me': 'Maine', 'md': 'Maryland',
    'ma': 'Massachusetts', 'mi': 'Michigan', 'mn': 'Minnesota', 'ms': 'Mississippi', 'mo': 'Missouri',
    'mt': 'Montana', 'ne': 'Nebraska', 'nv': 'Nevada', 'nh': 'New Hampshire', 'nj': 'New Jersey',
    'nm': 'New Mexico', 'ny': 'New York', 'nc': 'North Carolina', 'nd': 'North Dakota', 'oh': 'Ohio',
    'ok': 'Oklahoma', 'or': 'Oregon', 'pa': 'Pennsylvania', 'pr': 'Puerto Rico', 'ri': 'Rhode Island', 'sc': 'South Carolina',
    'sd': 'South Dakota', 'tn': 'Tennessee', 'tx': 'Texas', 'ut': 'Utah', 'vt': 'Vermont',
    'va': 'Virginia', 'wa': 'Washington', 'wv': 'West Virginia', 'wi': 'Wisconsin', 'wy': 'Wyoming',
    'dc': 'District of Columbia'
}


def get_state_name(code):
    """Convert state code to full state name"""
    return STATE_ABBR_TO_NAME.get(code.lower(), code.upper())


def get_seo_metadata(path):
    """
    Get SEO metadata based on the request path.
    Returns a dict with title, description, og_title, og_description, canonical_url, og_url, and include_image.
    """
    base_url = 'https://www.pbj320.com'
    
    # Default values for wrapped pages
    default_metadata = {
        'title': 'PBJ Wrapped Q2 2025 — Nursing Home Staffing Data by State and Region | PBJ320',
        'description': 'Explore Q2 2025 nursing home staffing data across all 50 states, CMS regions, and the United States. Interactive staffing insights from CMS Payroll-Based Journal (PBJ) data. Comprehensive analysis of 15,000+ nursing homes and long-term care facilities.',
        'og_title': 'PBJ Wrapped Q2 2025 — Nursing Home Staffing Data',
        'og_description': 'Interactive nursing home staffing data for Q2 2025. Explore staffing levels, trends, and insights by state, region, and nationally from CMS PBJ data.',
        'canonical_url': base_url + '/wrapped',
        'og_url': base_url + '/wrapped',
        'include_image': True,
        'og_image': base_url + '/images/phoebe-wrapped-wide.png',
    }
    
    # Normalize path (ensure leading slash, handle trailing slash)
    if not path:
        path = '/'
    if not path.startswith('/'):
        path = '/' + path
    
    # Handle SFF pages
    if path.startswith('/sff'):
        # Normalize /sff and /sff/ to /sff/usa
        if path == '/sff' or path == '/sff/':
            path = '/sff/usa'
        
        if path == '/sff/usa' or path == '/sff/usa/':
            return {
                'title': 'Special Focus Facilities Program — United States | PBJ320',
                'description': 'United States Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ Q2 2025.',
                'og_title': 'Special Focus Facilities Program — United States',
                'og_description': 'United States Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ Q2 2025.',
                'canonical_url': base_url + '/sff/usa',
                'og_url': base_url + '/sff/usa',
                'include_image': True,
                'og_image': base_url + '/og-image-1200x630.png',
            }
        elif '/sff/region' in path.lower():
            # Extract region number
            import re
            region_match = re.search(r'region-?(\d+)', path.lower())
            region_num = region_match.group(1) if region_match else ''
            return {
                'title': f'SFF Program: CMS Region {region_num} | PBJ320',
                'description': f'CMS Region {region_num} Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ Q2 2025.',
                'og_title': f'SFF Program: CMS Region {region_num}',
                'og_description': f'CMS Region {region_num} Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ Q2 2025.',
                'canonical_url': base_url + path.rstrip('/'),
                'og_url': base_url + path.rstrip('/'),
                'include_image': True,
                'og_image': base_url + '/og-image-1200x630.png',
            }
        else:
            # Extract state code
            parts = [p for p in path.split('/') if p]
            if len(parts) >= 2 and parts[0] == 'sff':
                state_code = parts[1].lower()
                if state_code and state_code not in ('sff', 'usa'):
                    state_name = get_state_name(state_code)
                    return {
                        'title': f'{state_name} Special Focus Facilities | PBJ320',
                        'description': f'{state_name} Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ Q2 2025.',
                        'og_title': f'{state_name} Special Focus Facilities',
                        'og_description': f'{state_name} Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ Q2 2025.',
                        'canonical_url': base_url + path.rstrip('/'),
                        'og_url': base_url + path.rstrip('/'),
                        'include_image': True,
                        'og_image': 'https://www.pbj320.com/og-image-1200x630.png',
                    }
    
    # For wrapped pages, update canonical and og:url to match path
    if path.startswith('/wrapped'):
        default_metadata['canonical_url'] = base_url + path.rstrip('/')
        default_metadata['og_url'] = base_url + path.rstrip('/')
    
    return default_metadata


