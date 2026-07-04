import json
import pandas as pd
from pathlib import Path

lite = pd.read_csv('facility_lite_metrics.csv', dtype={'PROVNUM': str})
lite['PROVNUM'] = lite['PROVNUM'].str.zfill(6)
pi = pd.read_csv('provider_info_combined.csv', dtype={'ccn': str}, low_memory=False)
pi['ccn'] = pi['ccn'].str.zfill(6)

rows = [
    ('035242', 'Gorman'),
    ('055293', 'Santa Anita'),
    ('245544', 'Victory'),
    ('265379', 'Pinnacle'),
    ('525409', 'Pine View'),
    ('265330', 'North Village'),
]
print('=== Q3 2025 PBJ (what SFF q2 JSON currently serves) ===')
for ccn, name in rows:
    q3 = lite[(lite.PROVNUM == ccn) & (lite.CY_Qtr == '2025Q3')]
    q4 = lite[(lite.PROVNUM == ccn) & (lite.CY_Qtr == '2025Q4')]
    if not len(q3):
        print(name, ccn, 'NO Q3')
        continue
    r = q3.iloc[0]
    cm = None
    sub = pi[pi.ccn == ccn]
    if len(sub):
        cm = float(sub.iloc[-1]['case_mix_total_nurse_hrs_per_resident_per_day'])
    pct = round(r.Total_Nurse_HPRD / cm * 100, 1) if cm else None
    print(
        f"{name} ({ccn}): census={r.Census:.1f} total={r.Total_Nurse_HPRD:.2f} "
        f"direct={r.Nurse_Care_HPRD:.2f} rn={r.Total_RN_HPRD:.2f} case_mix_pct={pct}"
    )
    if len(q4):
        r4 = q4.iloc[0]
        print(f"  Q4 would be: census={r4.Census:.1f} total={r4.Total_Nurse_HPRD:.2f}")
