import pandas as pd
from utils.staffing_chart_anomalies import apply_staffing_series_anomalies

df = pd.read_csv('facility_quarterly_metrics.csv', usecols=['PROVNUM','CY_Qtr','RN_HPRD'], low_memory=False)
df['RN_HPRD'] = pd.to_numeric(df['RN_HPRD'], errors='coerce')

# Homes with median RN in [0.08,0.10) - consistently low RN
med = df.groupby('PROVNUM')['RN_HPRD'].median()
low_rn_homes = med[(med >= 0.08) & (med < 0.10)].index.tolist()[:5]
print('Consistently low-RN homes (median 0.08-0.10):', len(med[(med >= 0.08) & (med < 0.10)]))
for prov in low_rn_homes:
    g = df[df['PROVNUM']==prov].sort_values('CY_Qtr')
    q = g['CY_Qtr'].astype(str).tolist()
    rn = g['RN_HPRD'].tolist()
    out = apply_staffing_series_anomalies(q, rn, None, ccn=prov, profile='rn')
    flagged = sum(out['is_staffing_anomaly'])
    print(f'  {prov}: {flagged}/{len(q)} quarters flagged, median={med[prov]:.3f}')

# How many homes have >50% quarters flagged purely due to abs<0.10?
high_flag_homes = 0
for prov, g in df.groupby('PROVNUM'):
    g = g.sort_values('CY_Qtr')
    rn = [x for x in g['RN_HPRD'].tolist() if pd.notna(x) and x>0]
    if len(rn) < 4: continue
    q = g['CY_Qtr'].astype(str).tolist()
    out = apply_staffing_series_anomalies(q, g['RN_HPRD'].tolist(), None, ccn=prov, profile='rn')
    flagged = sum(out['is_staffing_anomaly'])
    if flagged >= len(q) * 0.5 and med.get(prov, 1) < 0.10:
        high_flag_homes += 1
print(f'Homes with median RN<0.10 and >=50% quarters flagged: {high_flag_homes}')

# Compare 0.08 threshold impact
from utils.staffing_chart_anomalies import is_staffing_hprd_anomaly
count08 = sum(1 for v in df['RN_HPRD'].dropna() if v > 0 and v < 0.08)
count10 = sum(1 for v in df['RN_HPRD'].dropna() if v > 0 and v < 0.10)
print(f'Rows <0.08: {count08:,}; <0.10: {count10:,}; band 0.08-0.10: {count10-count08:,}')
