#!/usr/bin/env python3
"""Broad provider page sample: 200 + critical markers; log scan signals."""
from __future__ import annotations

import io
import json
import os
import random
import re
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ['PBJ_PROVIDER_COLD_BURST_LIMIT'] = '0'
os.environ['PBJ_PROVIDER_CRAWLER_COLD_LIMIT'] = '0'
os.environ.pop('RENDER', None)


def _critical_ok(html: str, status: int, prov: str = '') -> tuple[bool, list[str]]:
    if status != 200:
        return False, [f'status_{status}']
    fails = []
    if len(html) < 5000:
        fails.append('html_too_short')
    if 'pbj-chart-container' not in html and 'pbj-chart-wrapper' not in html:
        fails.append('no_charts')
    if 'HPRD' not in html:
        fails.append('no_hprd')
    ccn_ok = bool(prov and prov in html) or bool(
        re.search(r'data-ccn=["\'](\d{6})', html, re.I)
    )
    if not ccn_ok:
        fails.append('no_ccn_marker')
    if re.search(r'\bnan\b', html[:80000], re.I):
        fails.append('nan_string')
    if 'pbj-chart-container"></div>' in html.replace(' ', ''):
        fails.append('empty_chart_card')
    return (len(fails) == 0, fails)


def _pick_ccns() -> dict[str, list[str]]:
    import pandas as pd

    out: dict[str, list[str]] = {
        'random_100': [],
        'largest_entities': [],
        'low_hprd': [],
        'high_contract': [],
        'small_states': [],
    }
    fq_path = ROOT / 'facility_quarterly_metrics.csv'
    pi_path = ROOT / 'provider_info' / 'ProviderInfoNorm_2026_04.csv'
    if not pi_path.is_file():
        pi_path = sorted((ROOT / 'provider_info').glob('ProviderInfoNorm_*.csv'))[-1]

    all_ccns: list[str] = []
    if fq_path.is_file():
        for chunk in pd.read_csv(fq_path, usecols=['PROVNUM'], chunksize=200000, low_memory=False):
            all_ccns.extend(chunk['PROVNUM'].astype(str).str.zfill(6).tolist())
    all_ccns = [c for c in all_ccns if len(c) == 6 and c.isdigit()]
    random.seed(42)
    out['random_100'] = random.sample(all_ccns, min(100, len(all_ccns)))

    pi = pd.read_csv(pi_path, dtype=str, low_memory=False)
    ccn_col = next((c for c in pi.columns if 'provnum' in c.lower() or 'ccn' in c.lower()), pi.columns[0])
    ent_col = next((c for c in pi.columns if 'entity_id' in c.lower()), None)
    st_col = next((c for c in pi.columns if c.upper() == 'STATE' or c.lower() == 'state'), None)
    pi['_ccn'] = pi[ccn_col].astype(str).str.zfill(6)

    if ent_col:
        vc = pi[ent_col].value_counts()
        big = vc.head(25).index.tolist()
        for eid in big:
            sub = pi[pi[ent_col] == eid]
            if not sub.empty:
                out['largest_entities'].append(sub.iloc[0]['_ccn'])

    if fq_path.is_file() and os.path.getsize(fq_path) > 0:
        latest = None
        for chunk in pd.read_csv(fq_path, usecols=['CY_Qtr'], chunksize=200000, low_memory=False):
            q = chunk['CY_Qtr'].astype(str).max()
            if latest is None or str(q) > str(latest):
                latest = q
        cols = ['PROVNUM', 'CY_Qtr', 'Total_Nurse_HPRD', 'Contract_Percentage', 'STATE']
        head = pd.read_csv(fq_path, nrows=0)
        usecols = [c for c in cols if c in head.columns]
        sub_chunks = []
        for chunk in pd.read_csv(fq_path, usecols=usecols, chunksize=150000, low_memory=False):
            c = chunk[chunk['CY_Qtr'].astype(str) == str(latest)].copy()
            if c.empty:
                continue
            c['_ccn'] = c['PROVNUM'].astype(str).str.zfill(6)
            sub_chunks.append(c)
        if sub_chunks:
            sub = pd.concat(sub_chunks, ignore_index=True)
            sub['_h'] = pd.to_numeric(sub['Total_Nurse_HPRD'], errors='coerce')
            sub['_c'] = pd.to_numeric(sub['Contract_Percentage'], errors='coerce')
            lo = sub[sub['_h'] <= 2.5].dropna(subset=['_h'])
            hi = sub[sub['_c'] >= 40].dropna(subset=['_c'])
            out['low_hprd'] = lo['_ccn'].drop_duplicates().head(25).tolist()
            out['high_contract'] = hi['_ccn'].drop_duplicates().head(25).tolist()
            if st_col and st_col in pi.columns:
                st_counts = pi[st_col].astype(str).str.upper().value_counts()
                small = st_counts[st_counts <= 30].index.tolist()[:25]
                for st in small:
                    row = sub[sub.get('STATE', sub.get('state', pd.Series())).astype(str).str.upper() == st]
                    if not row.empty:
                        out['small_states'].append(row.iloc[0]['_ccn'])

    seen = set()
    merged: list[str] = []
    for key, lst in out.items():
        for c in lst:
            if c not in seen and len(c) == 6 and c.isdigit():
                seen.add(c)
                merged.append(c)
    out['_all_unique'] = merged
    return out


def main() -> int:
    import app as m

    buckets = _pick_ccns()
    all_ccns = buckets['_all_unique']
    print(f'sample_total_unique={len(all_ccns)}')

    log_buf = io.StringIO()
    rows = []
    with redirect_stdout(log_buf):
        client = m.app.test_client()
        m._PROVIDER_INDEXES_HYDRATED = False
        m.clear_provider_page_cache()
        for prov in all_ccns:
            m.clear_provider_page_cache()
            t0 = time.perf_counter()
            r = client.get(f'/provider/{prov}', headers={'User-Agent': 'Mozilla/5.0'})
            ms = round((time.perf_counter() - t0) * 1000, 1)
            html = r.get_data(as_text=True)
            ok, fails = _critical_ok(html, r.status_code, prov)
            rows.append((prov, r.status_code, ms, ok, ','.join(fails) if fails else ''))

    log = log_buf.getvalue()
    bad_logs = {
        'entity_metrics_stream': log.count('"event":"entity_metrics_stream"') + log.count('entity_metrics_stream'),
        'provider_index_fallback': log.count('"event":"provider_index_fallback"'),
        'state_percentile_csv_rebuild': log.count('state_percentile_csv_rebuild'),
        'facility_quarterly_lookup_sqlite': log.count('"event":"facility_quarterly_lookup"'),
        'provider_indexes_hydrated': log.count('"event":"provider_indexes_hydrated"'),
    }

    fail_rows = [r for r in rows if not r[3]]
    status_counts = {}
    for _, st, _, _, _ in rows:
        status_counts[st] = status_counts.get(st, 0) + 1

    print('\n| bucket | n | pass | fail |')
    for key in ('random_100', 'largest_entities', 'low_hprd', 'high_contract', 'small_states'):
        lst = buckets.get(key, [])
        sub = [r for r in rows if r[0] in lst]
        p = sum(1 for r in sub if r[3])
        print(f'| {key} | {len(lst)} | {p} | {len(sub) - p} |')

    print('\n| status | count |')
    for st, n in sorted(status_counts.items()):
        print(f'| {st} | {n} |')

    print('\n| log signal | count |')
    for k, v in bad_logs.items():
        print(f'| {k} | {v} |')

    if fail_rows[:15]:
        print('\nFirst failures:')
        for r in fail_rows[:15]:
            print(f'  {r[0]} status={r[1]} ms={r[2]} {r[4]}')

    ok_deploy = (
        len(fail_rows) == 0
        and bad_logs['entity_metrics_stream'] == 0
        and bad_logs['provider_index_fallback'] == 0
        and bad_logs['state_percentile_csv_rebuild'] == 0
        and bad_logs['facility_quarterly_lookup_sqlite'] >= len(all_ccns) * 0.9
    )
    print(f'\nOVERALL: {"PASS" if ok_deploy else "FAIL"}')
    return 0 if ok_deploy else 1


if __name__ == '__main__':
    raise SystemExit(main())
