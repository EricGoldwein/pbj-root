import pandas as pd
from utils.staffing_chart_anomalies import is_staffing_hprd_anomaly, apply_staffing_series_anomalies

df = pd.read_csv('facility_quarterly_metrics.csv', usecols=['PROVNUM','CY_Qtr','RN_HPRD','RN_Care_HPRD'], low_memory=False)
df['RN_HPRD'] = pd.to_numeric(df['RN_HPRD'], errors='coerce')
df = df.dropna(subset=['RN_HPRD'])
df = df[df['RN_HPRD'] > 0]

# Distribution around RN floor
bins = [0, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.30, 999]
labels = ['0-0.05','0.05-0.08','0.08-0.10','0.10-0.12','0.12-0.15','0.15-0.20','0.20-0.30','0.30+']
df['bin'] = pd.cut(df['RN_HPRD'], bins=bins, labels=labels, right=False)
print('RN_HPRD distribution (facility-quarters):')
print(df['bin'].value_counts().sort_index().to_string())
print()

below10 = df[df['RN_HPRD'] < 0.10]
print(f'facility-quarters with RN < 0.10: {len(below10):,} ({100*len(below10)/len(df):.3f}% of {len(df):,})')
print(f'unique facilities with any RN < 0.10: {below10["PROVNUM"].nunique():,}')
print()

# False positive probe: RN in [0.08,0.10) with stable neighbors (both neighbors within 20% of value)
fp_candidates = []
for prov, g in df.groupby('PROVNUM'):
    g = g.sort_values('CY_Qtr')
    vals = g['RN_HPRD'].tolist()
    qs = g['CY_Qtr'].tolist()
    for i in range(1, len(vals)-1):
        v, p, n = vals[i], vals[i-1], vals[i+1]
        if 0.08 <= v < 0.10 and p > 0 and n > 0:
            if abs(p-v)/v < 0.20 and abs(n-v)/v < 0.20:
                flagged, reason = is_staffing_hprd_anomaly(v, p, n, profile='rn', typical_level=0.25)
                if flagged:
                    fp_candidates.append((prov, qs[i], v, p, n, reason))

print(f'Stable-neighbor RN in [0.08,0.10) flagged at 0.10 floor: {len(fp_candidates)}')
for row in fp_candidates[:8]:
    print(' ', row)
print()

# Compare thresholds 0.08 vs 0.10 on full facility series
flag08 = flag10 = neighbor_only = 0
examples_08not10 = []
for prov, g in df.groupby('PROVNUM'):
    g = g.sort_values('CY_Qtr')
    quarters = g['CY_Qtr'].astype(str).tolist()
    rn = g['RN_HPRD'].tolist()
    out10 = apply_staffing_series_anomalies(quarters, rn, None, ccn=prov, profile='rn')
    # manual 0.08 check on same quarters
    for i, v in enumerate(rn):
        if v is None or pd.isna(v):
            continue
        prior = rn[i-1] if i>0 else None
        nxt = rn[i+1] if i<len(rn)-1 else None
        f10 = out10['is_staffing_anomaly'][i]
        f08, _ = is_staffing_hprd_anomaly(v, prior, nxt, profile='rn', typical_level=None)
        if v < 0.08:
            # would need custom threshold - use direct abs check
            pass
        if f10:
            flag10 += 1
            reason = out10['anomaly_reason'][i] or ''
            if 'below 0.05' in reason or 'below 5%' in reason:
                neighbor_only += 1
        if v < 0.08 and not f10:
            examples_08not10.append((prov, quarters[i], v))

print(f'Total RN anomaly flags at 0.10 threshold: {flag10:,}')
print(f'  of which neighbor-rule (not abs-only): {neighbor_only:,}')
band_08_10 = df[(df['RN_HPRD'] >= 0.08) & (df['RN_HPRD'] < 0.10)]
print(f'facility-quarters in [0.08, 0.10): {len(band_08_10):,}')
