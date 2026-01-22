#!/usr/bin/env python3
"""
Simple Flask app to serve static files with proper headers for Facebook scraper
Now with dynamic date support
"""
from flask import Flask, send_from_directory, send_file, render_template_string, render_template, jsonify, request, redirect
import os
import sys
import re
import csv
import json
from pathlib import Path
from datetime import datetime

try:
    import markdown  # type: ignore
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False
    markdown = None  # type: ignore
    print("Warning: markdown module not found. PBJpedia pages will not be available.")
    print("Install with: pip install markdown")

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("Warning: pandas module not found. Dynamic PBJpedia pages will not be available.")
    print("Install with: pip install pandas")

# Import date utilities from local utils package
from utils.date_utils import get_latest_data_periods, get_latest_update_month_year
from utils.seo_utils import get_seo_metadata

app = Flask(__name__)

# Cache for built assets (cleared on app start)
_built_assets_cache = None
_built_assets_mtime = None

def get_built_assets():
    """Extract script and CSS link tags from built index.html (cached)"""
    global _built_assets_cache, _built_assets_mtime
    
    wrapped_index = os.path.join('pbj-wrapped', 'dist', 'index.html')
    if not os.path.exists(wrapped_index):
        return {'scripts': '', 'stylesheets': ''}
    
    # Check if file has been modified (cache invalidation)
    try:
        current_mtime = os.path.getmtime(wrapped_index)
        if _built_assets_cache is not None and _built_assets_mtime == current_mtime:
            return _built_assets_cache
    except Exception:
        pass
    
    try:
        with open(wrapped_index, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract script tags
        script_pattern = r'<script[^>]*src=["\']([^"\']+)["\'][^>]*></script>'
        scripts = re.findall(script_pattern, content)
        script_tags = '\n'.join([f'    <script type="module" crossorigin src="{s}"></script>' for s in scripts])
        
        # Extract link tags for stylesheets
        link_pattern = r'<link[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\'][^>]*>'
        links = re.findall(link_pattern, content)
        link_tags = '\n'.join([f'    <link rel="stylesheet" crossorigin href="{l}">' for l in links])
        
        result = {'scripts': script_tags, 'stylesheets': link_tags}
        
        # Cache the result
        _built_assets_cache = result
        try:
            _built_assets_mtime = os.path.getmtime(wrapped_index)
        except Exception:
            _built_assets_mtime = None
        
        return result
    except Exception as e:
        print(f"Warning: Could not extract assets from built index.html: {e}")
        return {'scripts': '', 'stylesheets': ''}

def get_dynamic_dates():
    """Get dynamic date information"""
    try:
        return get_latest_data_periods()
    except Exception as e:
        print(f"Warning: Could not get dynamic dates: {e}")
        return {
            'data_range': '2017-2025',
            'quarter_count': 33,
            'provider_info_latest': 'September 2025',
            'provider_info_previous': 'June 2025',
            'affiliated_entity_latest': 'July 2025',
            'current_year': 2025
        }

@app.route('/api/dates')
def api_dates():
    """API endpoint to get dynamic date information"""
    return jsonify(get_dynamic_dates())

@app.route('/')
def index():
    return send_file('index.html', mimetype='text/html')

@app.route('/about')
def about():
    return send_file('about.html', mimetype='text/html')

@app.route('/insights')
@app.route('/insights/')
def insights():
    return send_file('insights.html', mimetype='text/html')

@app.route('/pbj-sample')
def pbj_sample():
    """Handle both /pbj-sample and /pbj-sample.html"""
    return send_file('pbj-sample.html', mimetype='text/html')

@app.route('/report')
@app.route('/report/')
def report():
    return send_file('report.html', mimetype='text/html')

@app.route('/sitemap.xml')
def sitemap():
    return send_file('sitemap.xml', mimetype='application/xml')


# State name to code mapping
STATE_NAME_TO_CODE = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA',
    'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA',
    'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
    'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS', 'missouri': 'MO',
    'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
    'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH',
    'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT',
    'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
    'district of columbia': 'DC', 'puerto rico': 'PR'
}

STATE_CODE_TO_NAME = {v: k.title() for k, v in STATE_NAME_TO_CODE.items()}

# Canonical slug mapping: state code -> canonical slug (lowercase, hyphenated)
# Examples: TN -> /tn, NY -> /new-york
def get_canonical_slug(state_code):
    """Get canonical URL slug for a state (e.g., 'tn', 'new-york')"""
    state_name = STATE_CODE_TO_NAME.get(state_code.upper(), '')
    if not state_name:
        return state_code.lower()
    # Convert state name to slug: "New York" -> "new-york", "Tennessee" -> "tennessee"
    slug = state_name.lower().replace(' ', '-')
    return slug

# Build alias mapping: all possible inputs -> canonical slug
STATE_ALIAS_TO_SLUG = {}
for state_name_lower, state_code in STATE_NAME_TO_CODE.items():
    canonical_slug = get_canonical_slug(state_code)
    state_name = STATE_CODE_TO_NAME[state_code]
    
    # Add all aliases
    STATE_ALIAS_TO_SLUG[state_code.lower()] = canonical_slug  # 'tn' -> 'tennessee'
    STATE_ALIAS_TO_SLUG[state_code.upper()] = canonical_slug  # 'TN' -> 'tennessee'
    STATE_ALIAS_TO_SLUG[state_name_lower] = canonical_slug  # 'tennessee' -> 'tennessee'
    STATE_ALIAS_TO_SLUG[state_name_lower.replace(' ', '-')] = canonical_slug  # 'new-york' -> 'new-york'
    STATE_ALIAS_TO_SLUG[state_name_lower.replace(' ', '')] = canonical_slug  # 'newyork' -> 'new-york'
    STATE_ALIAS_TO_SLUG[state_name] = canonical_slug  # 'Tennessee' -> 'tennessee'
    STATE_ALIAS_TO_SLUG[state_name.replace(' ', '-')] = canonical_slug  # 'New York' -> 'new-york'
    STATE_ALIAS_TO_SLUG[state_name.replace(' ', '')] = canonical_slug  # 'NewYork' -> 'new-york'

def resolve_state_slug(identifier):
    """Resolve any state identifier to canonical slug and state code"""
    identifier_clean = identifier.strip().lower()
    
    # Check direct alias mapping
    if identifier_clean in STATE_ALIAS_TO_SLUG:
        canonical_slug = STATE_ALIAS_TO_SLUG[identifier_clean]
        # Find state code from slug
        for code, name in STATE_CODE_TO_NAME.items():
            if get_canonical_slug(code) == canonical_slug:
                return canonical_slug, code
    return None, None

def load_state_agency_contact():
    """Load state agency contact information from JSON"""
    contact_paths = [
        'pbj-wrapped/public/data/json/state_agency_contact.json',
        'pbj-wrapped/public/data/json/state_contact.json',
    ]
    
    for path in contact_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Convert list to dict keyed by state_code
                    if isinstance(data, list):
                        contact_dict = {}
                        for item in data:
                            state_code = item.get('state_code', '').upper()
                            if state_code:
                                contact_dict[state_code] = item
                        return contact_dict
                    elif isinstance(data, dict):
                        return data
            except Exception as e:
                print(f"Error loading state contact data from {path}: {e}")
                continue
    return {}

def load_csv_data(filename):
    """Load CSV data, trying multiple locations"""
    possible_paths = [
        filename,
        os.path.join('pbj-wrapped', 'public', 'data', filename),
        os.path.join('pbj-wrapped', 'dist', 'data', filename),
        os.path.join('data', filename),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                if HAS_PANDAS:
                    return pd.read_csv(path)
                else:
                    # Fallback to CSV reader
                    with open(path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        return list(reader)
            except Exception as e:
                print(f"Error loading {path}: {e}")
                continue
    return None

def get_latest_quarter(df):
    """Get the most recent quarter from a dataframe"""
    if HAS_PANDAS and isinstance(df, pd.DataFrame):
        if 'CY_Qtr' in df.columns:
            return df['CY_Qtr'].max()
    return None

def format_quarter(quarter_str):
    """Convert quarter format from 2025Q2 to Q2 2025"""
    if not quarter_str:
        return "N/A"
    match = re.match(r'(\d{4})Q(\d)', str(quarter_str))
    if match:
        return f"Q{match.group(2)} {match.group(1)}"
    return str(quarter_str)

def load_provider_info():
    """Load provider info data for facility details (ownership, entity, residents, city)"""
    provider_paths = [
        'provider_info_combined_latest.csv',
        'provider_info_combined.csv',
        'pbj-wrapped/public/data/provider_info_combined.csv',
    ]
    
    if not HAS_PANDAS:
        return {}
    
    for path in provider_paths:
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                # Create lookup dict by PROVNUM (use latest quarter if multiple)
                provider_dict = {}
                # Sort by quarter to get latest
                if 'CY_Qtr' in df.columns:
                    df = df.sort_values('CY_Qtr', ascending=False)
                for _, row in df.iterrows():
                    provnum = str(row.get('PROVNUM', row.get('ccn', ''))).strip()
                    if provnum:
                        # Only keep first (latest) entry per PROVNUM
                        if provnum not in provider_dict:
                            provider_dict[provnum] = {
                                'city': row.get('CITY', row.get('city', '')),
                                'ownership_type': row.get('ownership_type', ''),
                                'avg_residents_per_day': row.get('avg_residents_per_day', ''),
                                'entity_name': row.get('entity_name', row.get('affiliated_entity', '')),
                            }
                return provider_dict
            except Exception as e:
                print(f"Error loading provider info from {path}: {e}")
                continue
    return {}

def load_sff_facilities():
    """Load Special Focus Facilities (SFF) data"""
    sff_paths = [
        'pbj-wrapped/public/sff-facilities.json',
        'pbj-wrapped/dist/sff-facilities.json',
        'sff-facilities.json',
    ]
    
    for path in sff_paths:
        if os.path.exists(path):
            try:
                import json
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and 'facilities' in data:
                        return data['facilities']
                    elif isinstance(data, list):
                        return data
            except Exception as e:
                print(f"Error loading SFF data from {path}: {e}")
                continue
    return []

def get_state_historical_data(state_code):
    """Get historical quarterly data for a state to build time series chart"""
    if not HAS_PANDAS:
        return None, None
    try:
        state_df = load_csv_data('state_quarterly_metrics.csv')
        if state_df is None:
            return None, None
        
        # Filter to this state and sort by quarter
        state_rows = state_df[state_df['STATE'] == state_code].sort_values('CY_Qtr')
        if state_rows.empty:
            return None, None
        
        # Build quarters and data arrays
        quarters = []
        hprd_data = []
        
        for _, row in state_rows.iterrows():
            q_str = str(row['CY_Qtr'])
            # Convert 2025Q2 to Q2 2025
            match = re.match(r'(\d{4})Q(\d)', q_str)
            if match:
                quarters.append(f"Q{match.group(2)} {match.group(1)}")
            else:
                quarters.append(q_str)
            
            hprd = float(row['Total_Nurse_HPRD']) if pd.notna(row['Total_Nurse_HPRD']) else 0
            hprd_data.append(round(hprd, 3))
        
        return quarters, hprd_data
    except Exception as e:
        print(f"Error loading historical data for {state_code}: {e}")
        return None, None

def get_national_historical_data():
    """Get historical quarterly data for USA to build time series chart"""
    if not HAS_PANDAS:
        return None, None
    try:
        national_df = load_csv_data('national_quarterly_metrics.csv')
        if national_df is None:
            return None, None
        
        # Sort by quarter
        national_rows = national_df.sort_values('CY_Qtr') if isinstance(national_df, pd.DataFrame) else sorted(national_df, key=lambda x: x.get('CY_Qtr', ''))
        
        if isinstance(national_df, pd.DataFrame):
            if national_rows.empty:
                return None, None
        else:
            if not national_rows:
                return None, None
        
        # Build quarters and data arrays
        quarters = []
        hprd_data = []
        
        if isinstance(national_df, pd.DataFrame):
            for _, row in national_rows.iterrows():
                q_str = str(row['CY_Qtr'])
                # Convert 2025Q2 to Q2 2025
                match = re.match(r'(\d{4})Q(\d)', q_str)
                if match:
                    quarters.append(f"Q{match.group(2)} {match.group(1)}")
                else:
                    quarters.append(q_str)
                
                hprd = float(row['Total_Nurse_HPRD']) if pd.notna(row['Total_Nurse_HPRD']) else 0
                hprd_data.append(round(hprd, 3))
        else:
            for row in national_rows:
                q_str = str(row.get('CY_Qtr', ''))
                match = re.match(r'(\d{4})Q(\d)', q_str)
                if match:
                    quarters.append(f"Q{match.group(2)} {match.group(1)}")
                else:
                    quarters.append(q_str)
                
                hprd = float(row.get('Total_Nurse_HPRD', 0)) if row.get('Total_Nurse_HPRD') else 0
                hprd_data.append(round(hprd, 3))
        
        return quarters, hprd_data
    except Exception as e:
        print(f"Error loading national historical data: {e}")
        return None, None

def generate_us_chart_html():
    """Generate HTML and JavaScript for US staffing trends chart"""
    quarters, hprd_data = get_national_historical_data()
    
    if not quarters or not hprd_data:
        return ""  # Return empty if no data
    
    # Convert to JavaScript arrays
    quarters_js = json.dumps(quarters)
    data_js = json.dumps(hprd_data)
    
    # Calculate end year from quarters
    end_year = quarters[-1].split(' ')[1] if quarters else "2025"
    start_year = quarters[0].split(' ')[1] if quarters else "2017"
    
    chart_html = f"""
    <section class="mobile-chart" id="usChart" aria-label="US nursing home staffing trends chart" style="margin: 1.5em 0; max-width: 600px;">
        <div class="chart-container" style="background-color: #f8f9fa; padding: 0.5em; border-radius: 4px;">
            <canvas id="usStaffingChart" width="600" height="300" aria-label="US staffing trends line chart" style="max-width: 100%; height: auto;"></canvas>
        </div>
        <div class="chart-footer" style="margin-top: 0.5em;">
            <div class="explore-link" style="text-align: center; margin-bottom: 0.3em;">
                <a href="https://pbjdashboard.com/" target="_blank" style="color: #0645ad; text-decoration: none;">Explore US PBJ Data ↗</a>
            </div>
        </div>
        <div class="chart-source" style="font-size: 0.75em; color: #54595d; text-align: center; margin-top: 0.5em;">
            Source: CMS Payroll-Based Journal Data • 320 Consulting
        </div>
    </section>
    <script>
        (function() {{
            const chartCanvas = document.getElementById('usStaffingChart');
            if (!chartCanvas) return;
            
            const ctx = chartCanvas.getContext('2d');
            const quarters = {quarters_js};
            const data = {data_js};
            
            function drawChart() {{
                const paddingTop = 30;
                const paddingBottom = 40;
                const paddingLeft = 50;
                const paddingRight = 20;
                const chartWidth = chartCanvas.width - paddingLeft - paddingRight;
                const chartHeight = chartCanvas.height - paddingTop - paddingBottom;
                
                // Clear canvas
                ctx.clearRect(0, 0, chartCanvas.width, chartCanvas.height);
                
                // Find min and max values
                const minValue = Math.min(...data);
                const maxValue = Math.max(...data);
                const range = maxValue - minValue || 1;
                
                // Draw grid lines
                ctx.strokeStyle = '#e0e0e0';
                ctx.lineWidth = 1;
                for (let i = 0; i <= 5; i++) {{
                    const y = paddingTop + (chartHeight * i / 5);
                    ctx.beginPath();
                    ctx.moveTo(paddingLeft, y);
                    ctx.lineTo(chartCanvas.width - paddingRight, y);
                    ctx.stroke();
                    
                    // Y-axis labels
                    const value = maxValue - (range * i / 5);
                    ctx.fillStyle = '#54595d';
                    ctx.font = '10px Arial';
                    ctx.textAlign = 'right';
                    ctx.fillText(value.toFixed(2), paddingLeft - 10, y + 4);
                }}
                
                // Draw line
                ctx.strokeStyle = '#0645ad';
                ctx.lineWidth = 2;
                ctx.beginPath();
                data.forEach((value, index) => {{
                    const x = paddingLeft + (chartWidth * index / (data.length - 1));
                    const y = chartCanvas.height - paddingBottom - ((value - minValue) / range * chartHeight);
                    if (index === 0) {{
                        ctx.moveTo(x, y);
                    }} else {{
                        ctx.lineTo(x, y);
                    }}
                }});
                ctx.stroke();
                
                // Draw points
                ctx.fillStyle = '#0645ad';
                data.forEach((value, index) => {{
                    const x = paddingLeft + (chartWidth * index / (data.length - 1));
                    const y = chartCanvas.height - paddingBottom - ((value - minValue) / range * chartHeight);
                    ctx.beginPath();
                    ctx.arc(x, y, 3, 0, 2 * Math.PI);
                    ctx.fill();
                }});
                
                // X-axis labels
                ctx.fillStyle = '#202122';
                ctx.font = '10px Arial';
                ctx.textAlign = 'center';
                const maxLabels = 12;
                const labelStep = Math.max(1, Math.ceil(data.length / maxLabels));
                data.forEach((value, index) => {{
                    if (index === 0 || index === data.length - 1 || index % labelStep === 0) {{
                        const x = paddingLeft + (chartWidth * index / (data.length - 1));
                        const label = quarters[index] || '';
                        ctx.save();
                        ctx.translate(x, chartCanvas.height - paddingBottom + 20);
                        ctx.rotate(-Math.PI / 4);
                        ctx.fillText(label, 0, 0);
                        ctx.restore();
                    }}
                }});
                
                // Title
                ctx.fillStyle = '#202122';
                ctx.font = 'bold 13px Arial';
                ctx.textAlign = 'center';
                ctx.fillText('US Nursing Home Staffing ({start_year}-{end_year})', chartCanvas.width / 2, paddingTop - 5);
            }}
            
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', drawChart);
            }} else {{
                drawChart();
            }}
        }})();
    </script>
    """
    return chart_html

def generate_state_chart_html(state_name, state_code):
    """Generate HTML and JavaScript for state staffing trends chart"""
    quarters, hprd_data = get_state_historical_data(state_code)
    
    if not quarters or not hprd_data:
        return ""  # Return empty if no data
    
    # Convert to JavaScript arrays
    quarters_js = json.dumps(quarters)
    data_js = json.dumps(hprd_data)
    
    # Calculate end year from quarters
    end_year = quarters[-1].split(' ')[1] if quarters else "2025"
    start_year = quarters[0].split(' ')[1] if quarters else "2017"
    
    chart_html = f"""
    <section class="mobile-chart" id="stateChart" aria-label="Nursing home staffing trends chart" style="margin: 1.5em 0; max-width: 600px;">
        <div class="chart-header" style="margin-bottom: 0.5em;">
        <div class="chart-container" style="background-color: #f8f9fa; padding: 0.5em; border-radius: 4px;">
            <canvas id="stateStaffingChart" width="600" height="300" aria-label="Staffing trends line chart" style="max-width: 100%; height: auto;"></canvas>
        </div>
        <div class="chart-footer" style="margin-top: 0.5em;">
            <div class="explore-link" style="text-align: center; margin-bottom: 0.3em;">
                <a href="https://pbjdashboard.com/?state={state_code}" target="_blank" style="color: #0645ad; text-decoration: none;">Explore {state_name} PBJ Data ↗</a>
            </div>
        </div>
        <div class="chart-source" style="font-size: 0.75em; color: #54595d; text-align: center; margin-top: 0.5em;">
            Source: CMS Payroll-Based Journal Data • 320 Consulting
        </div>
    </section>
    <script>
        (function() {{
            const chartCanvas = document.getElementById('stateStaffingChart');
            if (!chartCanvas) return;
            
            const ctx = chartCanvas.getContext('2d');
            const quarters = {quarters_js};
            const data = {data_js};
            
            function drawChart() {{
                ctx.clearRect(0, 0, chartCanvas.width, chartCanvas.height);
                
                if (!data || data.length === 0) return;
                
                const maxValue = Math.max(...data) + 0.1;
                const minValue = Math.min(...data) - 0.1;
                const range = maxValue - minValue || 1;
                const paddingLeft = 40;
                const paddingRight = 30;
                const paddingTop = 20;
                const paddingBottom = 40;  // Increased to prevent label bleeding
                const chartWidth = chartCanvas.width - paddingLeft - paddingRight;
                const chartHeight = chartCanvas.height - paddingTop - paddingBottom;
                
                // Draw axes
                ctx.strokeStyle = '#a2a9b1';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(paddingLeft, paddingTop);
                ctx.lineTo(paddingLeft, chartCanvas.height - paddingBottom);
                ctx.lineTo(chartCanvas.width - paddingRight, chartCanvas.height - paddingBottom);
                ctx.stroke();
                
                // Y-axis labels
                ctx.fillStyle = '#202122';
                ctx.font = '11px Arial';
                ctx.textAlign = 'right';
                const ySteps = 4;
                for (let i = 0; i <= ySteps; i++) {{
                    const value = minValue + (range * i / ySteps);
                    const y = chartCanvas.height - paddingBottom - (chartHeight * i / ySteps);
                    ctx.fillText(value.toFixed(1), paddingLeft - 5, y + 3);
                }}
                
                // Y-axis label
                ctx.save();
                ctx.translate(12, chartCanvas.height / 2);
                ctx.rotate(-Math.PI / 2);
                ctx.textAlign = 'center';
                ctx.font = 'bold 12px Arial';
                ctx.fillStyle = '#202122';
                ctx.fillText('Hours Per Resident Day', 0, 0);
                ctx.restore();
                
                // Draw line
                ctx.strokeStyle = '#0645ad';
                ctx.lineWidth = 2.5;
                ctx.beginPath();
                
                data.forEach((value, index) => {{
                    const x = paddingLeft + (chartWidth * index / (data.length - 1));
                    const y = chartCanvas.height - paddingBottom - ((value - minValue) / range * chartHeight);
                    
                    if (index === 0) {{
                        ctx.moveTo(x, y);
                    }} else {{
                        ctx.lineTo(x, y);
                    }}
                }});
                ctx.stroke();
                
                // Draw points
                ctx.fillStyle = '#0645ad';
                data.forEach((value, index) => {{
                    const x = paddingLeft + (chartWidth * index / (data.length - 1));
                    const y = chartCanvas.height - paddingBottom - ((value - minValue) / range * chartHeight);
                    ctx.beginPath();
                    ctx.arc(x, y, 3, 0, 2 * Math.PI);
                    ctx.fill();
                }});
                
                // X-axis labels - show all quarters, rotated to prevent overlap
                ctx.fillStyle = '#202122';
                ctx.font = '10px Arial';
                ctx.textAlign = 'center';
                // Show all labels but space them out if too many
                const maxLabels = 12;  // Maximum labels to show
                const labelStep = Math.max(1, Math.ceil(data.length / maxLabels));
                data.forEach((value, index) => {{
                    // Show first, last, and every Nth label
                    if (index === 0 || index === data.length - 1 || index % labelStep === 0) {{
                        const x = paddingLeft + (chartWidth * index / (data.length - 1));
                        const label = quarters[index] || '';
                        ctx.save();
                        // Position label higher to prevent bleeding
                        ctx.translate(x, chartCanvas.height - paddingBottom + 20);
                        ctx.rotate(-Math.PI / 4);
                        ctx.fillText(label, 0, 0);
                        ctx.restore();
                    }}
                }});
                
                // Title
                ctx.fillStyle = '#202122';
                ctx.font = 'bold 13px Arial';
                ctx.textAlign = 'center';
                ctx.fillText('{state_name} Nursing Home Staffing ({start_year}-{end_year})', chartCanvas.width / 2, paddingTop - 5);
            }}
            
            // Draw chart when page loads
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', drawChart);
            }} else {{
                drawChart();
            }}
        }})();
    </script>
    """
    return chart_html

def generate_state_page_html(state_name, state_code, state_data, macpac_standard, region_info, quarter, rank_total=None, rank_rn=None, total_states=None, sff_facilities=None, raw_quarter=None, contact_info=None):
    """Generate HTML for state page - returns full Wikipedia-style page"""
    # Format data values
    def fmt(val, decimals=2):
        try:
            if pd.isna(val) or val is None:
                return "N/A"
            return f"{float(val):.{decimals}f}"
        except:
            return "N/A"
    
    def get_val(key, default='N/A'):
        try:
            if isinstance(state_data, dict):
                return state_data.get(key, default)
            else:
                return state_data.get(key, default) if hasattr(state_data, 'get') else getattr(state_data, key, default)
        except:
            return default
    
    # Calculate rankings for each metric
    def get_rank_for_metric(metric_key):
        """Get ranking for a specific metric (1 = best/highest)"""
        if not HAS_PANDAS or raw_quarter is None:
            return None
        try:
            # Load all state data for latest quarter
            state_df = load_csv_data('state_quarterly_metrics.csv')
            if state_df is None:
                return None
            latest_all = state_df[state_df['CY_Qtr'] == raw_quarter]
            if latest_all.empty:
                return None
            latest_all_sorted = latest_all.sort_values(metric_key, ascending=False).reset_index(drop=True)
            state_idx = latest_all_sorted[latest_all_sorted['STATE'] == state_code].index
            if not state_idx.empty:
                return int(state_idx[0]) + 1
        except:
            pass
        return None
    
    # Region link removed per user request
    region_link = ""
    
    macpac_section = ""
    if macpac_standard is not None:
        try:
            display_text = macpac_standard.get('Display_Text', '') if isinstance(macpac_standard, dict) else getattr(macpac_standard, 'Display_Text', '')
            min_staffing_raw = macpac_standard.get('Min_Staffing', '') if isinstance(macpac_standard, dict) else getattr(macpac_standard, 'Min_Staffing', '')
            # Handle Min_Staffing - it might be a string like "0.30" or "0.30 HPRD"
            min_staffing_val = str(min_staffing_raw).replace(' HPRD', '').strip()
            try:
                min_staffing_num = float(min_staffing_val)
                min_staffing_display = fmt(min_staffing_num, 2)
            except:
                min_staffing_display = str(min_staffing_raw)
            # Remove "State Standard:" prefix from display_text if it exists
            clean_display_text = display_text.replace('State Standard: ', '').strip()
            # Check if clean_display_text already contains the HPRD value to avoid redundancy
            hprd_in_text = min_staffing_display in clean_display_text or f"{min_staffing_display} HPRD" in clean_display_text
            if hprd_in_text:
                # If HPRD is already in the text, don't add it again
                macpac_section = f"""
        <h2>{state_name} Staffing Requirements</h2>
        <p><strong>State Standard:</strong> {clean_display_text}</p>
        """
            else:
                # If HPRD is not in the text, add it
                macpac_section = f"""
        <h2>{state_name} Staffing Requirements</h2>
        <p><strong>State Standard:</strong> {clean_display_text} ({min_staffing_display} HPRD)</p>
        """
        except Exception as e:
            print(f"Error formatting MACPAC section: {e}")
            pass
    
    # If no state standard found, explicitly note this
    if not macpac_section:
        macpac_section = f"""
        <h2>{state_name} Staffing Requirements</h2>
        <p><strong>No state-level minimum staffing requirement beyond federal requirements.</strong> {state_name} nursing homes must meet federal minimum staffing requirements.</p>
        """
    
    # Get basics
    facility_count = int(float(get_val('facility_count', 0)))
    avg_daily_census_val = get_val('avg_daily_census', 0)
    try:
        avg_daily_census_float = float(avg_daily_census_val) if avg_daily_census_val != 'N/A' else 0
    except:
        avg_daily_census_float = 0
    
    # Calculate total residents: nursing homes × average daily census
    total_residents = int(facility_count * avg_daily_census_float) if avg_daily_census_float > 0 and facility_count > 0 else 0
    total_residents_display = f"{total_residents:,}" if total_residents > 0 else "N/A"
    
    total_resident_days = get_val('total_resident_days', 0)
    try:
        resident_count = int(float(total_resident_days) / 90) if total_resident_days != 'N/A' else 'N/A'
    except:
        resident_count = 'N/A'
    
    # Get rankings for each metric
    rank_total_nurse = get_rank_for_metric('Total_Nurse_HPRD') or rank_total
    rank_rn_hprd = get_rank_for_metric('RN_HPRD') or rank_rn
    rank_direct_care = get_rank_for_metric('Nurse_Care_HPRD')
    rank_rn_care = get_rank_for_metric('RN_Care_HPRD')
    rank_nurse_aide = get_rank_for_metric('Nurse_Assistant_HPRD')
    
    # Get Total HPRD with rank for overview table
    total_hprd_val = fmt(get_val('Total_Nurse_HPRD'))
    total_hprd_display = total_hprd_val
    if rank_total_nurse and total_states:
        # Proper ordinal suffix: 1st, 2nd, 3rd, 4th, etc.
        # Special cases: 11th, 12th, 13th (not 11st, 12nd, 13rd)
        rank = rank_total_nurse
        if rank % 100 in [11, 12, 13]:
            suffix = 'th'
        elif rank % 10 == 1:
            suffix = 'st'
        elif rank % 10 == 2:
            suffix = 'nd'
        elif rank % 10 == 3:
            suffix = 'rd'
        else:
            suffix = 'th'
        total_hprd_display = f"{total_hprd_val} ({rank}{suffix})"
    
    # Basics section
    basics_section = f"""
    <div class="infobox" style="width: 280px; margin: 0 0 1em 1em; float: right; clear: right; border: 1px solid #a2a9b1; background-color: #f8f9fa;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr><th colspan="2" scope="colgroup" style="background-color: #eaecf0; padding: 0.6em 0.5em; text-align: center; border-bottom: 1px solid #a2a9b1; font-weight: bold;">{state_name} Overview ({quarter})</th></tr>
            <tr><td style="padding: 0.4em 0.5em; font-weight: bold; border-bottom: 1px solid #a2a9b1; background-color: #f8f9fa;">Nursing Homes</td><td style="padding: 0.4em 0.5em; border-bottom: 1px solid #a2a9b1; text-align: right; background-color: #ffffff;">{facility_count:,}</td></tr>
            <tr><td style="padding: 0.4em 0.5em; font-weight: bold; border-bottom: 1px solid #a2a9b1; background-color: #f8f9fa;">Residents</td><td style="padding: 0.4em 0.5em; border-bottom: 1px solid #a2a9b1; text-align: right; background-color: #ffffff;">{total_residents_display}</td></tr>
            <tr><td style="padding: 0.4em 0.5em; font-weight: bold; background-color: #f8f9fa;">Total HPRD</td><td style="padding: 0.4em 0.5em; text-align: right; background-color: #ffffff; white-space: normal; word-wrap: break-word;">{total_hprd_display}</td></tr>
        </table>
    </div>
    """
    
    # Helper function to capitalize facility names properly
    def capitalize_facility_name(name):
        """Capitalize facility name: first letter of each word, except 'at', 'and', 'of', 'the', 'for'"""
        if not name:
            return name
        words = name.split()
        small_words = {'at', 'and', 'of', 'the', 'for', 'in', 'on', 'to', 'a', 'an'}
        capitalized = []
        for i, word in enumerate(words):
            # Always capitalize first word, or if word is not in small_words, or if previous word ends with punctuation
            if i == 0 or word.lower() not in small_words or (i > 0 and words[i-1][-1] in '.,;:'):
                # Preserve hyphens and apostrophes
                if '-' in word:
                    parts = word.split('-')
                    capitalized.append('-'.join([p.capitalize() if p else p for p in parts]))
                elif "'" in word:
                    parts = word.split("'")
                    capitalized.append("'".join([p.capitalize() if p else p for p in parts]))
                else:
                    capitalized.append(word.capitalize())
            else:
                capitalized.append(word.lower())
        return ' '.join(capitalized)
    
    # Helper function to capitalize city names properly (Title Case)
    def capitalize_city_name(city):
        """Capitalize city name: Title Case (e.g., CAMPBELL HALL -> Campbell Hall)"""
        if not city:
            return city
        # Split by spaces and capitalize each word
        words = city.split()
        return ' '.join([word.capitalize() for word in words])
    
    # Load provider info for SFF facilities
    provider_info = load_provider_info()
    
    # Helper to format ownership type
    def format_ownership_type(ownership):
        """Format ownership type: For-Profit, Non Profit, or Government"""
        if not ownership:
            return ""
        ownership_lower = str(ownership).lower().strip()
        # Remove common suffixes like "Corporation", "LLC", etc.
        ownership_clean = re.sub(r'\s*(corporation|corp|llc|l\.l\.c\.|inc|incorporated|partnership|partners|co\.|company)\s*$', '', ownership_lower, flags=re.IGNORECASE)
        if 'profit' in ownership_clean and 'non' not in ownership_clean:
            return "For-Profit"
        elif 'non-profit' in ownership_clean or 'nonprofit' in ownership_clean or ('non' in ownership_clean and 'profit' in ownership_clean):
            return "Non Profit"
        elif 'government' in ownership_clean or 'gov' in ownership_clean:
            return "Government"
        return ownership
    
    # SFF facilities section
    sff_section = ""
    if sff_facilities:
        facility_count = len(sff_facilities)
        facility_word = "facility" if facility_count == 1 else "facilities"
        sff_section = f"""
    <h2>Special Focus Facilities (SFF)</h2>
    <p>{state_name} has <strong>{facility_count}</strong> {facility_word} in the Special Focus Facility program:</p>
    <ul class="sff-facilities-list">
    """
        for facility in sff_facilities:  # List ALL facilities
            facility_name = facility.get('facility_name', 'Unknown')
            provider_number = facility.get('provider_number', '')
            months_sff = facility.get('months_as_sff', 0)
            city = facility.get('city', '')
            
            # Get provider info
            prov_info = provider_info.get(provider_number, {})
            if not city:
                city = prov_info.get('city', '')
            residents = prov_info.get('avg_residents_per_day', '')
            ownership = format_ownership_type(prov_info.get('ownership_type', ''))
            entity = prov_info.get('entity_name', '')
            
            # Capitalize properly
            facility_name_cap = capitalize_facility_name(facility_name)
            city_cap = capitalize_city_name(city) if city else ''
            # Create link to PBJ Dashboard
            dashboard_link = f'https://pbjdashboard.com/?facility={provider_number}'
            
            # Build facility line (polished format)
            facility_line = f'<li><a href="{dashboard_link}" target="_blank">{facility_name_cap}</a>'
            if city_cap:
                facility_line += f' ({city_cap})'
            facility_line += f' – {months_sff} months as SFF'
            if residents:
                try:
                    residents_int = int(float(residents))
                    facility_line += f' - {residents_int} residents'
                except:
                    pass
            if ownership:
                facility_line += f', {ownership}'
            if entity:
                facility_line += f': {entity}'
            facility_line += '</li>'
            sff_section += facility_line
        sff_section += "</ul>"
    
    # Ranking info removed - already shown in overview table
    ranking_info = ""
    
    # Generate chart HTML (with dynamic state name in heading)
    chart_html = generate_state_chart_html(state_name, state_code)
    
    # Generate contact/complaint section (Wikipedia-style, factual)
    contact_section = ""
    if contact_info:
        phone_html = ""
        if contact_info.get('phone'):
            phones = contact_info['phone']
            phone_parts = []
            if phones.get('general'):
                phone_parts.append(f"General: {', '.join(phones['general'])}")
            if phones.get('toll_free'):
                phone_parts.append(f"Toll-free: {', '.join(phones['toll_free'])}")
            if phones.get('hha'):
                phone_parts.append(f"Home Health Agency: {', '.join(phones['hha'])}")
            if phones.get('hospice'):
                phone_parts.append(f"Hospice: {', '.join(phones['hospice'])}")
            if phone_parts:
                phone_html = "<p>" + " | ".join(phone_parts) + "</p>"
        
        website_url = contact_info.get('website_url', '')
        website_link = f'<p>Complaint website: <a href="{website_url}" target="_blank" rel="noopener">{website_url}</a></p>' if website_url else ""
        
        notes = contact_info.get('notes', [])
        notes_html = ""
        if notes:
            notes_html = "<p>" + " ".join(notes) + "</p>"
        
        contact_section = f"""
    <h2>Filing Complaints & Contact Information</h2>
    <p>Complaints about nursing homes in {state_name} may be filed with the state regulatory agency. Contact information:</p>
    {phone_html}
    {website_link}
    {notes_html}
    <p><small>Contact information is provided for reference. For current information, consult the state agency website.</small></p>
    """
    elif macpac_standard is None:
        # If no state standard AND no contact info, note that complaints go to CMS
        contact_section = """
    <h2>Filing Complaints & Contact Information</h2>
    <p>To file a complaint about a nursing home, contact your state's health department or the <a href="https://www.medicare.gov/care-compare/" target="_blank" rel="noopener">Medicare Care Compare</a> complaint system.</p>
    """
    
    # Generate CTA section for attorneys/journalists
    cta_section = f"""
    <div style="background-color: #f8f9fa; border: 1px solid #a7d7f9; border-radius: 4px; padding: 1.5em; margin: 2em 0;">
        <h3 style="margin-top: 0; font-size: 1.1em;">Custom PBJ Analysis for Attorneys & Journalists</h3>
        <p>320 Consulting offers custom reports and dashboards for {state_name} nursing homes with daily, position-level analysis and data visualizations tied to ratings, enforcement, and other critical metrics to support your casework and advocacy. Check out a <a href="https://pbj320-395258.vercel.app/" target="_blank" rel="noopener">sample dashboard</a>.</p>
        <p><strong>Contact:</strong> <a href="mailto:eric@320insight.com">eric@320insight.com</a> | <a href="tel:+19298084996">(347) 992-3569</a> (text preferred)</p>
        <p style="margin-bottom: 0;"><strong>Journalists:</strong> If you're working on a story, I'm happy to share data or walk you through it.</p>
    </div>
    """
    
    # Generate narrative summary with staffing standard at the end
    total_hprd = fmt(get_val('Total_Nurse_HPRD'))
    narrative_summary = f"""
    <p>In {quarter}, {state_name} nursing homes reported an average of <strong>{total_hprd} hours per resident day</strong> of total nurse staffing. This includes registered nurses (RNs), licensed practical nurses (LPNs), and nurse aides.</p>
    """
    # Combine ranking and staffing standard into one line
    if rank_total_nurse and total_states:
        ranking_text = f"{state_name} ranks <strong>#{rank_total_nurse} of {total_states}</strong> states for total nurse staffing HPRD"
        
        # Add staffing standard to the same line
        if macpac_standard is not None:
            try:
                display_text = macpac_standard.get('Display_Text', '') if isinstance(macpac_standard, dict) else getattr(macpac_standard, 'Display_Text', '')
                min_staffing_raw = macpac_standard.get('Min_Staffing', '') if isinstance(macpac_standard, dict) else getattr(macpac_standard, 'Min_Staffing', '')
                min_staffing_val = str(min_staffing_raw).replace(' HPRD', '').strip()
                try:
                    min_staffing_num = float(min_staffing_val)
                    min_staffing_display = fmt(min_staffing_num, 2)
                except:
                    min_staffing_display = str(min_staffing_raw)
                clean_display_text = display_text.replace('State Standard: ', '').strip()
                # Check if HPRD is already in the text
                hprd_in_text = min_staffing_display in clean_display_text or f"{min_staffing_display} HPRD" in clean_display_text
                if hprd_in_text:
                    # Extract just the HPRD value if it's in the text
                    standard_text = clean_display_text
                else:
                    standard_text = f"{min_staffing_display} HPRD"
                ranking_text += f" (state standard: {standard_text})"
            except Exception as e:
                print(f"Error formatting staffing standard: {e}")
                pass
        
        narrative_summary += f"<p>{ranking_text}.</p>"
    
    # Remove MACPAC section - it's now in the overview
    content = f"""
    {basics_section}
    {narrative_summary}
    {ranking_info}
    {chart_html}
    <h2>Staffing Metrics ({quarter})</h2>
    <table class="wikitable" style="max-width: 600px;">
        <tr><th scope="col">Metric</th><th scope="col">Value</th><th scope="col">National Rank</th></tr>
        <tr><td>Total Nurse Staffing HPRD</td><td>{fmt(get_val('Total_Nurse_HPRD'))}</td><td>#{rank_total_nurse} of {total_states if total_states else 'N/A'}</td></tr>
        <tr><td>RN HPRD</td><td>{fmt(get_val('RN_HPRD'))}</td><td>#{rank_rn_hprd} of {total_states if total_states else 'N/A'}</td></tr>
        <tr><td>Direct Care Nurse HPRD</td><td>{fmt(get_val('Nurse_Care_HPRD'))}</td><td>#{rank_direct_care} of {total_states if rank_direct_care and total_states else 'N/A'}</td></tr>
        <tr><td>RN Direct Care HPRD</td><td>{fmt(get_val('RN_Care_HPRD'))}</td><td>#{rank_rn_care} of {total_states if rank_rn_care and total_states else 'N/A'}</td></tr>
        <tr><td>Nurse Aide HPRD</td><td>{fmt(get_val('Nurse_Assistant_HPRD'))}</td><td>#{rank_nurse_aide} of {total_states if rank_nurse_aide and total_states else 'N/A'}</td></tr>
        <tr><td>Contract Staff Percentage</td><td>{fmt(get_val('Contract_Percentage'))}%</td><td>—</td></tr>
        <tr><td>Direct Care Percentage</td><td>{fmt(get_val('Direct_Care_Percentage'))}%</td><td>—</td></tr>
        <tr><td>Total RN Percentage</td><td>{fmt(get_val('Total_RN_Percentage'))}%</td><td>—</td></tr>
        <tr><td>Nurse Aide Percentage</td><td>{fmt(get_val('Nurse_Aide_Percentage'))}%</td><td>—</td></tr>
    </table>
    
    {sff_section}
    
    {region_link}
    
    <h2>Explore {state_name} Data</h2>
    <ul>
        <li><a href="https://pbjdashboard.com/?state={state_code}" target="_blank" rel="noopener">{state_name} PBJ Dashboard</a> – Statewide staffing trends and facility-level data</li>
        <li><a href="https://www.pbj320.com/sff/{state_code.lower()}" target="_blank" rel="noopener">{state_name} Special Focus</a> – Staffing data on the state's Special Focus Facilities, SFF Candidates, Graduates, and Decertified Facilities</li>
        <li><a href="https://www.pbj320.com/wrapped/{state_code.lower()}" target="_blank" rel="noopener">{state_name} PBJ Wrapped</a> – Interactive state-level analysis</li>

    </ul>
    
    {cta_section}
    
    <h2>Related PBJpedia Pages</h2>
    <ul>
        <li><a href="/pbjpedia/state-standards">State Staffing Standards</a> – Overview of federal and state minimum staffing requirements</li>
        <li><a href="/pbjpedia/metrics">PBJ Metrics</a> – Definitions of HPRD and other staffing measures</li>
        <li><a href="/pbjpedia/methodology">PBJ Methodology</a> – How PBJ data are collected and published</li>
    </ul>
    
    {contact_section}
    """
    
    # Wikipedia-style title (state name with context)
    page_title = f"{state_name} Nursing Home Staffing"
    
    # Build SEO description for OG tags
    total_hprd = fmt(get_val('Total_Nurse_HPRD'))
    seo_description_parts = [
        f"{state_name} nursing homes averaged {total_hprd} hours per resident day (HPRD) of total nurse staffing in {quarter}."
    ]
    if rank_total_nurse and total_states:
        seo_description_parts.append(f"Ranked #{rank_total_nurse} of {total_states} states.")
    if macpac_standard:
        min_staffing = macpac_standard.get('Min_Staffing', '')
        if min_staffing:
            try:
                min_val = float(str(min_staffing).replace(' HPRD', ''))
                seo_description_parts.append(f"State minimum staffing requirement: {min_val:.2f} HPRD.")
            except:
                pass
    seo_description_parts.append("Data from CMS Payroll-Based Journal (PBJ).")
    seo_description = " ".join(seo_description_parts)
    
    # OG title with SEO info
    og_title = f"{state_name} | PBJ320 Nursing Home Staffing Data"
    
    # OG description for social sharing
    og_description = f"{state_name} reports {total_hprd} HPRD"
    if rank_total_nurse and total_states:
        og_description += f" (rank: {rank_total_nurse})"
    og_description += f" staffing at {facility_count:,} nursing homes and {total_residents_display} residents."
    
    # Canonical slug for URL
    canonical_slug = get_canonical_slug(state_code)
    canonical_url = f"https://pbj320.com/{canonical_slug}"
    
    # Use the same template function as regular pages with enhanced SEO
    return generate_dynamic_pbjpedia_page(
        page_title,  # Wikipedia-style title
        canonical_slug, 
        content, 
        '',
        seo_description=seo_description,
        og_title=og_title,  # SEO-rich OG title
        og_image=f"https://pbj320.com/og/state/{state_code.lower()}.png",
        canonical_url=canonical_url
    )

def generate_region_page_html(region_num, region_data, states_in_region, state_data_list, quarter, rank=None, total_regions=None, sff_facilities=None, raw_quarter=None):
    """Generate HTML for CMS region page"""
    def fmt(val, decimals=2):
        try:
            if pd.isna(val) or val is None:
                return "N/A"
            return f"{float(val):.{decimals}f}"
        except:
            return "N/A"
    
    def get_val(key, default='N/A'):
        try:
            if isinstance(region_data, dict):
                return region_data.get(key, default)
            else:
                return getattr(region_data, key, default)
        except:
            return default
    
    region_name = get_val('REGION_NAME', f'Region {region_num}')
    region_full = get_val('REGION', f'Region {region_num}')
    
    # Get basics
    facility_count = int(float(get_val('facility_count', 0)))
    avg_daily_census_val = get_val('avg_daily_census', 0)
    try:
        avg_daily_census_float = float(avg_daily_census_val) if avg_daily_census_val != 'N/A' else 0
    except:
        avg_daily_census_float = 0
    
    # Calculate total residents: nursing homes × average daily census
    total_residents = int(facility_count * avg_daily_census_float) if avg_daily_census_float > 0 and facility_count > 0 else 0
    total_residents_display = f"{total_residents:,}" if total_residents > 0 else "N/A"
    
    # Basics section
    basics_section = f"""
    <div class="infobox" style="width: 280px; margin-bottom: 1em;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr><th colspan="2" scope="colgroup" style="background-color: #eaecf0; padding: 0.3em; text-align: center; border-bottom: 1px solid #a2a9b1;">{region_full} Overview</th></tr>
            <tr><td style="padding: 0.3em; font-weight: bold; border-bottom: 1px solid #a2a9b1;">Nursing Homes</td><td style="padding: 0.3em; border-bottom: 1px solid #a2a9b1;">{facility_count:,}</td></tr>
            <tr><td style="padding: 0.3em; font-weight: bold; border-bottom: 1px solid #a2a9b1;">Total Residents</td><td style="padding: 0.3em; border-bottom: 1px solid #a2a9b1;">{total_residents_display}</td></tr>
            <tr><td style="padding: 0.3em; font-weight: bold; border-bottom: 1px solid #a2a9b1;">States</td><td style="padding: 0.3em; border-bottom: 1px solid #a2a9b1;">{len(states_in_region)}</td></tr>
            <tr><td style="padding: 0.3em; font-weight: bold;">Reporting Quarter</td><td style="padding: 0.3em;">{quarter}</td></tr>
        </table>
    </div>
    """
    
    # SFF facilities section
    sff_section = ""
    if sff_facilities:
        sff_section = f"""
    <h2>Special Focus Facilities (SFF)</h2>
    <p>{region_full} has <strong>{len(sff_facilities)}</strong> {'facility' if len(sff_facilities) == 1 else 'facilities'} in the Special Focus Facility program across all states in the region.</p>
    """
    
    # Add ranking info
    ranking_info = ""
    if rank and total_regions:
        ranking_info = f"<p><strong>National Ranking:</strong> {region_full} ranks <strong>#{rank} of {total_regions}</strong> CMS regions for Total Nurse Staffing HPRD.</p>"
    
    # States table
    states_table = ""
    if state_data_list:
        # Sort states by Total Nurse HPRD (descending) for ranking
        sorted_states = sorted(state_data_list, key=lambda x: float(x['data'].get('Total_Nurse_HPRD', 0) if isinstance(x['data'], dict) else getattr(x['data'], 'Total_Nurse_HPRD', 0)), reverse=True)
        
        states_table = f"""
        <h2>States in {region_full}</h2>
        <table class="wikitable">
            <tr>
                <th scope="col">Rank</th>
                <th scope="col">State</th>
                <th scope="col">Total Nurse HPRD</th>
                <th scope="col">RN HPRD</th>
                <th scope="col">Direct Care HPRD</th>
                <th scope="col">Contract %</th>
                <th scope="col">Facilities</th>
            </tr>
        """
        for idx, item in enumerate(sorted_states, 1):
            state_info = item['info']
            state_data = item['data']
            state_code = state_info.get('State_Code', '')
            state_name = state_info.get('State_Name', '')
            
            def get_state_val(key, default='N/A'):
                try:
                    if isinstance(state_data, dict):
                        return state_data.get(key, default)
                    else:
                        return getattr(state_data, key, default)
                except:
                    return default
            
            facility_count_val = get_state_val('facility_count', 0)
            try:
                facility_count_int = int(float(facility_count_val))
            except:
                facility_count_int = 0
            
            states_table += f"""
            <tr>
                <td><strong>{idx}</strong></td>
                <td><a href="/pbjpedia/state/{state_code}">{state_name}</a></td>
                <td>{fmt(get_state_val('Total_Nurse_HPRD'))}</td>
                <td>{fmt(get_state_val('RN_HPRD'))}</td>
                <td>{fmt(get_state_val('Nurse_Care_HPRD'))}</td>
                <td>{fmt(get_state_val('Contract_Percentage'))}%</td>
                <td>{facility_count_int}</td>
            </tr>
            """
        states_table += "</table>"
    
    content = f"""
    {basics_section}
    {ranking_info}
    <h2>Region-Wide Staffing Metrics ({quarter})</h2>
    <table class="wikitable">
        <tr><th scope="col">Metric</th><th scope="col">Value</th><th scope="col">Median</th></tr>
        <tr><td>Total Nurse Staffing HPRD</td><td>{fmt(get_val('Total_Nurse_HPRD'))}</td><td>{fmt(get_val('Total_Nurse_HPRD_Median'))}</td></tr>
        <tr><td>RN HPRD</td><td>{fmt(get_val('RN_HPRD'))}</td><td>{fmt(get_val('RN_HPRD_Median'))}</td></tr>
        <tr><td>Direct Care Nurse HPRD</td><td>{fmt(get_val('Nurse_Care_HPRD'))}</td><td>{fmt(get_val('Nurse_Care_HPRD_Median'))}</td></tr>
        <tr><td>RN Direct Care HPRD</td><td>{fmt(get_val('RN_Care_HPRD'))}</td><td>{fmt(get_val('RN_Care_HPRD_Median'))}</td></tr>
        <tr><td>Nurse Aide HPRD</td><td>{fmt(get_val('Nurse_Assistant_HPRD'))}</td><td>{fmt(get_val('Nurse_Assistant_HPRD_Median'))}</td></tr>
        <tr><td>Contract Staff Percentage</td><td>{fmt(get_val('Contract_Percentage'))}%</td><td>{fmt(get_val('Contract_Percentage_Median'))}%</td></tr>
        <tr><td>Direct Care Percentage</td><td>{fmt(get_val('Direct_Care_Percentage'))}%</td><td>—</td></tr>
        <tr><td>Total RN Percentage</td><td>{fmt(get_val('Total_RN_Percentage'))}%</td><td>—</td></tr>
        <tr><td>Nurse Aide Percentage</td><td>{fmt(get_val('Nurse_Aide_Percentage'))}%</td><td>—</td></tr>
        <tr><td>Number of Facilities</td><td>{int(float(get_val('facility_count', 0)))}</td><td>—</td></tr>
        <tr><td>Average Daily Census</td><td>{fmt(get_val('avg_daily_census'))}</td><td>—</td></tr>
    </table>
    
    {states_table}
    
    {sff_section}
    
    <h2>Related PBJpedia Pages</h2>
    <ul>
        <li><a href="/pbjpedia/state-standards">State Staffing Standards</a> – Overview of federal and state minimum staffing requirements</li>
        <li><a href="/pbjpedia/metrics">PBJ Metrics</a> – Definitions of HPRD and other staffing measures</li>
        <li><a href="/pbjpedia/methodology">PBJ Methodology</a> – How PBJ data are collected and published</li>
    </ul>
    """
    
    return generate_dynamic_pbjpedia_page(f"{region_full} Nursing Home Staffing", f"region/{region_num}", content)

def get_pbjpedia_sidebar():
    """Get the PBJpedia sidebar navigation HTML"""
    return """
        <div id="mw-navigation">
            <h2>Navigation menu</h2>
            <div id="mw-panel">
                <div id="p-logo" role="banner">
                    <a href="/pbjpedia/overview" title="Visit the main page">
                        <div style="text-align: center; padding: 0.3em 0.2em;">
                            <img src="/pbj_favicon.png" alt="PBJ320" width="50" height="50" style="margin: 0 auto 0.1em; display: block; max-width: 50px; max-height: 50px;">
                            <div style="font-size: 0.9em; font-weight: bold; color: #0645ad; margin-top: 0;">PBJ320</div>
                        </div>
                    </a>
                </div>
                <div class="portal" role="navigation" id="p-navigation">
                    <div class="body">
                        <ul>
                            <li><a href="/pbjpedia/overview">Overview</a></li>
                            <li><a href="/pbjpedia/methodology">Methodology</a></li>
                            <li><a href="/pbjpedia/metrics">Metrics</a></li>
                            <li><a href="/pbjpedia/state-standards">State Standards</a></li>
                        </ul>
                    </div>
                </div>
                <div class="portal" role="navigation" id="p-tb">
                    <h3>PBJ320</h3>
                    <div class="body">
                        <ul>
                            <li><a href="/">Dashboard</a></li>
                            <li><a href="/insights">Insights</a></li>
                            <li><a href="https://www.320insight.com/phoebe" target="_blank" class="external-link">Phoebe J</a></li>
                        </ul>
                    </div>
                </div>
                <div class="portal" role="navigation" id="p-more">
                    <h3>More</h3>
                    <div class="body">
                        <ul>
                            <li><a href="/about">About</a></li>
                            <li><a href="mailto:eric@320insight.com">Contact</a></li>
                            <li><a href="https://www.320insight.com" target="_blank" class="external-link">320 Consulting</a></li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    """

def generate_dynamic_pbjpedia_page(title, page_path, content, toc_html='', seo_description=None, og_title=None, og_description=None, og_image=None, canonical_url=None):
    """Generate Wikipedia-style HTML page with rigid CSS Grid layout"""
    sidebar_nav = get_pbjpedia_sidebar()
    
    # Move TOC to sidebar if it exists - extract just the UL from TOC
    sidebar_with_toc = sidebar_nav
    if toc_html:
        # Extract the UL content from TOC HTML
        toc_match = re.search(r'<ul[^>]*>(.*?)</ul>', toc_html, re.DOTALL)
        # TOC removed from sidebar per user request
        # if toc_match:
        #     ... (code disabled)
    
    # Set defaults for SEO
    meta_description = seo_description or f"Learn about {title} in PBJpedia, the comprehensive reference guide for Payroll-Based Journal nursing home staffing data."
    og_description_final = og_description or seo_description or f"Nursing home staffing data and analysis for {title} from PBJ320."
    canonical = canonical_url or f"https://pbj320.com/pbjpedia/{page_path}"
    og_image_tag = f'<meta property="og:image" content="{og_image}">' if og_image else ''
    twitter_image_tag = f'<meta name="twitter:image" content="{og_image}">' if og_image else ''
    
    return f"""<!DOCTYPE html>
<html lang="en" dir="ltr" class="client-nojs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="/pbj_favicon.png">
    <title>{og_title if og_title else title} | PBJ320</title>
    <meta name="description" content="{meta_description}">
    <link rel="canonical" href="{canonical}">
    <meta property="og:title" content="{og_title if og_title else title} | PBJ320">
    <meta property="og:description" content="{og_description_final}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{canonical}">
    <meta property="og:site_name" content="PBJ320">
    {og_image_tag}
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="{title} - PBJpedia | PBJ320">
    <meta name="twitter:description" content="{og_description_final}">
    {twitter_image_tag}
    <style>
        /* HARD RESET: Rigid CSS Grid Layout - No Floating, No Absolute Positioning */
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Liberation Sans', sans-serif;
            font-size: 0.875em;
            line-height: 1.6;
            color: #202122;
            background-color: #f8f9fa;
        }}
        
        /* PAGE GRID: Sidebar | Article */
        .pbjpedia-page-container {{
            display: grid;
            grid-template-columns: 10em 1fr;
            min-height: 100vh;
        }}
        
        /* LEFT SIDEBAR - Fixed width, no floating */
        #mw-navigation {{
            grid-column: 1;
            background-color: #f8f9fa;
            border-right: 1px solid #a7d7f9;
            padding: 0.5em;
            font-size: 0.875em;
            position: sticky;
            top: 0;
            height: 100vh;
            overflow-y: auto;
        }}
        #mw-panel {{
            display: flex;
            flex-direction: column;
            gap: 0.5em;
        }}
        #p-logo {{
            margin-bottom: 0.5em;
        }}
        #p-logo a {{
            display: block;
            text-decoration: none;
            padding: 0.3em 0.2em;
            text-align: center;
        }}
        #p-logo img {{
            max-width: 50px;
            max-height: 50px;
            margin: 0 auto 0.1em;
            display: block;
        }}
        #p-logo > a > div > div:first-of-type {{
            font-size: 0.9em;
            font-weight: bold;
            color: #0645ad;
            margin-top: 0;
        }}
        .portal {{
            margin: 0.5em 0;
        }}
        .portal h3 {{
            font-size: 0.75em;
            color: #72777d;
            font-weight: 500;
            margin: 0 0 0.3em 0.7em;
            padding: 0.25em 0;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            pointer-events: none;
        }}
        .portal .body li a.external-link::after {{
            content: ' ↗';
            font-size: 0.8em;
            opacity: 0.7;
        }}
        .portal .body ul {{
            list-style: none;
            margin: 0;
            padding: 0.3em 0 0 0;
        }}
        .portal .body li {{
            line-height: 1.125em;
            margin: 0;
            padding: 0.25em 0;
            font-size: 0.85em;
        }}
        .portal .body li a {{
            color: #0645ad;
            text-decoration: none;
        }}
        .portal .body li a:hover {{
            text-decoration: underline;
        }}
        /* TOC in sidebar */
        #p-toc .body ul {{
            list-style: none;
            margin: 0;
            padding-left: 0.5em;
        }}
        #p-toc .body li {{
            font-size: 0.7em;
            line-height: 1.3;
        }}
        #mw-navigation h2 {{
            display: none;
        }}
        
        /* MAIN ARTICLE COLUMN */
        .mw-body {{
            grid-column: 2;
            background-color: #ffffff;
            border: 1px solid #a7d7f9;
            border-left: none;
            padding: 1em 1.5em;
            max-width: 100%;
            overflow-x: hidden;
        }}
        h1.firstHeading {{
            border-bottom: 1px solid #a7d7f9;
            padding-bottom: 0.25em;
            margin-bottom: 0.3em;
            font-size: 1.8em;
            font-weight: 600;
            margin-top: 0;
        }}
        #siteSub {{
            font-size: 0.9em;
            color: #202122;
            margin-bottom: 0.5em;
            font-weight: 500;
        }}
        .breadcrumb {{
            font-size: 0.875em;
            margin-bottom: 0.5em;
            color: #54595d;
        }}
        .breadcrumb a {{
            color: #0645ad;
        }}
        .breadcrumb span {{
            margin: 0 0.3em;
            color: #54595d;
        }}
        .breadcrumb span:last-of-type {{
            color: #202122;
            font-weight: 500;
        }}
        h2 {{
            margin-bottom: 0.5em;
            padding-top: 0.8em;
            padding-bottom: 0.25em;
            border-bottom: 2px solid #a7d7f9;
            font-size: 1.5em;
            font-weight: normal;
            margin-top: 1em;
            page-break-after: avoid;  /* Polish: Prevent page breaks after headings */
        }}
        h3 {{
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 0.4em;
            margin-top: 1em;
            border-bottom: 1px solid #a7d7f9;
            padding-bottom: 0.2em;
        }}
        h4 {{
            font-size: 1.05em;
            font-weight: bold;
            margin-bottom: 0.3em;
            margin-top: 0.8em;
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 0.15em;
        }}
        p {{
            margin: 0.4em 0 0.5em 0;
            line-height: 1.6;
        }}
        .mw-parser-output ul,
        .mw-parser-output ol {{
            margin: 0.3em 0 0.5em 1.6em;
            padding-left: 0.4em;
            line-height: 1.6;
        }}
        .mw-parser-output li {{
            margin: 0.25em 0;
            padding-left: 0.2em;
        }}
        table.wikitable {{
            border: 1px solid #a2a9b1;
            border-collapse: collapse;
            background-color: #f8f9fa;
            margin: 1em 0;
            width: 100%;
            max-width: 100%;
            empty-cells: show;  /* Polish: Show empty cells for clarity */
        }}
        table.wikitable th,
        table.wikitable td {{
            border: 1px solid #a2a9b1;
            padding: 0.4em 0.6em;
            word-wrap: break-word;
        }}
        table.wikitable th {{
            background-color: #eaecf0;
            text-align: center;
            font-weight: bold;
        }}
        table.wikitable th[scope="col"] {{
            /* Accessibility: scope attribute for screen readers */
        }}
        table.wikitable th[scope="row"] {{
            text-align: left;
        }}
        .infobox {{
            float: right;
            margin-top: 0.5em;
            margin-bottom: 1em;
            margin-left: 1em;
            margin-right: 0;
            width: 280px;
            clear: right;
        }}
        .infobox table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .infobox th {{
            background-color: #eaecf0;
            padding: 0.4em;
            text-align: center;
            font-weight: bold;
        }}
        .infobox td {{
            padding: 0.4em;
            border: 1px solid #a2a9b1;
        }}
        .categories {{
            margin-top: 2em;
            padding-top: 1em;
            border-top: 1px solid #a7d7f9;
            font-size: 0.875em;
            color: #54595d;
        }}
        .categories a {{
            color: #0645ad;
            margin-right: 0.5em;
        }}
        .edit-link {{
            font-size: 0.875em;
            color: #54595d;
            margin-top: 1em;
        }}
        .mw-footer {{
            grid-column: 2;
            margin-top: 0;
            margin-left: 0;
            padding: 0.75em 1.5em 0.75em 1.5em;
            border-top: 1px solid #a7d7f9;
            background-color: #f8f9fa;
            font-size: 0.75em;
            clear: both;
        }}
        .mw-footer ul {{
            list-style: none;
            margin: 0;
            padding: 0;
        }}
        .mw-footer li {{
            color: #0645ad;
            margin: 0;
            padding: 0.3em 0;
        }}
        .sff-facilities-list {{
            margin: 0.3em 0 0.5em 1.6em !important;
            padding-left: 0.4em !important;
            list-style-position: outside !important;
        }}
        .sff-facilities-list li {{
            margin: 0.3em 0 !important;
            padding-left: 0.2em !important;
        }}
        
        /* Mobile header - hidden on desktop */
        .mobile-header {{
            display: none;
        }}
        
        /* MOBILE: Stack layout */
        @media screen and (max-width: 800px) {{
            .pbjpedia-page-container {{
                grid-template-columns: 1fr;
            }}
            
            /* Mobile header - visible on mobile */
            .mobile-header {{
                display: block;
                position: sticky;
                top: 0;
                z-index: 1000;
                background-color: #f8f9fa;
                border-bottom: 1px solid #a7d7f9;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .mobile-header-content {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0.5em 1em;
                max-width: 100%;
            }}
            .mobile-logo-link {{
                display: flex;
                align-items: center;
                gap: 0.5em;
                text-decoration: none;
                color: #0645ad;
            }}
            .mobile-logo-link img {{
                display: block;
            }}
            .mobile-logo-text {{
                font-size: 0.9em;
                font-weight: bold;
            }}
            .mobile-page-title {{
                flex: 1;
                margin: 0 0.5em;
                font-size: 1em;
                font-weight: normal;
                color: #202122;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            .mobile-menu-toggle {{
                background: none;
                border: none;
                padding: 0.5em;
                cursor: pointer;
                min-width: 44px;
                min-height: 44px;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
            }}
            .mobile-menu-toggle:focus {{
                outline: 2px solid #0645ad;
                outline-offset: 2px;
            }}
            .hamburger-icon {{
                display: flex;
                flex-direction: column;
                gap: 4px;
                width: 24px;
                height: 18px;
                position: relative;
                justify-content: center;
            }}
            .hamburger-line {{
                width: 100%;
                height: 2px;
                background-color: #0645ad;
                transition: all 0.3s ease;
            }}
            body.mobile-menu-open .hamburger-icon {{
                gap: 0;
            }}
            body.mobile-menu-open .hamburger-line:nth-child(1) {{
                transform: rotate(45deg) translateY(0px);
            }}
            body.mobile-menu-open .hamburger-line:nth-child(2) {{
                opacity: 0;
            }}
            body.mobile-menu-open .hamburger-line:nth-child(3) {{
                transform: rotate(-45deg) translateY(-2px);
            }}
            
            /* Hide sidebar by default on mobile */
            #mw-navigation {{
                display: none;
                grid-column: 1;
                position: fixed;
                top: 56px;
                left: 0;
                width: 100%;
                max-width: 280px;
                height: calc(100vh - 56px);
                z-index: 1001;
                background-color: #ffffff;
                border-right: 1px solid #a7d7f9;
                overflow-y: auto;
                transform: translateX(-100%);
                transition: transform 0.3s ease;
                box-shadow: 2px 0 12px rgba(0,0,0,0.15);
                padding-top: 0;
            }}
            
            /* Show sidebar when menu is open */
            body.mobile-menu-open #mw-navigation {{
                display: block;
                transform: translateX(0);
            }}
            
            /* Simplify mobile menu - hide logo section when open */
            body.mobile-menu-open #p-logo {{
                display: none;
            }}
            
            /* Simplify mobile menu - reduce padding and spacing, ensure top is visible */
            body.mobile-menu-open #mw-panel {{
                padding: 0.8em 0.5em 1em 0.5em;
                margin-top: 0;
            }}
            
            /* Ensure first portal has enough top space */
            body.mobile-menu-open .portal:first-of-type {{
                margin-top: 0;
                padding-top: 0;
            }}
            
            /* Hide less important menu items on mobile */
            body.mobile-menu-open .portal .body li a[href="/pbjpedia/non-nursing-staff"],
            body.mobile-menu-open .portal .body li a[href="/pbjpedia/data-limitations"],
            body.mobile-menu-open .portal .body li a[href="/pbjpedia/history"] {{
                display: none;
            }}
            
            body.mobile-menu-open .portal {{
                margin: 0;
                padding-top: 0.8em;
                padding-bottom: 0.2em;
            }}
            
            body.mobile-menu-open .portal:first-of-type {{
                padding-top: 0;
            }}
            
            body.mobile-menu-open .portal:not(:first-of-type) {{
                border-top: 1px solid #d0d0d0;
                margin-top: 0;
            }}
            
            body.mobile-menu-open .portal h3 {{
                font-size: 0.75em;
                margin-bottom: 0.4em;
                padding-bottom: 0;
                border-bottom: none;
                font-weight: 500;
                color: #72777d;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                pointer-events: none;
            }}
            
            body.mobile-menu-open .portal .body li a.external-link::after {{
                content: ' ↗';
                font-size: 0.8em;
                opacity: 0.7;
            }}
            
            body.mobile-menu-open .portal .body ul {{
                padding: 0;
                margin: 0;
            }}
            
            body.mobile-menu-open .portal .body li {{
                padding: 0;
                margin: 0;
                border-bottom: 1px solid #e8e8e8;
            }}
            
            /* Remove border from last item in each section - this prevents double divider with next section */
            body.mobile-menu-open .portal .body li:last-child {{
                border-bottom: none !important;
            }}
            
            body.mobile-menu-open .portal .body li a {{
                font-size: 1em;
                padding: 0.5em 0.5em;
                border-radius: 0;
                display: block;
            }}
            
            body.mobile-menu-open .portal .body li a:hover {{
                background-color: #f0f0f0;
            }}
            
            /* Overlay when menu is open */
            body.mobile-menu-open::before {{
                content: '';
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.5);
                z-index: 998;
            }}
            
            .mw-body {{
                grid-column: 1;
                padding: 1em;
            }}
            
            .mw-footer {{
                grid-column: 1;
            }}
            
            table.wikitable {{
                font-size: 0.85em;
                display: block;
                overflow-x: auto;
            }}
            h1.firstHeading {{
                font-size: 1.5em;
                font-weight: 600;
            }}
            h2 {{
                font-size: 1.3em;
            }}
            
            /* Improve touch targets */
            .portal .body li a {{
                padding: 0.5em 0;
                display: block;
                min-height: 44px;
                display: flex;
                align-items: center;
            }}
        }}
    </style>
</head>
<body class="mediawiki ltr sitedir-ltr mw-hide-empty-elt ns-0 ns-subject page-{page_path.replace('/', '_')} skin-vector action-view">
    <div class="mobile-header">
        <div class="mobile-header-content">
            <a href="/pbjpedia/overview" class="mobile-logo-link">
                <img src="/pbj_favicon.png" alt="PBJ320" width="32" height="32">
                <span class="mobile-logo-text">PBJpedia</span>
            </a>
            <h1 class="mobile-page-title">PBJpedia: PBJ Nursing Home Staffing</h1>
            <button class="mobile-menu-toggle" aria-label="Toggle navigation menu" aria-expanded="false" aria-controls="mw-navigation">
                <span class="hamburger-icon">
                    <span class="hamburger-line"></span>
                    <span class="hamburger-line"></span>
                    <span class="hamburger-line"></span>
                </span>
            </button>
        </div>
    </div>
    <div class="pbjpedia-page-container">
        {sidebar_with_toc}
        <div class="mw-body" role="main" id="content">
            <h1 id="firstHeading" class="firstHeading"><span class="mw-headline">{title}</span></h1>
            <div class="breadcrumb noprint">
                <a href="/pbjpedia/overview">PBJpedia</a> <span>›</span> <span>{title}</span>
            </div>
            <div class="mw-parser-output">
                {content}
            </div>
            <div class="categories">
                <strong>Categories:</strong>
                <a href="/pbjpedia/overview">PBJ Data</a>
                <a href="/pbjpedia/overview">Nursing Home Staffing</a>
                <a href="/pbjpedia/overview">CMS Regulations</a>
            </div>
        </div>
        <div class="mw-footer">
        <p style="margin: 0.2em 0; line-height: 1.4;">
            Updated {get_latest_update_month_year()}.<br>
            <a href="/about">About PBJ320</a> | 
            <a href="/pbjpedia/overview">PBJpedia Overview</a> | 
            <a href="https://www.320insight.com" target="_blank">320 Consulting</a> | 
            <a href="mailto:eric@320insight.com">eric@320insight.com</a> | <a href="tel:+19298084996">(347) 992-3569</a> (text preferred)
        </p>
    </div>
    <script>
        (function() {{
            var menuToggle = document.querySelector('.mobile-menu-toggle');
            var body = document.body;
            
            if (menuToggle) {{
                menuToggle.addEventListener('click', function() {{
                    var isOpen = body.classList.contains('mobile-menu-open');
                    
                    if (isOpen) {{
                        body.classList.remove('mobile-menu-open');
                        menuToggle.setAttribute('aria-expanded', 'false');
                        body.style.overflow = '';
                    }} else {{
                        body.classList.add('mobile-menu-open');
                        menuToggle.setAttribute('aria-expanded', 'true');
                        body.style.overflow = 'hidden';
                        // Scroll menu to top when opening
                        var nav = document.querySelector('#mw-navigation');
                        if (nav) {{
                            nav.scrollTop = 0;
                        }}
                    }}
                }});
                
                // Close menu when clicking outside navigation
                document.addEventListener('click', function(e) {{
                    if (body.classList.contains('mobile-menu-open')) {{
                        var nav = document.querySelector('#mw-navigation');
                        var isClickInsideNav = nav && nav.contains(e.target);
                        var isClickOnToggle = menuToggle.contains(e.target);
                        
                        if (!isClickInsideNav && !isClickOnToggle) {{
                            // Close menu if clicking outside (on overlay or content area)
                            body.classList.remove('mobile-menu-open');
                            menuToggle.setAttribute('aria-expanded', 'false');
                            body.style.overflow = '';
                        }}
                    }}
                }});
                
                // Close menu when clicking navigation links
                var navLinks = document.querySelectorAll('#mw-navigation a');
                navLinks.forEach(function(link) {{
                    link.addEventListener('click', function() {{
                        body.classList.remove('mobile-menu-open');
                        menuToggle.setAttribute('aria-expanded', 'false');
                        body.style.overflow = '';
                    }});
                }});
                
                // Keyboard support
                menuToggle.addEventListener('keydown', function(e) {{
                    if (e.key === 'Enter' || e.key === ' ') {{
                        e.preventDefault();
                        menuToggle.click();
                    }}
                }});
            }}
        }})();
    </script>
</body>
</html>"""

# PBJpedia routes - serve markdown files as HTML
@app.route('/pbjpedia')
@app.route('/pbjpedia/')
def pbjpedia_index():
    """Redirect to PBJpedia overview page"""
    from flask import redirect
    return redirect('/pbjpedia/overview')


# Dynamic state and region pages - must come before catch-all route
# Dynamic state canonical pages - must come after specific routes but before PBJpedia routes
# This route handles /tn, /new-york, etc. and redirects aliases to canonical
@app.route('/<state_slug>')
def canonical_state_page(state_slug):
    """Canonical state page route (e.g., /tn, /new-york)"""
    # Handle JSON files first - serve them directly
    if state_slug.endswith('.json'):
        json_path = os.path.join('.', state_slug)
        if os.path.isfile(json_path):
            return send_file(json_path, mimetype='application/json')
        from flask import abort
        abort(404)
    
    # Handle image files - serve them directly
    if state_slug.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.svg')):
        image_path = os.path.join('.', state_slug)
        if os.path.isfile(image_path):
            mimetype = 'image/png' if state_slug.endswith('.png') else 'image/jpeg' if state_slug.endswith(('.jpg', '.jpeg')) else 'image/gif' if state_slug.endswith('.gif') else 'image/webp' if state_slug.endswith('.webp') else 'image/svg+xml' if state_slug.endswith('.svg') else 'image/x-icon'
            return send_file(image_path, mimetype=mimetype)
        from flask import abort
        abort(404)
    
    # Handle CSV files - serve them directly
    if state_slug.endswith('.csv'):
        csv_path = os.path.join('.', state_slug)
        if os.path.isfile(csv_path):
            return send_file(csv_path, mimetype='text/csv')
        from flask import abort
        abort(404)
    
    # Check if this is a known route first (avoid conflicts)
    known_routes = ['pbjpedia', 'wrapped', 'api', 'static', 'favicon.ico', 'robots.txt', 'sitemap.xml']
    if state_slug.lower() in known_routes:
        # Let Flask continue to next route by aborting (Flask will handle 404)
        from flask import abort
        abort(404)
    
    canonical_slug, state_code = resolve_state_slug(state_slug)
    
    if not canonical_slug or not state_code:
        return f"State '{state_slug}' not found", 404
    
    # If requested slug is not canonical, redirect
    if state_slug.lower() != canonical_slug:
        return redirect(f'/{canonical_slug}', code=301)
    
    # Generate the state page
    return generate_state_page(state_code)

@app.route('/pbjpedia/state/<state_identifier>')
def pbjpedia_state_page(state_identifier):
    """Legacy PBJpedia state page route - redirects to canonical"""
    canonical_slug, state_code = resolve_state_slug(state_identifier)
    
    if not canonical_slug or not state_code:
        return f"State '{state_identifier}' not found", 404
    
    # Redirect to canonical URL
    return redirect(f'/{canonical_slug}', code=301)

def generate_state_page(state_code):
    """Generate state page with all data - used by both canonical and legacy routes"""
    if not HAS_PANDAS:
        return "Pandas not available. Dynamic state pages require pandas.", 503
    
    state_name = STATE_CODE_TO_NAME.get(state_code, state_code)
    
    # Load data
    state_df = load_csv_data('state_quarterly_metrics.csv')
    region_mapping_df = load_csv_data('cms_region_state_mapping.csv')
    
    # Load MACPAC standards from JSON (preferred) or CSV (fallback)
    macpac_standard = None
    state_standards_json_path = 'pbj-wrapped/public/data/json/state_standards.json'
    if os.path.exists(state_standards_json_path):
        try:
            with open(state_standards_json_path, 'r', encoding='utf-8') as f:
                state_standards_json = json.load(f)
                # JSON is keyed by lowercase state code
                state_code_lower = state_code.lower()
                if state_code_lower in state_standards_json:
                    macpac_standard = state_standards_json[state_code_lower]
        except Exception as e:
            print(f"Error loading state standards JSON: {e}")
    
    # Fallback to CSV if JSON not available
    if macpac_standard is None:
        macpac_df = load_csv_data('macpac_state_standards_clean.csv')
        if macpac_df is not None and not macpac_df.empty:
            try:
                # Try matching by state name first (case-insensitive)
                macpac_row = macpac_df[macpac_df['State'].str.upper().str.strip() == state_name.upper().strip()]
                if macpac_row.empty:
                    # Try matching by state code if there's a State_Code column
                    if 'State_Code' in macpac_df.columns:
                        macpac_row = macpac_df[macpac_df['State_Code'].str.upper().str.strip() == state_code.upper().strip()]
                if not macpac_row.empty:
                    macpac_standard = macpac_row.iloc[0].to_dict()
            except Exception as e:
                print(f"Error loading MACPAC standard from CSV for {state_name}: {e}")
    
    if state_df is None:
        return "State data not available", 503
    
    # Get latest quarter data for this state
    state_data = state_df[state_df['STATE'] == state_code]
    if state_data.empty:
        return f"No data found for {state_name}", 404
    
    latest_quarter = get_latest_quarter(state_data)
    latest_data = state_data[state_data['CY_Qtr'] == latest_quarter].iloc[0] if latest_quarter else state_data.iloc[-1]
    formatted_quarter = format_quarter(latest_quarter)
    
    # Load SFF facilities for this state
    sff_facilities = load_sff_facilities()
    state_sff = [f for f in sff_facilities if f.get('state', '').upper() == state_code]
    
    # Calculate rankings for this state
    latest_all_states = state_df[state_df['CY_Qtr'] == latest_quarter] if latest_quarter else state_df
    total_states = len(latest_all_states)
    
    # Rank by Total Nurse HPRD (higher is better)
    latest_all_states_sorted = latest_all_states.sort_values('Total_Nurse_HPRD', ascending=False).reset_index(drop=True)
    state_rank_total = None
    if not latest_all_states_sorted[latest_all_states_sorted['STATE'] == state_code].empty:
        state_rank_total = latest_all_states_sorted[latest_all_states_sorted['STATE'] == state_code].index[0] + 1
    
    # Rank by RN HPRD
    latest_all_states_sorted_rn = latest_all_states.sort_values('RN_HPRD', ascending=False).reset_index(drop=True)
    state_rank_rn = None
    if not latest_all_states_sorted_rn[latest_all_states_sorted_rn['STATE'] == state_code].empty:
        state_rank_rn = latest_all_states_sorted_rn[latest_all_states_sorted_rn['STATE'] == state_code].index[0] + 1
    
    
    # Get region info
    region_info = None
    if region_mapping_df is not None:
        region_row = region_mapping_df[region_mapping_df['State_Code'] == state_code]
        if not region_row.empty:
            region_info = region_row.iloc[0]
    
    # Load state agency contact info
    state_contacts = load_state_agency_contact()
    contact_info = state_contacts.get(state_code, None)
    
    # Generate HTML content using the same template as regular pages
    html_content = generate_state_page_html(
        state_name, state_code, latest_data, macpac_standard, region_info, 
        formatted_quarter, state_rank_total, state_rank_rn, total_states, 
        state_sff, latest_quarter, contact_info
    )
    
    return html_content, 200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }

@app.route('/pbjpedia/region/<region_number>')
def pbjpedia_region_page(region_number):
    """Dynamic CMS region page with region-wide metrics and state breakdowns"""
    if not HAS_PANDAS:
        return "Pandas not available. Dynamic region pages require pandas.", 503
    
    try:
        region_num = int(region_number)
    except ValueError:
        return f"Invalid region number: {region_number}", 404
    
    # Load data
    region_df = load_csv_data('cms_region_quarterly_metrics.csv')
    state_df = load_csv_data('state_quarterly_metrics.csv')
    region_mapping_df = load_csv_data('cms_region_state_mapping.csv')
    
    if region_df is None:
        return "Region data not available", 503
    
    # Get region data
    region_data = region_df[region_df['REGION_NUMBER'] == region_num]
    if region_data.empty:
        return f"Region {region_num} not found", 404
    
    latest_quarter = get_latest_quarter(region_data)
    latest_region_data = region_data[region_data['CY_Qtr'] == latest_quarter].iloc[0] if latest_quarter else region_data.iloc[-1]
    formatted_quarter = format_quarter(latest_quarter)
    
    # Get states in this region FIRST (before using it)
    states_in_region = []
    if region_mapping_df is not None:
        region_states = region_mapping_df[region_mapping_df['CMS_Region_Number'] == region_num]
        states_in_region = region_states.to_dict('records')
    
    # Load SFF facilities for states in this region
    sff_facilities = load_sff_facilities()
    region_sff = []
    if states_in_region:
        state_codes = [s.get('State_Code', '') for s in states_in_region]
        region_sff = [f for f in sff_facilities if f.get('state', '').upper() in state_codes]
    
    # Calculate region ranking
    all_regions = region_df[region_df['CY_Qtr'] == latest_quarter] if latest_quarter else region_df
    total_regions = len(all_regions)
    all_regions_sorted = all_regions.sort_values('Total_Nurse_HPRD', ascending=False).reset_index(drop=True)
    region_rank = None
    if not all_regions_sorted[all_regions_sorted['REGION_NUMBER'] == region_num].empty:
        region_rank = all_regions_sorted[all_regions_sorted['REGION_NUMBER'] == region_num].index[0] + 1
    
    # Get state data for states in this region
    state_data_list = []
    if state_df is not None and states_in_region:
        for state_info in states_in_region:
            state_code = state_info.get('State_Code', '')
            state_data = state_df[(state_df['STATE'] == state_code) & (state_df['CY_Qtr'] == latest_quarter)]
            if not state_data.empty:
                state_data_list.append({
                    'info': state_info,
                    'data': state_data.iloc[0]
                })
    
    # Generate HTML content
    html_content = generate_region_page_html(region_num, latest_region_data, states_in_region, state_data_list, formatted_quarter, region_rank, total_regions, region_sff, latest_quarter)
    
    return html_content, 200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }

@app.route('/pbjpedia/<path:page>')
def pbjpedia_page(page):
    """Serve PBJpedia markdown files as HTML"""
    if not HAS_MARKDOWN:
        return "PBJpedia is not available. Please install markdown: pip install markdown", 503
    
    pbjpedia_dir = 'PBJPedia'
    
    # Map page names to filenames
    page_map = {
        'overview': 'pbjpedia-overview.md',
        'methodology': 'pbjpedia-methodology.md',
        'metrics': 'pbjpedia-metrics.md',
        'state-standards': 'pbjpedia-state-standards.md',
        'non-nursing-staff': 'pbjpedia-non-nursing-staff.md',
        'data-limitations': 'pbjpedia-data-limitations.md',
        'history': 'pbjpedia-history.md',
    }
    
    # Handle both with and without .md extension
    if page.endswith('.md'):
        filename = page
    else:
        filename = page_map.get(page, f'pbjpedia-{page}.md')
    
    file_path = os.path.join(pbjpedia_dir, filename)
    
    if not os.path.exists(file_path):
        from flask import abort
        abort(404)
    
    try:
        # Read markdown file
        with open(file_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        # Extract title from markdown
        title = page.replace('-', ' ').title()
        for line in md_content.split('\n'):
            if line.strip().startswith('# '):
                title = line.strip()[2:].strip()
                # Remove anchor tags if any
                title = re.sub(r'<a[^>]*></a>', '', title)
                break
        
        # Special case: overview page should use full name
        if page == 'overview':
            title = 'Payroll-Based Journal Nursing Home Staffing Data'
        
        # Convert markdown to HTML with TOC
        if markdown is None:
            return "Markdown module not available", 503
        
        # Configure markdown with TOC extension
        def slugify(value, separator='-'):
            """Create URL-friendly slug from heading text"""
            value = re.sub(r'[^\w\s-]', '', value).strip().lower()
            value = re.sub(r'[-\s]+', separator, value)
            return value
        
        md_ext = markdown.Markdown(extensions=[
            'extra',
            'codehilite', 
            'toc',
            'fenced_code',
            'tables',
            'attr_list'
        ], extension_configs={
            'toc': {
                'permalink': False,
                'baselevel': 2,
                'slugify': slugify
            }
        })
        
        html_content = md_ext.convert(md_content)
        toc = md_ext.toc if hasattr(md_ext, 'toc') and md_ext.toc else ''
        
        # Special handling for overview page - rewrite top content
        if page == 'overview':
            # Get US chart HTML first
            us_chart = generate_us_chart_html() or ""
            
            # Replace the first paragraph(s) with the new content, including chart
            new_intro = f"""<p>The <strong>Payroll-Based Journal (PBJ)</strong> is a federally mandated staffing data reporting system for U.S. nursing homes. Medicare- and Medicaid-certified long-term care facilities are required to submit daily, employee-level staffing data each quarter using payroll and timekeeping records. Facilities report hours worked for each staff member, including agency and contract staff, by job category and date. Submissions are considered timely only if received within 45 days after the end of the quarter. PBJ data are auditable and are used by the Centers for Medicare & Medicaid Services (CMS) for public reporting, enforcement activities, and research.</p>

<p>PBJ replaced earlier staffing surveys that captured staffing over a limited reporting period. The system became mandatory on July 1, 2016, and CMS began releasing public use files in 2017. PBJ is the most detailed national dataset on nursing home staffing currently available, but it reflects only paid hours and does not include information such as shift start times, wages, or clinical outcomes.</p>

{us_chart}

<h2>Why PBJ Exists</h2>

<p>Before PBJ, nursing home staffing data were collected through periodic surveys, including the CMS-671 and CMS-672 forms. These surveys typically measured staffing during a two-week period and relied on facility-reported counts. Section 6106 of the Affordable Care Act directed CMS to establish an auditable, standardized system for collecting staffing data based on payroll records. PBJ fulfills this requirement by requiring facilities to submit daily staffing data and by making public use files available for analysis by regulators, researchers, and the public.</p>"""
            
            # Find and replace the first few paragraphs and "Why PBJ Exists" section
            # Remove everything from start until after "Why PBJ Exists" section
            html_content = re.sub(
                r'^.*?<h2[^>]*>Why PBJ Exists</h2>.*?</p>',
                new_intro,
                html_content,
                flags=re.DOTALL | re.IGNORECASE
            )
        
        # AGGRESSIVELY Remove ALL H1 tags from markdown content (we use the page title instead)
        # This prevents duplicate titles - remove ALL h1 tags, no exceptions
        html_content = re.sub(r'<h1[^>]*>.*?</h1>\s*', '', html_content, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove ANY heading (h1-h6) that contains the title text
        title_escaped = re.escape(title)
        html_content = re.sub(rf'<h[1-6][^>]*>.*?{title_escaped}.*?</h[1-6]>\s*', '', html_content, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove any paragraph that contains the full title
        html_content = re.sub(rf'<p><strong>{title_escaped}</strong>.*?</p>\s*', '', html_content, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
        html_content = re.sub(rf'<p>{title_escaped}</p>\s*', '', html_content, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
        
        # Remove first element if it's the title (any tag)
        # Check if the very first element after whitespace is the title
        html_content_stripped = html_content.lstrip()
        title_patterns = [
            rf'^<h[1-6][^>]*>.*?{re.escape(title)}.*?</h[1-6]>',
            rf'^<p><strong>.*?{re.escape(title)}.*?</strong>.*?</p>',
            rf'^<p>.*?{re.escape(title)}.*?</p>'
        ]
        for pattern in title_patterns:
            html_content = re.sub(pattern, '', html_content, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
        
        # Ensure all headings have IDs for section jumping and TOC
        # Add IDs to any headings that don't have them
        heading_pattern = r'<h([2-4])([^>]*)>(.*?)</h[2-4]>'
        def add_id_if_missing(match):
            level = match.group(1)
            attrs = match.group(2)
            text = match.group(3)
            text_clean = re.sub(r'<[^>]+>', '', text).strip()
            
            if 'id=' not in attrs:
                anchor = slugify(text_clean)
                return f'<h{level}{attrs} id="{anchor}">{text}</h{level}>'
            return match.group(0)
        
        html_content = re.sub(heading_pattern, add_id_if_missing, html_content)
        
        # Now extract headings for TOC (after IDs are added)
        headings_for_toc = re.findall(r'<h([2-4])[^>]*id="([^"]*)"[^>]*>(.*?)</h[2-4]>', html_content)
        
        # Convert markdown links to pbjpedia URLs
        # Replace ./pbjpedia-*.md links with /pbjpedia/* URLs
        html_content = re.sub(
            r'href="\./pbjpedia-([^"]+)\.md"',
            lambda m: f'href="/pbjpedia/{m.group(1)}"',
            html_content
        )
        # Also handle links without ./
        html_content = re.sub(
            r'href="pbjpedia-([^"]+)\.md"',
            lambda m: f'href="/pbjpedia/{m.group(1)}"',
            html_content
        )
        
        # Stub notices removed per user request
        
        # Improve reference formatting
        # Wrap references section in proper div if it exists
        if re.search(r'<h2[^>]*>References</h2>', html_content, re.IGNORECASE):
            # Find the References heading and wrap content until next h2 or end
            html_content = re.sub(
                r'(<h2[^>]*>References</h2>)(.*?)(?=<h2|</div>|$)',
                r'<div class="references">\1\2</div>',
                html_content,
                flags=re.IGNORECASE | re.DOTALL
            )
        
        # Generate table of contents from headings
        toc_html = ''
        # First try to use markdown TOC extension output
        if toc and '<ul' in toc:
            # Extract just the UL element for sidebar
            toc_match = re.search(r'<ul[^>]*>.*?</ul>', toc, re.DOTALL)
            if toc_match:
                toc_html = toc_match.group(0)  # Full UL element
            else:
                toc_html = toc
        
        # If no TOC from extension, generate manually from headings we just extracted
        if not toc_html:
            if headings_for_toc:
                headings = headings_for_toc
            else:
                # Fallback: extract headings again if headings_for_toc is empty
                headings = re.findall(r'<h([2-4])[^>]*id="([^"]*)"[^>]*>(.*?)</h[2-4]>', html_content)
            
            if headings:
                toc_items = []
                prev_level = 2
                counters = {2: 0, 3: 0, 4: 0}
                
                for level, anchor, text in headings:
                    level_int = int(level)
                    # Clean text from HTML tags
                    text_clean = re.sub(r'<[^>]+>', '', text).strip()
                    
                    # Reset lower level counters when going up a level
                    if level_int < prev_level:
                        for l in range(level_int + 1, 5):
                            counters[l] = 0
                    
                    # Increment counter for this level
                    counters[level_int] += 1
                    
                    # Build number string (e.g., "1.2.3")
                    number_parts = []
                    for l in range(2, level_int + 1):
                        number_parts.append(str(counters[l]))
                    number_str = '.'.join(number_parts)
                    
                    # Handle nested lists
                    if level_int > prev_level:
                        # Open new nested ul
                        for _ in range(prev_level, level_int):
                            toc_items.append('<ul>')
                    elif level_int < prev_level:
                        # Close nested uls
                        for _ in range(level_int, prev_level):
                            toc_items.append('</li></ul>')
                        toc_items.append('</li>')
                    elif prev_level == level_int and toc_items:
                        # Same level, close previous item
                        toc_items.append('</li>')
                    
                    toc_items.append(f'<li class="toclevel-{level_int}"><a href="#{anchor}"><span class="tocnumber">{number_str}</span> <span class="toctext">{text_clean}</span></a>')
                    prev_level = level_int
                
                # Close any remaining open tags
                if toc_items:
                    toc_items.append('</li>')
                    for _ in range(2, prev_level):
                        toc_items.append('</ul>')
                    
                    toc_html = f'<ul>{"".join(toc_items)}</ul>'
        
        # Generate sidebar navigation
        sidebar_nav = get_pbjpedia_sidebar()
        
        # Move TOC to sidebar if it exists
        sidebar_with_toc = sidebar_nav
        if toc_html and toc_html.strip():
            # Extract UL content - handle both full UL or just content
            toc_match = re.search(r'<ul[^>]*>(.*?)</ul>', toc_html, re.DOTALL)
            if toc_match:
                toc_ul_content = toc_match.group(1)
                toc_in_sidebar = f'<div class="portal" role="navigation" id="p-toc"><h3>Contents</h3><div class="body"><ul>{toc_ul_content}</ul></div></div>'
            elif toc_html.strip().startswith('<ul'):
                # Already a full UL, wrap it
                toc_in_sidebar = f'<div class="portal" role="navigation" id="p-toc"><h3>Contents</h3><div class="body">{toc_html}</div></div>'
            else:
                toc_in_sidebar = None
            
            # TOC removed from sidebar per user request
            # if toc_in_sidebar and page != 'overview':
            #     ... (code disabled)
        
        # Wikipedia-style HTML template with rigid CSS Grid
        html_page = f"""<!DOCTYPE html>
<html lang="en" dir="ltr" class="client-nojs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="/pbj_favicon.png">
    <title>{title} - PBJpedia | PBJ320</title>
    <meta name="description" content="Learn about {title} in PBJpedia, the comprehensive reference guide for Payroll-Based Journal nursing home staffing data.">
    <link rel="canonical" href="https://pbj320.com/pbjpedia/{page}">
    <style>
        /* HARD RESET: Rigid CSS Grid Layout - No Floating, No Absolute Positioning */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Liberation Sans', sans-serif;
            font-size: 0.875em;
            line-height: 1.6;
            color: #202122;
            background-color: #f8f9fa;
        }}
        
        /* PAGE GRID: Sidebar | Article */
        .pbjpedia-page-container {{
            display: grid;
            grid-template-columns: 10em 1fr;
            min-height: 100vh;
        }}
        
        /* LEFT SIDEBAR - Fixed width, no floating */
        #mw-navigation {{
            grid-column: 1;
            background-color: #f8f9fa;
            border-right: 1px solid #a7d7f9;
            padding: 0.5em;
            font-size: 0.875em;
            position: sticky;
            top: 0;
            height: 100vh;
            overflow-y: auto;
        }}
        #mw-panel {{
            display: flex;
            flex-direction: column;
            gap: 0.5em;
        }}
        #p-logo {{
            margin-bottom: 0.5em;
        }}
        #p-logo a {{
            display: block;
            text-decoration: none;
            padding: 0.3em 0.2em;
            text-align: center;
        }}
        #p-logo img {{
            max-width: 50px;
            max-height: 50px;
            margin: 0 auto 0.1em;
            display: block;
        }}
        #p-logo > a > div > div:first-of-type {{
            font-size: 0.9em;
            font-weight: bold;
            color: #0645ad;
            margin-top: 0;
        }}
        .portal {{
            margin: 0.5em 0;
        }}
        .portal h3 {{
            font-size: 0.75em;
            color: #72777d;
            font-weight: 500;
            margin: 0 0 0.3em 0.7em;
            padding: 0.25em 0;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            pointer-events: none;
        }}
        .portal .body li a.external-link::after {{
            content: ' ↗';
            font-size: 0.8em;
            opacity: 0.7;
        }}
        .portal .body ul {{
            list-style: none;
            margin: 0;
            padding: 0.3em 0 0 0;
        }}
        .portal .body li {{
            line-height: 1.125em;
            margin: 0;
            padding: 0.25em 0;
            font-size: 0.85em;
        }}
        .portal .body li a {{
            color: #0645ad;
            text-decoration: none;
        }}
        .portal .body li a:hover {{
            text-decoration: underline;
        }}
        /* TOC in sidebar - Wikipedia style, larger and at top */
        #p-toc {{
            margin-bottom: 1em;
        }}
        #p-toc h3 {{
            font-size: 0.875em;
            font-weight: bold;
            color: #202122;
            margin: 0 0 0.3em 0.7em;
            padding: 0.25em 0;
            border-bottom: 1px solid #a7d7f9;
        }}
        #p-toc .body ul {{
            list-style: none;
            margin: 0;
            padding-left: 0.5em;
        }}
        #p-toc .body li {{
            font-size: 0.875em;
            line-height: 1.4;
            margin: 0.2em 0;
        }}
        #p-toc .body li a {{
            color: #0645ad;
        }}
        #mw-navigation h2 {{
            display: none;
        }}
        
        /* MAIN ARTICLE COLUMN */
        .mw-body {{
            grid-column: 2;
            background-color: #ffffff;
            border: 1px solid #a7d7f9;
            border-left: none;
            padding: 1em 1.5em;
            max-width: 100%;
            overflow-x: hidden;
        }}
        h1.firstHeading {{
            border-bottom: 1px solid #a7d7f9;
            padding-bottom: 0.25em;
            margin-bottom: 0.3em;
            font-size: 1.8em;
            font-weight: 600;
            margin-top: 0;
        }}
        #siteSub {{
            font-size: 0.9em;
            color: #202122;
            margin-bottom: 0.5em;
            font-weight: 500;
        }}
        .breadcrumb {{
            font-size: 0.875em;
            margin-bottom: 0.5em;
            color: #54595d;
        }}
        .breadcrumb a {{
            color: #0645ad;
        }}
        .breadcrumb span {{
            margin: 0 0.3em;
            color: #54595d;
        }}
        .breadcrumb span:last-of-type {{
            color: #202122;
            font-weight: 500;
        }}
        h2 {{
            margin-bottom: 0.5em;
            padding-top: 0.8em;
            padding-bottom: 0.25em;
            border-bottom: 2px solid #a7d7f9;
            font-size: 1.5em;
            font-weight: normal;
            line-height: 1.4;
            margin-top: 1em;
            clear: both;
        }}
        h3 {{
            font-size: 1.2em;
            font-weight: bold;
            line-height: 1.4;
            margin-bottom: 0.4em;
            margin-top: 1em;
            border-bottom: 1px solid #a7d7f9;
            padding-bottom: 0.2em;
        }}
        h4 {{
            font-size: 1.05em;
            font-weight: bold;
            margin-bottom: 0.3em;
            margin-top: 0.8em;
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 0.15em;
        }}
        p {{
            margin: 0.4em 0 0.5em 0;
            line-height: 1.6;
        }}
        /* List styling - proper indentation - IMPORTANT: Override any markdown defaults */
        .mw-parser-output ul,
        .mw-parser-output ol,
        ul:not(.portal .body ul):not(.toc ul):not(.mw-footer ul):not(.sff-facilities-list),
        ol:not(.portal .body ol):not(.toc ol):not(.mw-footer ol) {{
            margin: 0.3em 0 0.5em 1.6em !important;
            padding-left: 0.4em !important;
            line-height: 1.6;
            list-style-position: outside;
        }}
        .sff-facilities-list {{
            margin: 0.3em 0 0.5em 1.6em !important;
            padding-left: 0.4em !important;
            list-style-position: outside !important;
        }}
        .sff-facilities-list li {{
            margin: 0.3em 0 !important;
            padding-left: 0.2em !important;
        }}
        .mw-parser-output li,
        li:not(.portal .body li):not(.toc li):not(.mw-footer li) {{
            margin: 0.25em 0 !important;
            padding-left: 0.2em !important;
        }}
        .mw-parser-output ul ul,
        .mw-parser-output ol ol,
        .mw-parser-output ul ol,
        .mw-parser-output ol ul,
        ul ul:not(.portal .body ul):not(.toc ul),
        ol ol:not(.portal .body ol):not(.toc ol) {{
            margin: 0.2em 0 0.2em 1.2em !important;
        }}
        a {{
            color: #0645ad;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        a:visited {{
            color: #0b0080;
        }}
        /* Keyboard navigation improvements */
        a:focus,
        button:focus {{
            outline: 2px solid #0645ad;
            outline-offset: 2px;
        }}
        /* Skip to content link for accessibility */
        .skip-to-content {{
            position: absolute;
            left: -9999px;
            z-index: 999;
        }}
        .skip-to-content:focus {{
            left: 1em;
            top: 1em;
            background: #0645ad;
            color: white;
            padding: 0.5em 1em;
            text-decoration: none;
            border-radius: 3px;
        }}
        /* Back to top link */
        .back-to-top {{
            display: block;
            text-align: center;
            margin: 2em 0 1em;
            padding: 0.5em;
            font-size: 0.9em;
        }}
        .back-to-top a {{
            color: #0645ad;
            text-decoration: none;
        }}
        .back-to-top a:hover {{
            text-decoration: underline;
        }}
        /* Smooth scroll behavior */
        html {{
            scroll-behavior: smooth;
        }}
        /* Print stylesheet */
        @media print {{
            .pbjpedia-page-container {{
                grid-template-columns: 1fr;
            }}
            #mw-navigation,
            .breadcrumb,
            .categories,
            .edit-link,
            .back-to-top,
            .mw-footer {{
                display: none;
            }}
            .mw-body {{
                border: none;
                padding: 0;
            }}
            a {{
                color: #000;
                text-decoration: underline;
            }}
            a[href^="http"]:after {{
                content: " (" attr(href) ")";
                font-size: 0.8em;
            }}
        }}
        /* TOC removed from article - now in sidebar */
        .toctitle {{
            text-align: center;
            direction: ltr;
        }}
        .toctitle h2 {{
            display: inline;
            border: 0;
            padding: 0;
            font-size: 100%;
            font-weight: bold;
            margin: 0;
        }}
        .toc ul {{
            list-style-type: none;
            list-style-image: none;
            margin-left: 0;
            padding-left: 0;
            text-align: left;
        }}
        .toc ul ul {{
            margin: 0 0 0 2em;
        }}
        .toc li {{
            list-style: none;
            margin: 0;
            padding: 0;
        }}
        .toc a {{
            display: block;
            padding: 0.1em 0;
        }}
        .tocnumber {{
            color: #222;
            padding-right: 0.5em;
        }}
        .toctext {{
            color: #0645ad;
        }}
        table {{
            border: 1px solid #a2a9b1;
            border-collapse: collapse;
            background-color: #f8f9fa;
            color: black;
            margin: 1em 0;
            font-size: 100%;
        }}
        table.wikitable > tr > th,
        table.wikitable > tr > td,
        table.wikitable > * > tr > th,
        table.wikitable > * > tr > td {{
            border: 1px solid #a2a9b1;
            padding: 0.2em 0.4em;
        }}
        table.wikitable > tr > th,
        table.wikitable > * > tr > th {{
            background-color: #eaecf0;
            text-align: center;
            font-weight: bold;
        }}
        code {{
            background-color: #eaecf0;
            border: 1px solid #c8ccd1;
            border-radius: 2px;
            padding: 1px 4px;
            font-family: 'Courier New', 'Courier', monospace;
        }}
        pre {{
            padding: 1em;
            border: 1px solid #c8ccd1;
            background-color: #f8f9fa;
            overflow-x: auto;
        }}
        .mw-footer {{
            grid-column: 2;
            margin-top: 0;
            margin-left: 0;
            padding: 0.75em 1.5em 0.75em 1.5em;
            border-top: 1px solid #a7d7f9;
            background-color: #f8f9fa;
            font-size: 0.75em;
            clear: both;
        }}
        .mw-footer ul {{
            list-style: none;
            margin: 0;
            padding: 0;
        }}
        .mw-footer li {{
            color: #0645ad;
            margin: 0;
            padding: 0.3em 0;
        }}
        .mw-footer p {{
            margin: 0.2em 0;
            line-height: 1.4;
        }}
        .infobox {{
            border: 1px solid #a7d7f9;
            border-spacing: 3px;
            background-color: #f8f9fa;
            color: black;
            margin-top: 0.5em;
            margin-bottom: 1em;
            margin-left: 1em;
            margin-right: 0;
            padding: 0.2em;
            float: right;
            clear: right;
            font-size: 88%;
            line-height: 1.5em;
            width: 22em;
        }}
        .breadcrumb {{
            font-size: 0.875em;
            margin-bottom: 0.5em;
            color: #54595d;
        }}
        .breadcrumb a {{
            color: #0645ad;
        }}
        .breadcrumb span {{
            margin: 0 0.3em;
            color: #54595d;
        }}
        .breadcrumb span:last-of-type {{
            color: #202122;
            font-weight: 500;
        }}
        .stub {{
            background-color: #fef6e7;
            border: 1px solid #fc3;
            padding: 0.5em;
            margin: 1em 0;
            font-size: 0.9em;
        }}
        .stub strong {{
            color: #d97706;
        }}
        .categories {{
            margin-top: 2em;
            padding-top: 1em;
            border-top: 1px solid #a7d7f9;
            font-size: 0.875em;
            color: #54595d;
        }}
        .categories a {{
            color: #0645ad;
            margin-right: 0.5em;
        }}
        .references {{
            font-size: 0.9em;
        }}
        .references ol {{
            margin: 0.5em 0;
            padding-left: 2em;
        }}
        .references li {{
            margin: 0.3em 0;
        }}
        
        /* Mobile header - hidden on desktop */
        .mobile-header {{
            display: none;
        }}
        
        /* MOBILE: Stack layout */
        @media screen and (max-width: 800px) {{
            .pbjpedia-page-container {{
                grid-template-columns: 1fr;
            }}
            
            /* Mobile header - visible on mobile */
            .mobile-header {{
                display: block;
                position: sticky;
                top: 0;
                z-index: 1000;
                background-color: #f8f9fa;
                border-bottom: 1px solid #a7d7f9;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .mobile-header-content {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0.5em 1em;
                max-width: 100%;
            }}
            .mobile-logo-link {{
                display: flex;
                align-items: center;
                gap: 0.5em;
                text-decoration: none;
                color: #0645ad;
            }}
            .mobile-logo-link img {{
                display: block;
            }}
            .mobile-logo-text {{
                font-size: 0.9em;
                font-weight: bold;
            }}
            .mobile-page-title {{
                flex: 1;
                margin: 0 0.5em;
                font-size: 1em;
                font-weight: normal;
                color: #202122;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            .mobile-menu-toggle {{
                background: none;
                border: none;
                padding: 0.5em;
                cursor: pointer;
                min-width: 44px;
                min-height: 44px;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
            }}
            .mobile-menu-toggle:focus {{
                outline: 2px solid #0645ad;
                outline-offset: 2px;
            }}
            .hamburger-icon {{
                display: flex;
                flex-direction: column;
                gap: 4px;
                width: 24px;
                height: 18px;
                position: relative;
                justify-content: center;
            }}
            .hamburger-line {{
                width: 100%;
                height: 2px;
                background-color: #0645ad;
                transition: all 0.3s ease;
            }}
            body.mobile-menu-open .hamburger-icon {{
                gap: 0;
            }}
            body.mobile-menu-open .hamburger-line:nth-child(1) {{
                transform: rotate(45deg) translateY(0px);
            }}
            body.mobile-menu-open .hamburger-line:nth-child(2) {{
                opacity: 0;
            }}
            body.mobile-menu-open .hamburger-line:nth-child(3) {{
                transform: rotate(-45deg) translateY(-2px);
            }}
            
            /* Hide sidebar by default on mobile */
            #mw-navigation {{
                display: none;
                grid-column: 1;
                position: fixed;
                top: 56px;
                left: 0;
                width: 100%;
                max-width: 280px;
                height: calc(100vh - 56px);
                z-index: 1001;
                background-color: #ffffff;
                border-right: 1px solid #a7d7f9;
                overflow-y: auto;
                transform: translateX(-100%);
                transition: transform 0.3s ease;
                box-shadow: 2px 0 12px rgba(0,0,0,0.15);
                padding-top: 0;
            }}
            
            /* Show sidebar when menu is open */
            body.mobile-menu-open #mw-navigation {{
                display: block;
                transform: translateX(0);
            }}
            
            /* Simplify mobile menu - hide logo section when open */
            body.mobile-menu-open #p-logo {{
                display: none;
            }}
            
            /* Simplify mobile menu - reduce padding and spacing, ensure top is visible */
            body.mobile-menu-open #mw-panel {{
                padding: 0.8em 0.5em 1em 0.5em;
                margin-top: 0;
            }}
            
            /* Ensure first portal has enough top space */
            body.mobile-menu-open .portal:first-of-type {{
                margin-top: 0;
                padding-top: 0;
            }}
            
            /* Hide less important menu items on mobile */
            body.mobile-menu-open .portal .body li a[href="/pbjpedia/non-nursing-staff"],
            body.mobile-menu-open .portal .body li a[href="/pbjpedia/data-limitations"],
            body.mobile-menu-open .portal .body li a[href="/pbjpedia/history"] {{
                display: none;
            }}
            
            body.mobile-menu-open .portal {{
                margin: 0;
                padding-top: 0.8em;
                padding-bottom: 0.2em;
            }}
            
            body.mobile-menu-open .portal:first-of-type {{
                padding-top: 0;
            }}
            
            body.mobile-menu-open .portal:not(:first-of-type) {{
                border-top: 1px solid #d0d0d0;
                margin-top: 0;
            }}
            
            body.mobile-menu-open .portal h3 {{
                font-size: 0.75em;
                margin-bottom: 0.4em;
                padding-bottom: 0;
                border-bottom: none;
                font-weight: 500;
                color: #72777d;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                pointer-events: none;
            }}
            
            body.mobile-menu-open .portal .body li a.external-link::after {{
                content: ' ↗';
                font-size: 0.8em;
                opacity: 0.7;
            }}
            
            body.mobile-menu-open .portal .body ul {{
                padding: 0;
                margin: 0;
            }}
            
            body.mobile-menu-open .portal .body li {{
                padding: 0;
                margin: 0;
                border-bottom: 1px solid #e8e8e8;
            }}
            
            /* Remove border from last item in each section - this prevents double divider with next section */
            body.mobile-menu-open .portal .body li:last-child {{
                border-bottom: none !important;
            }}
            
            body.mobile-menu-open .portal .body li a {{
                font-size: 1em;
                padding: 0.5em 0.5em;
                border-radius: 0;
                display: block;
            }}
            
            body.mobile-menu-open .portal .body li a:hover {{
                background-color: #f0f0f0;
            }}
            
            /* Overlay when menu is open */
            body.mobile-menu-open::before {{
                content: '';
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.5);
                z-index: 998;
            }}
            
            .mw-body {{
                grid-column: 1;
                padding: 1em;
            }}
            
            .mw-footer {{
                grid-column: 1;
            }}
            
            table.wikitable {{
                font-size: 0.85em;
                display: block;
                overflow-x: auto;
            }}
            h1.firstHeading {{
                font-size: 1.5em;
                font-weight: 600;
            }}
            h2 {{
                font-size: 1.3em;
            }}
            
            /* Improve touch targets */
            .portal .body li a {{
                padding: 0.5em 0;
                display: block;
                min-height: 44px;
                display: flex;
                align-items: center;
            }}
        }}
        /* Readability improvements */
        .mw-parser-output {{
            max-width: 100%;
            word-wrap: break-word;
        }}
        table.wikitable {{
            width: 100%;
            max-width: 100%;
            table-layout: auto;
        }}
        table.wikitable th, table.wikitable td {{
            word-wrap: break-word;
            hyphens: auto;
        }}
        /* Better spacing for content sections */
        .mw-parser-output > * {{
            margin-bottom: 0.8em;
        }}
        .mw-parser-output > h2:first-child {{
            margin-top: 0;
        }}
        /* Improve external link visibility */
        a[href^="http"]:not([href*="pbj320.com"]):not([href*="pbjdashboard.com"]) {{
            /* External links - could add icon if desired */
        }}
        /* Improve definition lists if used */
        dl {{
            margin: 0.5em 0;
        }}
        dt {{
            font-weight: bold;
            margin-top: 0.5em;
        }}
        dd {{
            margin-left: 1.5em;
            margin-bottom: 0.5em;
        }}
    </style>
</head>
<body class="mediawiki ltr sitedir-ltr mw-hide-empty-elt ns-0 ns-subject page-{page.replace('-', '_')} rootpage-{page.replace('-', '_')} skin-vector action-view">
    <div class="mobile-header">
        <div class="mobile-header-content">
            <a href="/pbjpedia/overview" class="mobile-logo-link">
                <img src="/pbj_favicon.png" alt="PBJ320" width="32" height="32">
                <span class="mobile-logo-text">PBJpedia</span>
            </a>
            <button class="mobile-menu-toggle" aria-label="Toggle navigation menu" aria-expanded="false" aria-controls="mw-navigation">
                <span class="hamburger-icon">
                    <span class="hamburger-line"></span>
                    <span class="hamburger-line"></span>
                    <span class="hamburger-line"></span>
                </span>
            </button>
        </div>
    </div>
    <div class="pbjpedia-page-container">
        {sidebar_with_toc}
        <div class="mw-body" role="main" id="content">
            <h1 id="firstHeading" class="firstHeading"><span class="mw-headline">{title}</span></h1>
            <div class="breadcrumb noprint">
                <a href="/pbjpedia/overview">PBJpedia</a> <span>›</span> <span>{title}</span>
            </div>
            <div class="mw-parser-output">
                {html_content}
            </div>
            <div style="background-color: #f8f9fa; border: 1px solid #a7d7f9; border-radius: 4px; padding: 1.5em; margin: 2em 0;">
                <h3 style="margin-top: 0; font-size: 1.1em;">Custom PBJ Analysis for Attorneys & Journalists</h3>
                <p>320 Consulting offers custom reports and dashboards with daily, position-level analysis and data visualizations tied to ratings, enforcement, and other critical metrics to support your casework and advocacy. Check out a <a href="https://pbj320-395258.vercel.app/" target="_blank" rel="noopener">sample dashboard</a>.</p>
                <p><strong>Contact:</strong> <a href="mailto:eric@320insight.com">eric@320insight.com</a> | <a href="tel:+19298084996">(347) 992-3569</a> (text preferred)</p>
                <p style="margin-bottom: 0;"><strong>Journalists:</strong> If you're working on a story, I'm happy to share data or walk you through it.</p>
            </div>
            <div class="categories">
                <strong>Categories:</strong>
                <a href="/pbjpedia/overview">PBJ Data</a>
                <a href="/pbjpedia/overview">Nursing Home Staffing</a>
                <a href="/pbjpedia/overview">CMS Regulations</a>
            </div>
        </div>
        <div class="mw-footer">
        <p style="margin: 0.2em 0; line-height: 1.4;">
            Updated {get_latest_update_month_year()}.<br>
            <a href="/about">About PBJ320</a> | 
            <a href="/pbjpedia/overview">PBJpedia Overview</a> | 
            <a href="https://www.320insight.com" target="_blank">320 Consulting</a> | 
            <a href="mailto:eric@320insight.com">eric@320insight.com</a> | <a href="tel:+19298084996">(347) 992-3569</a> (text preferred)
        </p>
    </div>
    <script>
        (function() {{
            var menuToggle = document.querySelector('.mobile-menu-toggle');
            var body = document.body;
            
            if (menuToggle) {{
                menuToggle.addEventListener('click', function() {{
                    var isOpen = body.classList.contains('mobile-menu-open');
                    
                    if (isOpen) {{
                        body.classList.remove('mobile-menu-open');
                        menuToggle.setAttribute('aria-expanded', 'false');
                        body.style.overflow = '';
                    }} else {{
                        body.classList.add('mobile-menu-open');
                        menuToggle.setAttribute('aria-expanded', 'true');
                        body.style.overflow = 'hidden';
                        // Scroll menu to top when opening
                        var nav = document.querySelector('#mw-navigation');
                        if (nav) {{
                            nav.scrollTop = 0;
                        }}
                    }}
                }});
                
                // Close menu when clicking outside navigation
                document.addEventListener('click', function(e) {{
                    if (body.classList.contains('mobile-menu-open')) {{
                        var nav = document.querySelector('#mw-navigation');
                        var isClickInsideNav = nav && nav.contains(e.target);
                        var isClickOnToggle = menuToggle.contains(e.target);
                        
                        if (!isClickInsideNav && !isClickOnToggle) {{
                            // Close menu if clicking outside (on overlay or content area)
                            body.classList.remove('mobile-menu-open');
                            menuToggle.setAttribute('aria-expanded', 'false');
                            body.style.overflow = '';
                        }}
                    }}
                }});
                
                // Close menu when clicking navigation links
                var navLinks = document.querySelectorAll('#mw-navigation a');
                navLinks.forEach(function(link) {{
                    link.addEventListener('click', function() {{
                        body.classList.remove('mobile-menu-open');
                        menuToggle.setAttribute('aria-expanded', 'false');
                        body.style.overflow = '';
                    }});
                }});
                
                // Keyboard support
                menuToggle.addEventListener('keydown', function(e) {{
                    if (e.key === 'Enter' || e.key === ' ') {{
                        e.preventDefault();
                        menuToggle.click();
                    }}
                }});
            }}
        }})();
    </script>
</body>
</html>"""
        
        return html_page, 200, {
            'Content-Type': 'text/html; charset=utf-8',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    
    except Exception as e:
        return f"Error rendering page: {str(e)}", 500

# Serve favicon with no-cache headers
@app.route('/favicon.ico')
def favicon():
    """Serve favicon with no-cache headers to ensure updates are visible"""
    favicon_path = 'pbj_favicon.png'
    if os.path.exists(favicon_path):
        response = send_file(favicon_path, mimetype='image/png')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    # Fallback to favicon.ico if it exists
    if os.path.exists('favicon.ico'):
        response = send_file('favicon.ico', mimetype='image/x-icon')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    from flask import abort
    abort(404)

# Serve pbj_favicon.png with no-cache headers
@app.route('/pbj_favicon.png')
def pbj_favicon():
    """Serve pbj_favicon.png with no-cache headers"""
    favicon_path = 'pbj_favicon.png'
    if os.path.exists(favicon_path):
        response = send_file(favicon_path, mimetype='image/png')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    from flask import abort
    abort(404)

# Serve images from pbj-wrapped/dist/images (for SEO meta tags)
# This route MUST come before the catch-all route to work correctly
@app.route('/images/<path:filename>')
def images_files(filename):
    """Serve image files from pbj-wrapped/dist/images directory"""
    images_dir = os.path.join('pbj-wrapped', 'dist', 'images')
    file_path = os.path.join(images_dir, filename)
    
    if os.path.isfile(file_path):
        # Serve with proper MIME type
        return send_file(file_path, mimetype='image/png')
    else:
        # Fallback to root directory for backward compatibility
        root_file = os.path.join('.', filename)
        if os.path.isfile(root_file) and filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            return send_file(root_file, mimetype='image/png')
        from flask import abort
        abort(404)

# Serve data files from pbj-wrapped/dist/data
# This route MUST come before the catch-all route to work correctly
@app.route('/data', defaults={'path': ''})
@app.route('/data/', defaults={'path': ''})
@app.route('/data/<path:path>')
def data_files(path):
    """Serve data files from pbj-wrapped/dist/data directory"""
    data_dir = os.path.join('pbj-wrapped', 'dist', 'data')
    file_path = os.path.join(data_dir, path)
    
    if os.path.isfile(file_path):
        # Serve with proper MIME types
        if path.endswith('.json'):
            return send_file(file_path, mimetype='application/json')
        elif path.endswith('.csv'):
            return send_file(file_path, mimetype='text/csv')
        else:
            return send_from_directory(data_dir, path)
    else:
        from flask import abort
        abort(404)

# Serve SFF routes at /sff (for pbj320.com/sff/)
@app.route('/sff')
@app.route('/sff/')
def sff_index():
    """Serve the wrapped React app index page for SFF routes with server-rendered SEO metadata"""
    seo = get_seo_metadata(request.path)
    assets = get_built_assets()
    try:
        return render_template('wrapped_index.html', seo=seo, assets=assets)
    except Exception as e:
        # Fallback to static file if template rendering fails
        print(f"Warning: Template rendering failed: {e}, falling back to static file")
    wrapped_index = os.path.join('pbj-wrapped', 'dist', 'index.html')
    if os.path.exists(wrapped_index):
        return send_file(wrapped_index, mimetype='text/html')
    else:
        return "PBJ Wrapped app not built. Run 'npm run build' in pbj-wrapped directory.", 404

@app.route('/sff/<path:path>')
def sff_static(path):
    """Serve static files and handle SPA routing for SFF"""
    wrapped_dist = os.path.join('pbj-wrapped', 'dist')
    
    # Check if it's a static asset (has extension)
    file_path = os.path.join(wrapped_dist, path)
    if os.path.isfile(file_path):
        # Serve the static file with proper MIME types
        if path.endswith('.js'):
            return send_file(file_path, mimetype='application/javascript')
        elif path.endswith('.css'):
            return send_file(file_path, mimetype='text/css')
        elif path.endswith('.json'):
            return send_file(file_path, mimetype='application/json')
        elif path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.woff', '.woff2', '.ttf', '.eot')):
            return send_file(file_path)
        else:
            return send_from_directory(wrapped_dist, path)
    else:
        # For SPA routing, serve index.html for any route with server-rendered SEO metadata
        # This allows React Router to handle client-side routing
        seo = get_seo_metadata(request.path)
        assets = get_built_assets()
        try:
            return render_template('wrapped_index.html', seo=seo, assets=assets)
        except Exception as e:
            # Fallback to static file if template rendering fails
            print(f"Warning: Template rendering failed: {e}, falling back to static file")
        wrapped_index = os.path.join(wrapped_dist, 'index.html')
        if os.path.exists(wrapped_index):
            return send_file(wrapped_index, mimetype='text/html')
        else:
            return "PBJ Wrapped app not built. Run 'npm run build' in pbj-wrapped directory.", 404

# Serve wrapped app at /wrapped (for pbj320.com/wrapped/)
@app.route('/wrapped')
@app.route('/wrapped/')
def wrapped_index():
    """Serve the wrapped React app index page with server-rendered SEO metadata"""
    seo = get_seo_metadata(request.path)
    assets = get_built_assets()
    try:
        return render_template('wrapped_index.html', seo=seo, assets=assets)
    except Exception as e:
        # Fallback to static file if template rendering fails
        print(f"Warning: Template rendering failed: {e}, falling back to static file")
    wrapped_index = os.path.join('pbj-wrapped', 'dist', 'index.html')
    if os.path.exists(wrapped_index):
        return send_file(wrapped_index, mimetype='text/html')
    else:
        return "PBJ Wrapped app not built. Run 'npm run build' in pbj-wrapped directory.", 404

@app.route('/wrapped/<path:path>')
def wrapped_static(path):
    """Serve static files and handle SPA routing for wrapped"""
    wrapped_dist = os.path.join('pbj-wrapped', 'dist')
    
    # Check if it's a static asset (has extension)
    file_path = os.path.join(wrapped_dist, path)
    if os.path.isfile(file_path):
        # Serve the static file with proper MIME types
        if path.endswith('.js'):
            return send_file(file_path, mimetype='application/javascript')
        elif path.endswith('.css'):
            return send_file(file_path, mimetype='text/css')
        elif path.endswith('.json'):
            return send_file(file_path, mimetype='application/json')
        elif path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.woff', '.woff2', '.ttf', '.eot')):
            return send_file(file_path)
        else:
            return send_from_directory(wrapped_dist, path)
    else:
        # For SPA routing, serve index.html for any route with server-rendered SEO metadata
        # This allows React Router to handle client-side routing
        seo = get_seo_metadata(request.path)
        assets = get_built_assets()
        try:
            return render_template('wrapped_index.html', seo=seo, assets=assets)
        except Exception as e:
            # Fallback to static file if template rendering fails
            print(f"Warning: Template rendering failed: {e}, falling back to static file")
        wrapped_index = os.path.join(wrapped_dist, 'index.html')
        if os.path.exists(wrapped_index):
            return send_file(wrapped_index, mimetype='text/html')
        else:
            return "PBJ Wrapped app not built. Run 'npm run build' in pbj-wrapped directory.", 404

# Legacy route: Serve pbj-wrapped app (for backward compatibility)
@app.route('/pbj-wrapped')
@app.route('/pbj-wrapped/')
def pbj_wrapped_index():
    """Serve the pbj-wrapped React app index page (legacy) with server-rendered SEO metadata"""
    seo = get_seo_metadata(request.path)
    assets = get_built_assets()
    try:
        return render_template('wrapped_index.html', seo=seo, assets=assets)
    except Exception as e:
        # Fallback to static file if template rendering fails
        print(f"Warning: Template rendering failed: {e}, falling back to static file")
    wrapped_index = os.path.join('pbj-wrapped', 'dist', 'index.html')
    if os.path.exists(wrapped_index):
        return send_file(wrapped_index, mimetype='text/html')
    else:
        return "PBJ Wrapped app not built. Run 'npm run build' in pbj-wrapped directory.", 404

@app.route('/pbj-wrapped/<path:path>')
def pbj_wrapped_static(path):
    """Serve static files and handle SPA routing for pbj-wrapped (legacy)"""
    wrapped_dist = os.path.join('pbj-wrapped', 'dist')
    
    # Check if it's a static asset (has extension)
    file_path = os.path.join(wrapped_dist, path)
    if os.path.isfile(file_path):
        # Serve the static file with proper MIME types
        if path.endswith('.js'):
            return send_file(file_path, mimetype='application/javascript')
        elif path.endswith('.css'):
            return send_file(file_path, mimetype='text/css')
        elif path.endswith('.json'):
            return send_file(file_path, mimetype='application/json')
        elif path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.woff', '.woff2', '.ttf', '.eot')):
            return send_file(file_path)
        else:
            return send_from_directory(wrapped_dist, path)
    else:
        # For SPA routing, serve index.html for any route with server-rendered SEO metadata
        # This allows React Router to handle client-side routing
        seo = get_seo_metadata(request.path)
        assets = get_built_assets()
        try:
            return render_template('wrapped_index.html', seo=seo, assets=assets)
        except Exception as e:
            # Fallback to static file if template rendering fails
            print(f"Warning: Template rendering failed: {e}, falling back to static file")
        wrapped_index = os.path.join(wrapped_dist, 'index.html')
        if os.path.exists(wrapped_index):
            return send_file(wrapped_index, mimetype='text/html')
        else:
            return "PBJ Wrapped app not built. Run 'npm run build' in pbj-wrapped directory.", 404

@app.route('/<path:filename>')
def static_files(filename):
    # Don't handle routes that are already defined
    if filename in ['insights', 'insights.html', 'about', 'pbj-sample', 'report', 'report.html', 'sitemap.xml', 'pbj-wrapped', 'wrapped', 'sff', 'data', 'pbjpedia']:
        from flask import abort
        abort(404)
    
    # Exclude directories that shouldn't be served (prevents connection failures)
    excluded_prefixes = ['node_modules/', '.git/', 'pbj-wrapped/node_modules/', 'pbj-wrapped/.git/', 'data/']
    if any(filename.startswith(prefix) for prefix in excluded_prefixes):
        from flask import abort
        abort(404)
    
    # Handle images with proper headers (including favicon)
    if filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico')):
        response = send_from_directory('.', filename, mimetype='image/png' if filename.endswith('.ico') else 'image/png')
        # Add cache-control headers for favicon to ensure updates are visible
        if filename.endswith('.ico') or 'favicon' in filename.lower():
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response
    # Handle CSS
    elif filename.endswith('.css'):
        return send_from_directory('.', filename, mimetype='text/css')
    # Handle JS
    elif filename.endswith('.js'):
        return send_from_directory('.', filename, mimetype='application/javascript')
    # Handle JSON files
    elif filename.endswith('.json'):
        json_path = os.path.join('.', filename)
        if os.path.isfile(json_path):
            return send_file(json_path, mimetype='application/json')
        from flask import abort
        abort(404)
    # Handle CSV files
    elif filename.endswith('.csv'):
        csv_path = os.path.join('.', filename)
        if os.path.isfile(csv_path):
            return send_file(csv_path, mimetype='text/csv')
        from flask import abort
        abort(404)
    # Handle other static files
    else:
        return send_from_directory('.', filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

