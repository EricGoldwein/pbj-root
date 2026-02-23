"""
Shared PBJ formatting: rounding (ROUND_HALF_UP), metric labels, quarter display.
Used by facility (provider), state, and entity pages for consistent display.
Aligns with pbj-contract/formatting.yaml and definitions.yaml (via contract_adapter when available).
"""
from decimal import Decimal, ROUND_HALF_UP


def round_half_up(value, decimals=0):
    """Round to given decimal places using ROUND_HALF_UP (audit/contract)."""
    if value is None or (isinstance(value, float) and __import__('math').isnan(value)):
        return None
    try:
        d = Decimal(str(float(value)))
        quantize = Decimal('0.1') ** decimals
        return float(d.quantize(quantize, rounding=ROUND_HALF_UP))
    except (TypeError, ValueError):
        return None


def format_quarter_display(quarter_str):
    """Convert quarter from 2025Q2 to Q2 2025 (audit: Qn YYYY)."""
    if not quarter_str:
        return "N/A"
    s = str(quarter_str).strip()
    import re
    match = re.match(r'(\d{4})Q(\d)', s)
    if match:
        return f"Q{match.group(2)} {match.group(1)}"
    return s


# Metric key -> display label (fallback; contract_adapter.definitions.metric_labels used when available)
METRIC_LABELS = {
    'Total_Nurse_HPRD': 'Total Nurse HPRD',
    'Total_RN_HPRD': 'RN HPRD',
    'RN_HPRD': 'RN HPRD',
    'Nurse_Care_HPRD': 'Direct Care HPRD',
    'RN_Care_HPRD': 'RN Care HPRD',
    'Nurse_Assistant_HPRD': 'Nurse Aide HPRD',
    'Contract_Percentage': 'Contract %',
    'avg_daily_census': 'Census',
}


def get_metric_label(key):
    """Return display label for metric key; use contract if available else METRIC_LABELS."""
    try:
        from contract_adapter import contract
        if contract.definitions and getattr(contract.definitions, 'metric_labels', None):
            ml = contract.definitions.metric_labels
            label = getattr(ml, key, None)
            if label is not None:
                return label
    except Exception:
        pass
    return METRIC_LABELS.get(key, key.replace('_', ' '))


def format_metric_value(value, metric_key, default='N/A'):
    """Format a metric for display: HPRD 2 decimals, percentage 1 decimal (ROUND_HALF_UP)."""
    if value is None or (isinstance(value, float) and __import__('math').isnan(value)):
        return default
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if 'Percentage' in metric_key or metric_key == 'Contract_Percentage':
        r = round_half_up(v, 1)
        return f"{r:.1f}" if r is not None else default
    if 'census' in metric_key.lower() or metric_key == 'avg_daily_census':
        r = round_half_up(v, 0)
        return f"{int(r)}" if r is not None else default
    # HPRD and similar
    r = round_half_up(v, 2)
    return f"{r:.2f}" if r is not None else default


def fmt(val, decimals=2, default='N/A'):
    """Generic formatter for state/region pages: float to string with given decimals (ROUND_HALF_UP)."""
    if val is None or (isinstance(val, float) and __import__('math').isnan(val)):
        return default
    try:
        v = float(val)
        r = round_half_up(v, decimals)
        return f"{r:.{decimals}f}" if r is not None else default
    except (TypeError, ValueError):
        return default
