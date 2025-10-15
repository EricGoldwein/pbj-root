import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
from scipy import stats
import duckdb
from decimal import Decimal, ROUND_HALF_UP

# Page configuration
st.set_page_config(
    page_title="PBJ Playground - Advanced Analytics",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

def find_file(filename):
    """Find a file in multiple possible locations."""
    import os
    possible_paths = [
        os.path.join(os.getcwd(), 'pbj_lite', filename),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pbj_lite', filename),
        os.path.join(os.getcwd(), filename),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), filename),
        filename
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

@st.cache_data
def load_facility_metrics():
    """Load facility metrics data for advanced analytics."""
    try:
        facility_path = find_file('facility_lite_metrics.csv')
        if not facility_path:
            st.error("Facility metrics file not found")
            return pd.DataFrame()
        
        df = pd.read_csv(facility_path, dtype={'PROVNUM': str})
        
        # Filter for most recent quarter
        if 'CY_Qtr' in df.columns:
            latest_quarter = df['CY_Qtr'].max()
            df = df[df['CY_Qtr'] == latest_quarter]
        
        # Clean data - remove nulls and outliers
        df = df.dropna(subset=['Total_Nurse_HPRD', 'Contract_Percentage'])
        
        # Remove extreme outliers (beyond 3 standard deviations)
        for col in ['Total_Nurse_HPRD', 'Contract_Percentage']:
            if col in df.columns:
                mean = df[col].mean()
                std = df[col].std()
                df = df[abs(df[col] - mean) <= 3 * std]
        
        return df
    except Exception as e:
        st.error(f"Error loading facility metrics: {str(e)}")
        return pd.DataFrame()

def format_metric(value, decimal_places=2, percentage=False):
    """Format metric values with proper rounding."""
    if pd.isna(value) or value is None:
        return "N/A"
    
    if percentage:
        return f"{float(Decimal(str(value)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)):.1f}%"
    else:
        return f"{float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)):.{decimal_places}f}"

def create_hprd_distribution_chart(df):
    """Create Total Nurse HPRD distribution chart."""
    if df.empty or 'Total_Nurse_HPRD' not in df.columns:
        return None
    
    hprd_data = df['Total_Nurse_HPRD'].dropna()
    
    # Create histogram
    fig = go.Figure()
    
    # Add histogram
    fig.add_trace(go.Histogram(
        x=hprd_data,
        nbinsx=50,
        name='HPRD Distribution',
        marker_color='#1f77b4',
        opacity=0.7,
        hovertemplate='HPRD: %{x:.2f}<br>Count: %{y}<extra></extra>'
    ))
    
    # Add statistical lines
    mean_val = hprd_data.mean()
    median_val = hprd_data.median()
    std_val = hprd_data.std()
    
    # Add mean line
    fig.add_vline(
        x=mean_val,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mean: {format_metric(mean_val)}",
        annotation_position="top"
    )
    
    # Add median line
    fig.add_vline(
        x=median_val,
        line_dash="dot",
        line_color="green",
        annotation_text=f"Median: {format_metric(median_val)}",
        annotation_position="top"
    )
    
    # Add standard deviation bands
    fig.add_vrect(
        x0=mean_val - std_val,
        x1=mean_val + std_val,
        fillcolor="lightblue",
        opacity=0.2,
        annotation_text=f"±1σ: {format_metric(mean_val - std_val)} to {format_metric(mean_val + std_val)}",
        annotation_position="top"
    )
    
    fig.update_layout(
        title="Total Nurse HPRD Distribution (Non-Normal)",
        xaxis_title="Hours Per Resident Day (HPRD)",
        yaxis_title="Number of Facilities",
        showlegend=False,
        height=500,
        template="plotly_white"
    )
    
    return fig

def create_contract_distribution_chart(df):
    """Create contract staff percentage distribution chart."""
    if df.empty or 'Contract_Percentage' not in df.columns:
        return None
    
    contract_data = df['Contract_Percentage'].dropna()
    
    # Create histogram
    fig = go.Figure()
    
    # Add histogram
    fig.add_trace(go.Histogram(
        x=contract_data,
        nbinsx=50,
        name='Contract % Distribution',
        marker_color='#ff7f0e',
        opacity=0.7,
        hovertemplate='Contract %: %{x:.1f}%<br>Count: %{y}<extra></extra>'
    ))
    
    # Add statistical lines
    mean_val = contract_data.mean()
    median_val = contract_data.median()
    std_val = contract_data.std()
    
    # Add mean line
    fig.add_vline(
        x=mean_val,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mean: {format_metric(mean_val, percentage=True)}",
        annotation_position="top"
    )
    
    # Add median line
    fig.add_vline(
        x=median_val,
        line_dash="dot",
        line_color="green",
        annotation_text=f"Median: {format_metric(median_val, percentage=True)}",
        annotation_position="top"
    )
    
    # Add standard deviation bands
    fig.add_vrect(
        x0=mean_val - std_val,
        x1=mean_val + std_val,
        fillcolor="lightcoral",
        opacity=0.2,
        annotation_text=f"±1σ: {format_metric(mean_val - std_val, percentage=True)} to {format_metric(mean_val + std_val, percentage=True)}",
        annotation_position="top"
    )
    
    fig.update_layout(
        title="Contract Staff Percentage Distribution",
        xaxis_title="Contract Staff Percentage (%)",
        yaxis_title="Number of Facilities",
        showlegend=False,
        height=500,
        template="plotly_white"
    )
    
    return fig

def create_comparison_chart(df):
    """Create side-by-side comparison of HPRD vs Contract % distributions."""
    if df.empty:
        return None
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Total Nurse HPRD Distribution", "Contract Staff % Distribution"),
        horizontal_spacing=0.1
    )
    
    # HPRD histogram
    hprd_data = df['Total_Nurse_HPRD'].dropna()
    fig.add_trace(
        go.Histogram(
            x=hprd_data,
            nbinsx=30,
            name='HPRD',
            marker_color='#1f77b4',
            opacity=0.7
        ),
        row=1, col=1
    )
    
    # Contract % histogram
    contract_data = df['Contract_Percentage'].dropna()
    fig.add_trace(
        go.Histogram(
            x=contract_data,
            nbinsx=30,
            name='Contract %',
            marker_color='#ff7f0e',
            opacity=0.7
        ),
        row=1, col=2
    )
    
    fig.update_layout(
        title="Distribution Comparison: HPRD vs Contract Staff %",
        showlegend=False,
        height=500,
        template="plotly_white"
    )
    
    fig.update_xaxes(title_text="HPRD", row=1, col=1)
    fig.update_xaxes(title_text="Contract %", row=1, col=2)
    fig.update_yaxes(title_text="Count", row=1, col=1)
    fig.update_yaxes(title_text="Count", row=1, col=2)
    
    return fig

def calculate_statistics(df):
    """Calculate detailed statistics for the distributions."""
    if df.empty:
        return {}
    
    stats_dict = {}
    
    # HPRD statistics
    if 'Total_Nurse_HPRD' in df.columns:
        hprd_data = df['Total_Nurse_HPRD'].dropna()
        if not hprd_data.empty:
            stats_dict['hprd'] = {
                'count': len(hprd_data),
                'mean': hprd_data.mean(),
                'median': hprd_data.median(),
                'std': hprd_data.std(),
                'min': hprd_data.min(),
                'max': hprd_data.max(),
                'q25': hprd_data.quantile(0.25),
                'q75': hprd_data.quantile(0.75),
                'skewness': stats.skew(hprd_data),
                'kurtosis': stats.kurtosis(hprd_data)
            }
    
    # Contract % statistics
    if 'Contract_Percentage' in df.columns:
        contract_data = df['Contract_Percentage'].dropna()
        if not contract_data.empty:
            stats_dict['contract'] = {
                'count': len(contract_data),
                'mean': contract_data.mean(),
                'median': contract_data.median(),
                'std': contract_data.std(),
                'min': contract_data.min(),
                'max': contract_data.max(),
                'q25': contract_data.quantile(0.25),
                'q75': contract_data.quantile(0.75),
                'skewness': stats.skew(contract_data),
                'kurtosis': stats.kurtosis(contract_data)
            }
    
    return stats_dict

def create_covid_bump_chart(df):
    """Create COVID bump illusion chart showing HPRD vs Census trends."""
    if df.empty:
        return None
    
    # Group by quarter and calculate weighted averages
    quarterly_data = df.groupby('CY_Qtr').agg({
        'Total_Nurse_HPRD': 'mean',
        'Census': 'mean'
    }).reset_index()
    
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Total Nurse HPRD Over Time", "Average Census Over Time"),
        vertical_spacing=0.1
    )
    
    # HPRD trend
    fig.add_trace(
        go.Scatter(
            x=quarterly_data['CY_Qtr'],
            y=quarterly_data['Total_Nurse_HPRD'],
            mode='lines+markers',
            name='HPRD',
            line=dict(color='#1f77b4', width=3)
        ),
        row=1, col=1
    )
    
    # Census trend
    fig.add_trace(
        go.Scatter(
            x=quarterly_data['CY_Qtr'],
            y=quarterly_data['Census'],
            mode='lines+markers',
            name='Census',
            line=dict(color='#ff7f0e', width=3)
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        title="The 'COVID Bump' Illusion: When Fewer Residents Make Averages Look Better",
        height=600,
        showlegend=True,
        template="plotly_white"
    )
    
    return fig

def create_mean_median_comparison(df):
    """Create mean vs median HPRD comparison chart."""
    if df.empty or 'Total_Nurse_HPRD' not in df.columns:
        return None
    
    hprd_data = df['Total_Nurse_HPRD'].dropna()
    
    # Calculate statistics
    mean_val = hprd_data.mean()
    median_val = hprd_data.median()
    
    # Create histogram with 20 bins (0.25 HPRD wide)
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=hprd_data,
        nbinsx=20,
        name='HPRD Distribution',
        marker_color='#1f77b4',
        opacity=0.7,
        hovertemplate='HPRD: %{x:.2f}<br>Count: %{y}<extra></extra>'
    ))
    
    # Add mean line
    fig.add_vline(
        x=mean_val,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mean: {format_metric(mean_val)}",
        annotation_position="top"
    )
    
    # Add median line
    fig.add_vline(
        x=median_val,
        line_dash="dot",
        line_color="green",
        annotation_text=f"Median: {format_metric(median_val)}",
        annotation_position="top"
    )
    
    # Add federal minimum reference
    fig.add_vline(
        x=3.48,
        line_dash="dashdot",
        line_color="purple",
        annotation_text="Federal Min: 3.48",
        annotation_position="top"
    )
    
    fig.update_layout(
        title="Mean vs. Median HPRD: Most Nursing Homes Are Below Average—Literally",
        xaxis_title="Hours Per Resident Day (HPRD)",
        yaxis_title="Number of Facilities",
        showlegend=False,
        height=500,
        template="plotly_white"
    )
    
    return fig

def create_average_methods_comparison(df):
    """Create comparison of different averaging methods."""
    if df.empty or 'Total_Nurse_HPRD' not in df.columns:
        return None
    
    hprd_data = df['Total_Nurse_HPRD'].dropna()
    census_data = df['Census'].dropna() if 'Census' in df.columns else None
    
    # Calculate different averages
    simple_mean = hprd_data.mean()
    median = hprd_data.median()
    
    # Weighted average (if census data available)
    if census_data is not None and len(census_data) == len(hprd_data):
        weighted_mean = np.average(hprd_data, weights=census_data)
    else:
        weighted_mean = simple_mean
    
    # Create comparison chart
    methods = ['Simple Mean', 'Weighted Mean', 'Median']
    values = [simple_mean, weighted_mean, median]
    colors = ['#e74c3c', '#f39c12', '#27ae60']
    
    fig = go.Figure(data=[
        go.Bar(
            x=methods,
            y=values,
            marker_color=colors,
            text=[f"{v:.2f}" for v in values],
            textposition='auto',
            hovertemplate='%{x}: %{y:.2f} HPRD<extra></extra>'
        )
    ])
    
    fig.update_layout(
        title="The 'Average Nursing Home' Fallacy: Three Ways to Compute National Average",
        xaxis_title="Calculation Method",
        yaxis_title="HPRD",
        height=400,
        template="plotly_white"
    )
    
    return fig, {
        'simple_mean': simple_mean,
        'weighted_mean': weighted_mean,
        'median': median
    }

def create_contract_median_mean_chart(df):
    """Create contract staffing median vs mean comparison."""
    if df.empty or 'Contract_Percentage' not in df.columns:
        return None
    
    contract_data = df['Contract_Percentage'].dropna()
    
    # Calculate statistics
    mean_val = contract_data.mean()
    median_val = contract_data.median()
    
    # Create histogram
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=contract_data,
        nbinsx=30,
        name='Contract % Distribution',
        marker_color='#ff7f0e',
        opacity=0.7,
        hovertemplate='Contract %: %{x:.1f}%<br>Count: %{y}<extra></extra>'
    ))
    
    # Add mean line
    fig.add_vline(
        x=mean_val,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mean: {format_metric(mean_val, percentage=True)}",
        annotation_position="top"
    )
    
    # Add median line
    fig.add_vline(
        x=median_val,
        line_dash="dot",
        line_color="green",
        annotation_text=f"Median: {format_metric(median_val, percentage=True)}",
        annotation_position="top"
    )
    
    fig.update_layout(
        title="Contract Staffing: Median vs. Mean - The Mean Makes It Look Like Everyone's Outsourcing",
        xaxis_title="Contract Staff Percentage (%)",
        yaxis_title="Number of Facilities",
        showlegend=False,
        height=500,
        template="plotly_white"
    )
    
    return fig

def create_hprd_distributions_by_type(df):
    """Create HPRD distributions for different staff types."""
    if df.empty:
        return None
    
    # Check which columns are available
    available_columns = []
    column_mappings = {
        'Total_Nurse_HPRD': 'Total Nurse HPRD',
        'RN_HPRD': 'RN HPRD (with Admin)',
        'LPN_HPRD': 'LPN HPRD',
        'CNA_HPRD': 'CNA HPRD'
    }
    
    for col, label in column_mappings.items():
        if col in df.columns:
            available_columns.append((col, label))
    
    if not available_columns:
        return None
    
    # Create subplots
    n_cols = min(2, len(available_columns))
    n_rows = (len(available_columns) + 1) // 2
    
    fig = make_subplots(
        rows=n_rows, cols=n_cols,
        subplot_titles=[label for _, label in available_columns],
        vertical_spacing=0.15,
        horizontal_spacing=0.1
    )
    
    for i, (col, label) in enumerate(available_columns):
        row = (i // n_cols) + 1
        col_idx = (i % n_cols) + 1
        
        data = df[col].dropna()
        if not data.empty:
            fig.add_trace(
                go.Histogram(
                    x=data,
                    nbinsx=20,
                    name=label,
                    marker_color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'][i % 4],
                    opacity=0.7
                ),
                row=row, col=col_idx
            )
    
    fig.update_layout(
        title="HPRD Distributions by Staff Type: Typical Range 2.5–5.0 HPRD",
        height=400 * n_rows,
        showlegend=False,
        template="plotly_white"
    )
    
    return fig

def main():
    """Main function for the PBJ Playground page."""
    
    # Header
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="color: #1769aa; margin-bottom: 0.5rem;">🎮 PBJ Playground</h1>
        <p style="color: #7a869a; font-size: 1.1em;">Fun with Charts • Advanced Analytics & Statistical Insights</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Load data
    with st.spinner("Loading facility data..."):
        df = load_facility_metrics()
    
    if df.empty:
        st.error("No data available for analysis")
        return
    
    # Data overview
    st.markdown("### Data Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Facilities", f"{len(df):,}")
    
    with col2:
        latest_quarter = df['CY_Qtr'].iloc[0] if 'CY_Qtr' in df.columns else "N/A"
        st.metric("Latest Quarter", latest_quarter)
    
    with col3:
        states = df['STATE'].nunique() if 'STATE' in df.columns else 0
        st.metric("States", states)
    
    with col4:
        counties = df['COUNTY_NAME'].nunique() if 'COUNTY_NAME' in df.columns else 0
        st.metric("Counties", counties)
    
    st.markdown("---")
    
    # Advanced Analytics
    st.markdown("### Advanced Analytics & Statistical Insights")
    
    # Create tabs for different analyses
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "COVID Bump Illusion", 
        "Mean vs Median", 
        "Average Methods", 
        "Contract Analysis",
        "HPRD Distributions",
        "Statistical Summary"
    ])
    
    with tab1:
        st.markdown("#### 1. The 'COVID Bump' Illusion")
        st.markdown("""
        **Insight**: Staffing ratios appeared to rise in 2020—but mainly because residents died or left. 
        Absolute staffing hours actually fell.
        
        **Tagline**: When fewer residents make your averages look better, it's not improvement—it's math.
        """)
        
        fig_covid = create_covid_bump_chart(df)
        if fig_covid:
            st.plotly_chart(fig_covid, use_container_width=True)
        else:
            st.warning("Unable to create COVID bump chart")
    
    with tab2:
        st.markdown("#### 2. Mean vs. Median HPRD")
        st.markdown("""
        **Insight**: A few overstaffed outliers pull the mean up; median better represents typical care.
        
        **Tagline**: Most nursing homes are below average—literally.
        """)
        
        fig_mean_median = create_mean_median_comparison(df)
        if fig_mean_median:
            st.plotly_chart(fig_mean_median, use_container_width=True)
        else:
            st.warning("Unable to create mean vs median chart")
    
    with tab3:
        st.markdown("#### 3. The 'Average Nursing Home' Fallacy")
        st.markdown("""
        **Three ways to compute a national "average":**
        - **Simple Mean**: Treats a 30-bed facility the same as a 500-bed facility
        - **Weighted Mean**: Uses census as weights (aggregate approach)
        - **Median**: Middle value, less affected by outliers
        
        **Tagline**: When everyone quotes "3.73 HPRD," ask: average by what?
        """)
        
        fig_average_methods, avg_stats = create_average_methods_comparison(df)
        if fig_average_methods:
            st.plotly_chart(fig_average_methods, use_container_width=True)
            
            # Show the percentage difference
            if avg_stats:
                simple_mean = avg_stats['simple_mean']
                weighted_mean = avg_stats['weighted_mean']
                median = avg_stats['median']
                
                st.markdown("**Percentage Differences:**")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    diff_weighted = abs(simple_mean - weighted_mean) / simple_mean * 100
                    st.metric("Simple vs Weighted", f"{diff_weighted:.1f}%")
                
                with col2:
                    diff_median = abs(simple_mean - median) / simple_mean * 100
                    st.metric("Simple vs Median", f"{diff_median:.1f}%")
                
                with col3:
                    diff_weighted_median = abs(weighted_mean - median) / weighted_mean * 100
                    st.metric("Weighted vs Median", f"{diff_weighted_median:.1f}%")
        else:
            st.warning("Unable to create average methods comparison")
    
    with tab4:
        st.markdown("#### 4. Contract Staffing: Median vs. Mean")
        st.markdown("""
        **Insight**: A few facilities use a ton of contract labor; most barely any.
        
        **Tagline**: The mean makes it look like everyone's outsourcing. The median says otherwise.
        """)
        
        fig_contract = create_contract_median_mean_chart(df)
        if fig_contract:
            st.plotly_chart(fig_contract, use_container_width=True)
        else:
            st.warning("Unable to create contract staffing chart")
    
    with tab5:
        st.markdown("#### 5. HPRD Distributions by Staff Type")
        st.markdown("""
        **Typical Range and Distribution:**
        - **Most facilities**: 2.5–5.0 HPRD
        - **Long tails**: Some dip below 2.0 or above 6.0 (rare but real)
        - **Total spread**: ≈ 1.5–7.0 HPRD
        
        **Visual Design**: 20 bins, each ~0.25 HPRD wide, spanning 1.5–7.5
        """)
        
        fig_distributions = create_hprd_distributions_by_type(df)
        if fig_distributions:
            st.plotly_chart(fig_distributions, use_container_width=True)
        else:
            st.warning("Unable to create HPRD distributions chart")
    
    with tab6:
        st.markdown("#### 6. Statistical Summary")
        
        stats_dict = calculate_statistics(df)
        
        if 'hprd' in stats_dict:
            st.markdown("##### Total Nurse HPRD Statistics")
            hprd_stats = stats_dict['hprd']
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Mean", format_metric(hprd_stats['mean']))
                st.metric("Median", format_metric(hprd_stats['median']))
                st.metric("Std Dev", format_metric(hprd_stats['std']))
            
            with col2:
                st.metric("Min", format_metric(hprd_stats['min']))
                st.metric("Max", format_metric(hprd_stats['max']))
                st.metric("Q25", format_metric(hprd_stats['q25']))
            
            with col3:
                st.metric("Q75", format_metric(hprd_stats['q75']))
                st.metric("Skewness", format_metric(hprd_stats['skewness']))
                st.metric("Kurtosis", format_metric(hprd_stats['kurtosis']))
        
        if 'contract' in stats_dict:
            st.markdown("##### Contract Staff % Statistics")
            contract_stats = stats_dict['contract']
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Mean", format_metric(contract_stats['mean'], percentage=True))
                st.metric("Median", format_metric(contract_stats['median'], percentage=True))
                st.metric("Std Dev", format_metric(contract_stats['std'], percentage=True))
            
            with col2:
                st.metric("Min", format_metric(contract_stats['min'], percentage=True))
                st.metric("Max", format_metric(contract_stats['max'], percentage=True))
                st.metric("Q25", format_metric(contract_stats['q25'], percentage=True))
            
            with col3:
                st.metric("Q75", format_metric(contract_stats['q75'], percentage=True))
                st.metric("Skewness", format_metric(contract_stats['skewness']))
                st.metric("Kurtosis", format_metric(contract_stats['kurtosis']))
    
    # Key Insights
    st.markdown("---")
    st.markdown("### Key Insights")
    
    if 'hprd' in stats_dict and 'contract' in stats_dict:
        hprd_stats = stats_dict['hprd']
        contract_stats = stats_dict['contract']
        
        # Calculate insights
        hprd_skew = hprd_stats['skewness']
        contract_skew = contract_stats['skewness']
        
        hprd_mean_median_diff = abs(hprd_stats['mean'] - hprd_stats['median'])
        contract_mean_median_diff = abs(contract_stats['mean'] - contract_stats['median'])
        
        st.markdown(f"""
        **Distribution Characteristics:**
        
        - **HPRD Distribution**: {'Right-skewed' if hprd_skew > 0.5 else 'Left-skewed' if hprd_skew < -0.5 else 'Approximately normal'} 
          (skewness: {format_metric(hprd_skew)})
        
        - **Contract % Distribution**: {'Right-skewed' if contract_skew > 0.5 else 'Left-skewed' if contract_skew < -0.5 else 'Approximately normal'}
          (skewness: {format_metric(contract_skew)})
        
        - **Mean-Median Difference**: 
          - HPRD: {format_metric(hprd_mean_median_diff)} 
          - Contract %: {format_metric(contract_mean_median_diff, percentage=True)}
        
        **Interpretation:**
        - The HPRD distribution is {'more normal' if abs(hprd_skew) < abs(contract_skew) else 'less normal'} than contract staff distribution
        - Contract staff usage shows {'higher' if contract_mean_median_diff > hprd_mean_median_diff else 'lower'} variability in facility practices
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; color: #666; font-size: 0.9em;">
        <p>🎮 PBJ Playground • Fun with Charts & Advanced Analytics</p>
        <p>By <a href="https://www.320insight.com/" target="_blank" style="color: #1E88E5; text-decoration: none;">320 Consulting LLC</a></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
